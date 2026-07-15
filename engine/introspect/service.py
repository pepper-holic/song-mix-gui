"""vstpreset 해석 서비스 — 프리셋을 플러그인에 주입해 파라미터 이름/값을 덤프.

플러그인 로드는 크래시/행업 격리를 위해 항상 서브프로세스(host_probe --dump)로.
결과는 (프리셋 바이트 해시, 바이너리) 키로 캐시.

P3(v2, 플러그인 그룹 입도 프리웜 우선순위): 배치 프로브는 플러그인 바이너리 단위이므로
(1회 로드로 여러 프리셋 처리) 우선순위도 그룹(바이너리+서브플러그인) 단위로만 재정렬한다
— 항목 단위 큐는 배치 효율을 파괴하므로 채택하지 않음(계획 Critic MAJOR① 반영).
"""
import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from ..songcore import SongContainer
from .inventory import Inventory
from .runtime import data_dir, probe_cmd

CACHE_DIR = data_dir() / "param_cache"
PROBE_TIMEOUT = 240


def _cache_key(preset_bytes: bytes, res) -> str:
    return hashlib.md5(preset_bytes + res.path.encode()
                       + (res.subname or "").encode()).hexdigest()


def _shape_output(data: dict, plugin_name: str) -> dict:
    """프로브 결과({ok, values…} 또는 {ok:False, error}) → GUI 응답 포맷."""
    if not data.get("ok"):
        return {"status": "uninterpretable", "pluginName": plugin_name,
                "params": [],
                "message": f"로드 실패 — 복사 가능: {str(data.get('error'))[:200]}"}
    values = data.get("values", [])
    changed = [v for v in values if v.get("changed")]
    shown = changed if changed else values
    return {"status": "ok", "pluginName": plugin_name,
            "params": [{"name": v["name"], "value": v["value"]}
                       for v in shown[:400]],
            "message": (f"프리셋 반영 파라미터 {len(changed)}개 표시"
                        if changed else "기본값과 동일 — 전체 파라미터 표시")}


GroupKey = tuple[str, str | None]  # (bin_path, subname)


class InterpretService:
    def __init__(self, inventory: Inventory | None = None):
        self.inventory = inventory or Inventory()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._queue: list[GroupKey] = []
        self._pending: dict[GroupKey, list[tuple[str, str, bytes]]] = {}
        self._done_groups = 0
        self._total_groups = 0

    def prewarm(self, song_path: Path,
                inserts: list[tuple[str, str]]) -> dict[str, int]:
        """(preset_entry, plugin_name) 목록을 플러그인별 배치 프로브로 미리 해석·캐시.

        백그라운드 스레드에서 호출 — 이후 interpret()는 캐시 적중으로 즉시 응답.
        그룹(바이너리+서브플러그인) 단위 큐로 처리하며, hint_visible()로 남은 큐의
        순서를 재정렬할 수 있다(그룹 큐는 self._lock으로 브리지↔워커 레이스 차단).
        반환: 통계 {"cached_hit": n, "warmed": n, "failed": n}.
        """
        stats = {"cached_hit": 0, "warmed": 0, "failed": 0}
        container = SongContainer.read(Path(song_path))
        groups: dict[GroupKey, list[tuple[str, str, bytes]]] = {}
        for preset_entry, plugin_name in inserts:
            res = self.inventory.resolve(plugin_name)
            if res is None:
                stats["failed"] += 1
                continue
            try:
                preset_bytes = container.read_entry(preset_entry)
            except KeyError:
                stats["failed"] += 1
                continue
            if (CACHE_DIR / f"{_cache_key(preset_bytes, res)}.json").exists():
                stats["cached_hit"] += 1
                continue
            groups.setdefault((res.path, res.subname), []).append(
                (preset_entry, plugin_name, preset_bytes))

        with self._lock:
            self._pending = groups
            self._queue = list(groups.keys())
            self._total_groups = len(self._queue)
            self._done_groups = 0

        while True:
            with self._lock:
                if not self._queue:
                    break
                key = self._queue.pop(0)
                items = self._pending.pop(key, None)
            if items:
                warmed, failed = self._probe_group(key, items)
                stats["warmed"] += warmed
                stats["failed"] += failed
            with self._lock:
                self._done_groups += 1
        return stats

    def _probe_group(self, key: GroupKey,
                     items: list[tuple[str, str, bytes]]) -> tuple[int, int]:
        """그룹 1개(바이너리+서브플러그인)를 배치 프로브 1회로 처리. 반환: (warmed, failed)."""
        bin_path, subname = key
        warmed = failed = 0
        tmpdir = Path(tempfile.mkdtemp(prefix="prewarm_"))
        tmp_map: dict[str, tuple[str, bytes]] = {}
        try:
            spec_presets = []
            for i, (_entry, plugin_name, preset_bytes) in enumerate(items):
                tmp = tmpdir / f"{i}.vstpreset"
                tmp.write_bytes(preset_bytes)
                spec_presets.append(str(tmp))
                tmp_map[str(tmp)] = (plugin_name, preset_bytes)
            spec_file = tmpdir / "batch.json"
            spec_file.write_text(json.dumps({"presets": spec_presets}),
                                 encoding="utf-8")
            cmd = probe_cmd(bin_path, "--presets-json", str(spec_file))
            if subname:
                cmd += ["--name", subname]
            timeout = PROBE_TIMEOUT + 30 * len(items)
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", timeout=timeout)
            lines = (r.stdout or "").strip().splitlines()
            data = json.loads(lines[-1]) if lines else {"ok": False, "error": "출력 없음"}
            batch = data.get("batch", {}) if data.get("ok") else {}
            for tmp_path, (plugin_name, preset_bytes) in tmp_map.items():
                entry_data = batch.get(tmp_path, data)  # 전체 실패 시 로드 오류 전파
                out = _shape_output(entry_data, plugin_name)
                res = self.inventory.resolve(plugin_name)
                cache_key = _cache_key(preset_bytes, res)
                (CACHE_DIR / f"{cache_key}.json").write_text(
                    json.dumps(out, ensure_ascii=False), encoding="utf-8")
                if out["status"] == "ok":
                    warmed += 1
                else:
                    failed += 1
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            failed += len(items)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        return warmed, failed

    def hint_visible(self, plugin_names: list[str]) -> None:
        """가시/선택 채널이 쓰는 플러그인의 그룹을 프리웜 큐 선두로 재정렬.

        미캐시 클릭(interpret() 캐시 미스) 시에도 동일 메커니즘으로 승격된다.
        """
        target_keys: set[GroupKey] = set()
        for name in plugin_names:
            res = self.inventory.resolve(name)
            if res is not None:
                target_keys.add((res.path, res.subname))
        if not target_keys:
            return
        with self._lock:
            priority = [k for k in self._queue if k in target_keys]
            rest = [k for k in self._queue if k not in target_keys]
            self._queue = priority + rest

    def prewarm_status(self) -> dict[str, int]:
        """프리웜 진행률 — 입도는 그룹 단위(N/M 플러그인 완료), 항목 단위 아님(AC-5 판정 기준)."""
        with self._lock:
            return {"done": self._done_groups, "total": self._total_groups}

    def interpret(self, song_path: Path, preset_entry: str,
                  plugin_name: str) -> dict:
        """반환: {status, pluginName, params[], message?} — GUI 응답 포맷."""
        try:
            container = SongContainer.read(Path(song_path))
            preset_bytes = container.read_entry(preset_entry)
        except (OSError, KeyError) as exc:
            return {"status": "error", "pluginName": plugin_name, "params": [],
                    "message": f"프리셋 읽기 실패: {exc}"}

        res = self.inventory.resolve(plugin_name)
        if res is None:
            return {"status": "uninterpretable", "pluginName": plugin_name,
                    "params": [],
                    "message": "설치된 바이너리를 찾지 못함 — 바이너리 복사/전송은 가능"}

        cache_file = CACHE_DIR / f"{_cache_key(preset_bytes, res)}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        # 미캐시 클릭: 백그라운드 프리웜 큐에 이 플러그인 그룹이 남아있으면 승격(P3)
        self.hint_visible([plugin_name])

        with tempfile.NamedTemporaryFile(suffix=".vstpreset", delete=False) as tf:
            tf.write(preset_bytes)
            tmp = Path(tf.name)
        try:
            cmd = probe_cmd(res.path, "--preset", str(tmp), "--dump")
            if res.subname:
                cmd += ["--name", res.subname]
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", timeout=PROBE_TIMEOUT)
            lines = (r.stdout or "").strip().splitlines()
            data = json.loads(lines[-1]) if lines else {"ok": False, "error": "출력 없음"}
        except subprocess.TimeoutExpired:
            data = {"ok": False, "error": f"플러그인 응답 없음({PROBE_TIMEOUT}s)"}
        except json.JSONDecodeError as exc:
            data = {"ok": False, "error": f"프로브 출력 손상: {exc}"}
        finally:
            tmp.unlink(missing_ok=True)

        out = _shape_output(data, plugin_name)
        cache_file.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out
