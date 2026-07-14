"""단일 플러그인 프로브 (서브프로세스 전용) — 결과를 JSON 한 줄로 stdout에 출력.

사용: python spikes/host_probe.py <플러그인경로> [--name <shell 내 이름>] [--preset <vstpreset>]
행업 대비를 위해 부모(host_poc.py)가 타임아웃으로 관리한다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

READABLE_RE = re.compile(r"[A-Za-z]{3,}")
OPAQUE_RE = re.compile(r"^(param(eter)?|p)[\s_#-]*\d+$", re.I)


def param_quality(names: list[str]) -> tuple[int, int]:
    readable = sum(1 for n in names
                   if READABLE_RE.search(n) and not OPAQUE_RE.match(n.strip()))
    return readable, len(names)


def dump_values(plugin, defaults: dict) -> tuple[list[dict], int]:
    """파라미터 이름/표시값 전체 덤프 + 기본값 대비 변경 수."""
    dump: list[dict] = []
    changed = 0
    for k, p in plugin.parameters.items():
        label = getattr(p, "name", k)
        m = re.search(r'value=(?:"([^"]*)"|(\S+))', str(p))
        display = (m.group(1) or m.group(2)) if m else str(p.raw_value)
        is_changed = p.raw_value != defaults.get(k)
        changed += is_changed
        dump.append({"name": label, "value": display, "changed": is_changed})
    return dump, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--name", default=None)
    ap.add_argument("--preset", default=None)
    ap.add_argument("--list-names", action="store_true")
    ap.add_argument("--dump", action="store_true",
                    help="프리셋 주입 후 전체 파라미터 이름/표시값 덤프")
    ap.add_argument("--presets-json", default=None,
                    help='배치 모드: {"presets": [경로…]} JSON 파일 — 플러그인 1회 로드로 전체 처리')
    args = ap.parse_args()

    result: dict = {"path": args.path, "subname": args.name}
    try:
        import pedalboard
        if args.list_names:
            names = pedalboard.VST3Plugin.get_plugin_names_for_file(args.path)
            print(json.dumps({"ok": True, "names": names}))
            return 0
        kwargs = {"plugin_name": args.name} if args.name else {}
        plugin = pedalboard.load_plugin(args.path, **kwargs)
        # 사람이 읽는 표시 이름 확보 (parameters dict 키는 python화된 이름)
        display = [getattr(p, "name", k) for k, p in plugin.parameters.items()]
        readable, total = param_quality(display)
        result.update(ok=True, loaded=True, param_count=total,
                      readable_count=readable,
                      sample_params=display[:12])
        if args.preset:
            # 레시피: load_preset → raw_state 캡처 → 새 인스턴스에 재주입 →
            # 컨트롤러 파라미터가 프리셋 값으로 동기화됨 (FabFilter 실측)
            defaults = {k: v.raw_value for k, v in plugin.parameters.items()}
            plugin.load_preset(args.preset)
            state = bytes(plugin.raw_state)
            fresh = pedalboard.load_plugin(args.path, **kwargs)
            fresh.raw_state = state
            changed = sum(1 for k, v in fresh.parameters.items()
                          if v.raw_value != defaults.get(k))
            values = []
            for k, p in fresh.parameters.items():
                if p.raw_value != defaults.get(k):
                    values.append(f"{getattr(p, 'name', k)} = {p}")
            result.update(preset_loaded=True, params_changed=changed,
                          preset_values_sample=values[:20])
            if args.dump:
                result["values"], _ = dump_values(fresh, defaults)
        if args.presets_json:
            # 배치: 이미 로드된 인스턴스를 재사용 — 프리셋마다 raw_state 레시피 적용
            spec = json.loads(Path(args.presets_json).read_text(encoding="utf-8"))
            defaults = {k: v.raw_value for k, v in plugin.parameters.items()}
            batch: dict[str, dict] = {}
            for preset_path in spec["presets"]:
                try:
                    plugin.load_preset(preset_path)
                    state = bytes(plugin.raw_state)
                    fresh = pedalboard.load_plugin(args.path, **kwargs)
                    fresh.raw_state = state
                    dump, changed = dump_values(fresh, defaults)
                    batch[preset_path] = {"ok": True, "params_changed": changed,
                                          "values": dump}
                except Exception as exc:  # noqa: BLE001 — 프리셋별 실패 격리
                    batch[preset_path] = {"ok": False,
                                          "error": f"{type(exc).__name__}: {exc}"}
            result["batch"] = batch
    except Exception as exc:  # noqa: BLE001 — 프로브는 모든 실패를 보고로 변환
        result.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        print(json.dumps(result, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
