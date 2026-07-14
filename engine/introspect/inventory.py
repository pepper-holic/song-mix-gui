"""플러그인 인벤토리 — classInfo 이름 → 바이너리(경로, 셸 서브플러그인명) 해석.

S0.2 실측 근거: 등급표(.omc/verify/plugin-grade-table.md)와 동일한 해석 전략.
WaveShell 서브플러그인 열거 결과는 캐시(JSON)로 보관한다.
"""
import json
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

VST3_DIR = Path("C:/Program Files/Common Files/VST3")
CACHE_PATH = Path(__file__).resolve().parents[2] / "spikes/out/inventory_cache.json"
PROBE = Path(__file__).resolve().parents[2] / "spikes/host_probe.py"
SHELL_SCAN_TIMEOUT = 300


@dataclass(frozen=True)
class Resolution:
    path: str
    subname: str | None  # WaveShell 내 플러그인명 (없으면 단독 vst3)


def _norm(label: str) -> str:
    """비교용 정규화: 'CLA-76 Stereo 3' → 'cla-76', 'Little Plate' → 'littleplate'."""
    label = re.sub(r"\s*\(\d+\)\s*$", "", label)
    label = re.sub(r"\s+(Mono|Stereo)(\s+\d+)?$", "", label, flags=re.I)
    label = re.sub(r"\s+\d+$", "", label)
    return label.strip().lower().replace(" ", "")


class Inventory:
    def __init__(self, cache_path: Path = CACHE_PATH):
        self.cache_path = cache_path
        self._shell_names: dict[str, str] = {}   # subplugin name → shell path
        self._files: dict[str, str] = {}          # normalized stem → path
        self._loaded = False
        self._load_lock = threading.Lock()  # GUI/프리웜 스레드 동시 스캔 방지

    def _scan_shells(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for shell in sorted(VST3_DIR.glob("WaveShell*-VST3*.vst3")):
            try:
                r = subprocess.run(
                    [sys.executable, str(PROBE), str(shell), "--list-names"],
                    capture_output=True, text=True, encoding="utf-8",
                    timeout=SHELL_SCAN_TIMEOUT)
                data = json.loads((r.stdout or "").strip().splitlines()[-1])
                if data.get("ok"):
                    for n in data["names"]:
                        names[n] = str(shell)
            except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
                continue
        return names

    def load(self, rescan: bool = False) -> None:
        if self._loaded and not rescan:
            return
        with self._load_lock:
            self._load_locked(rescan)

    def _load_locked(self, rescan: bool) -> None:
        if self._loaded and not rescan:
            return
        if self.cache_path.exists() and not rescan:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self._shell_names = cached.get("shell_names", {})
            self._files = cached.get("files", {})
        else:
            self._shell_names = self._scan_shells()
            self._files = {}
            for root in (VST3_DIR, *[p for p in VST3_DIR.iterdir() if p.is_dir()]):
                for f in root.glob("*.vst3"):
                    if f.name.startswith("WaveShell"):
                        continue
                    self._files[_norm(f.stem)] = str(f)
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(
                {"shell_names": self._shell_names, "files": self._files},
                ensure_ascii=False, indent=1), encoding="utf-8")
        self._loaded = True

    def resolve(self, class_info_name: str) -> Resolution | None:
        """audiomixer classInfo name(예: 'CLA-76 Stereo', 'Pro-Q 3')을 바이너리로."""
        self.load()
        norm = _norm(class_info_name)
        # 1) WaveShell 서브플러그인 (Stereo 우선)
        candidates = [(n, p) for n, p in self._shell_names.items()
                      if _norm(n) == norm]
        if candidates:
            stereo = next((c for c in candidates if "Stereo" in c[0]), candidates[0])
            return Resolution(stereo[1], stereo[0])
        # 2) 단독 vst3 파일 (부분 일치 허용: 'Pro-Q 3' → 'FabFilter Pro-Q 3')
        if norm in self._files:
            return Resolution(self._files[norm], None)
        for stem, path in self._files.items():
            if stem.endswith(norm) or norm in stem:
                return Resolution(path, None)
        # 3) 버전 승계 (Pro-Q → Pro-Q 3, Pro-R → Pro-R 2 — S0.2 검증됨)
        for stem, path in self._files.items():
            if stem.startswith(norm):
                return Resolution(path, None)
        return None
