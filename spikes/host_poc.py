"""S0.2 호스팅 + 파라미터 품질 스파이크 오케스트레이터.

실사용 22종 플러그인에 대해:
  - 바이너리 해석(VST3 단독 / WaveShell 서브플러그인)
  - 서브프로세스 프로브(행업/크래시 격리, 타임아웃)
  - 코퍼스에서 플러그인별 vstpreset 1개 확보 후 주입 검증
  - 3단계 등급표(.omc/verify/plugin-grade-table.md) 산출

사용: python spikes/host_poc.py
"""
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VST3 = Path("C:/Program Files/Common Files/VST3")
SONGS = Path("C:/Users/yhkze/Documents/Studio Pro/Songs")
PRESET_DIR = ROOT / "spikes/out/presets_by_plugin"
OUT_MD = ROOT / ".omc/verify/plugin-grade-table.md"
OUT_JSON = ROOT / "spikes/out/host_poc_results.json"
PROBE = ROOT / "spikes/host_probe.py"
PROBE_TIMEOUT = 240

WAVESHELLS = [VST3 / f"WaveShell1-VST3 {v}_x64.vst3" for v in ("15.5", "16.6", "16.7", "17.1")]

# 22종: 표시명 → (프리셋 파일명 매칭 접두사들, 바이너리 후보)
# 바이너리 후보: ("file", 경로) 또는 ("shell", 서브플러그인명 접두사)
TARGETS: list[tuple[str, list[str], list[tuple[str, object]]]] = [
    ("Waves CLA-76", ["CLA-76"], [("shell", "CLA-76 Stereo"), ("shell", "CLA-76 Mono")]),
    ("Soundtoys Decapitator", ["Decapitator"], [("file", VST3 / "Soundtoys/Decapitator.vst3")]),
    ("Waves SSLComp", ["SSLComp"], [("shell", "SSLComp Stereo"), ("shell", "SSLComp Mono")]),
    ("Waves Maag EQ2", ["Maag EQ2"], [("shell", "Maag EQ2"), ("file", VST3 / "Maag EQ2.vst3")]),
    ("FabFilter Pro-Q 3", ["Pro-Q 3"], [("file", VST3 / "FabFilter Pro-Q 3.vst3")]),
    ("JST Clip", ["JST Clip"], [("file", VST3 / "JST Clip.vst3")]),
    ("SPL Transient Designer Plus", ["SPL Transient Designer Plus"],
     [("file", VST3 / "SPL Transient Designer Plus.vst3")]),
    ("JST Gain Reduction Deluxe", ["Gain Reduction Deluxe"],
     [("file", VST3 / "Gain Reduction Deluxe.vst3")]),
    ("mvMeter2", ["mvMeter2"], [("file", VST3 / "TBProAudio/mvMeter2.vst3")]),
    ("Waves L4 Ultramaximizer", ["L4 Ultramaximizer"],
     [("shell", "L4 Ultramaximizer Stereo"), ("shell", "L4 Ultramaximizer Mono")]),
    ("SPL Attacker Plus", ["SPL Attacker Plus", "Attacker Plus"],
     [("file", VST3 / "SPL Attacker Plus.vst3")]),
    ("Soundtoys Little Plate", ["Little Plate"], [("file", VST3 / "Soundtoys/LittlePlate.vst3")]),
    ("Soundtoys Little MicroShift", ["Little MicroShift", "MicroShift"],
     [("file", VST3 / "Soundtoys/LittleMicroShift.vst3")]),
    ("Waves Scheps Omni Channel 2", ["Scheps Omni Channel 2", "Scheps Omni Channel"],
     [("shell", "Scheps Omni Channel 2 Stereo"), ("shell", "Scheps Omni Channel 2 Mono")]),
    ("IK AmpliTube 5", ["AmpliTube 5"], [("file", VST3 / "AmpliTube 5.vst3")]),
    ("Waves EQP-1A", ["EQP-1A", "PuigTec EQP-1A"],
     [("shell", "PuigTec EQP-1A"), ("shell", "EQP-1A")]),
    ("Slate Trigger 2", ["Trigger 2"], [("file", VST3 / "Trigger_2.vst3")]),
    ("Soundtoys Devil-Loc", ["Devil-Loc", "DevilLoc"], [("file", VST3 / "Soundtoys/DevilLoc.vst3")]),
    ("FabFilter Pro-Q", ["Pro-Q"], [("file", VST3 / "FabFilter Pro-Q 3.vst3")]),
    ("Magma StressBox", ["Magma StressBox", "StressBox"],
     [("shell", "Magma StressBox Stereo"), ("shell", "Magma StressBox Mono")]),
    ("Waves De Esser", ["De Esser", "DeEsser"], [("shell", "DeEsser"), ("shell", "De Esser")]),
    ("FabFilter Pro-R", ["Pro-R"], [("file", VST3 / "FabFilter Pro-R 2.vst3")]),
]


def run_probe(args: list[str]) -> dict:
    cmd = [sys.executable, str(PROBE), *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           timeout=PROBE_TIMEOUT)
        line = (r.stdout or "").strip().splitlines()
        if line:
            return json.loads(line[-1])
        return {"ok": False, "error": f"no output (stderr: {(r.stderr or '')[-300:]})"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout {PROBE_TIMEOUT}s"}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"bad json: {exc}"}


def enumerate_shells() -> dict[str, Path]:
    """서브플러그인명 → shell 경로. 스캔 실패 shell은 기록."""
    mapping: dict[str, Path] = {}
    failures: list[str] = []
    for shell in WAVESHELLS:
        res = run_probe([str(shell), "--list-names"])
        if res.get("ok"):
            for n in res["names"]:
                mapping[n] = shell
        else:
            failures.append(f"{shell.name}: {res.get('error')}")
    (ROOT / "spikes/out/waveshell_scan.json").write_text(
        json.dumps({"names": {k: str(v) for k, v in mapping.items()},
                    "failures": failures}, ensure_ascii=False, indent=1), encoding="utf-8")
    return mapping


PRESET_NAME_RE = re.compile(r"^\d+ - (.+)\.vstpreset$")


def normalize(label: str) -> str:
    label = re.sub(r"\s*\((\d+)\)\s*$", "", label)
    label = re.sub(r"\s+(Mono|Stereo)(\s+\d+)?$", "", label)
    label = re.sub(r"\s+\d+$", "", label)
    return label.strip()


def find_corpus_presets() -> dict[str, Path]:
    """플러그인 표시명 → 추출된 vstpreset 경로 (naiite_14 우선, 코퍼스 폴백)."""
    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    found: dict[str, Path] = {}
    songs = sorted(SONGS.rglob("*.song"),
                   key=lambda p: (0 if "naiite_14" in p.name else 1, str(p)))
    # 매칭 우선순위: 접두사가 긴 것 먼저 (Pro-Q 3가 Pro-Q보다 먼저)
    matchers: list[tuple[str, str]] = []
    for disp, prefixes, _ in TARGETS:
        for pre in prefixes:
            matchers.append((pre, disp))
    matchers.sort(key=lambda t: -len(t[0]))

    for song in songs:
        if len(found) == len(TARGETS):
            break
        try:
            with zipfile.ZipFile(song) as zf:
                for name in zf.namelist():
                    if not name.startswith("Presets/Channels/"):
                        continue
                    m = PRESET_NAME_RE.match(name.rsplit("/", 1)[-1])
                    if not m:
                        continue
                    base = normalize(m.group(1))
                    for pre, disp in matchers:
                        if disp in found:
                            continue
                        if base == pre or base.startswith(pre + " ") or base.startswith(pre + "."):
                            dst = PRESET_DIR / f"{disp}.vstpreset"
                            dst.write_bytes(zf.read(name))
                            found[disp] = dst
                            break
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"  corpus skip {song.name}: {exc}")
    return found


def grade(res: dict, has_preset: bool) -> tuple[str, str]:
    if not res.get("ok"):
        return "복사만 가능", res.get("error", "?")
    total = res.get("param_count", 0)
    readable = res.get("readable_count", 0)
    ratio = readable / total if total else 0
    injected = res.get("preset_loaded") and res.get("params_changed", 0) > 0
    if ratio >= 0.6 and injected:
        return "해석 가능", f"파라미터 {total}개(가독 {readable}), 주입 후 {res['params_changed']}개 변경"
    if ratio >= 0.6 and has_preset and res.get("preset_loaded") and res.get("params_changed", 0) == 0:
        return "부분 해석", f"로드/이름 OK({readable}/{total}), 프리셋 주입이 파라미터에 미반영"
    if ratio >= 0.6:
        return "부분 해석", f"로드/이름 OK({readable}/{total}), 코퍼스에 프리셋 없음 → 주입 미검증"
    return "부분 해석", f"로드 OK, 파라미터 이름 불투명({readable}/{total})"


def main() -> int:
    print("=== WaveShell 열거 ===")
    shell_map = enumerate_shells()
    print(f"  subplugins: {len(shell_map)}")
    print("=== 코퍼스 프리셋 수집 ===")
    presets = find_corpus_presets()
    print(f"  presets found: {len(presets)}/{len(TARGETS)}")

    results = []
    for disp, _prefixes, candidates in TARGETS:
        chosen: list[str] | None = None
        note = ""
        for kind, val in candidates:
            if kind == "file":
                if Path(val).exists():
                    chosen = [str(val)]
                    break
            else:  # shell
                hit = next((n for n in shell_map if n.startswith(str(val))), None)
                if hit:
                    chosen = [str(shell_map[hit]), "--name", hit]
                    break
        preset = presets.get(disp)
        if disp == "FabFilter Pro-Q" and preset:
            # Pro-Q(v1) 프리셋을 Pro-Q 3 바이너리로 열 수 있는지 실험 (클래스ID 다르면 실패 기록)
            note = "Pro-Q(v1) 미설치 — Pro-Q 3 바이너리로 주입 시도"
        if not chosen:
            results.append({"plugin": disp, "grade": "복사만 가능",
                            "detail": "바이너리 미발견(스캔 실패 shell 소속 가능)", "note": note})
            print(f"[{disp}] 바이너리 미발견")
            continue
        args = chosen + (["--preset", str(preset)] if preset else [])
        print(f"[{disp}] probing… ({' '.join(args[:1])}{' :: ' + args[2] if len(chosen) > 1 else ''})")
        res = run_probe(args)
        if not res.get("ok") and preset:
            # 프리셋 주입 실패가 로드 실패로 오인되지 않게 프리셋 없이 재시도
            res_nop = run_probe(chosen)
            if res_nop.get("ok"):
                res_nop["preset_injection_error"] = res.get("error")
                res = res_nop
        g, detail = grade(res, preset is not None)
        if res.get("preset_injection_error"):
            g = "부분 해석"
            detail += f" | 주입 오류: {res['preset_injection_error'][:120]}"
        results.append({"plugin": disp, "grade": g, "detail": detail, "note": note,
                        "raw": {k: v for k, v in res.items()
                                if k not in ("preset_values_sample",)},
                        "values_sample": res.get("preset_values_sample", [])[:8]})
        print(f"  -> {g}: {detail[:100]}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# 플러그인 해석 등급표 (S0.2)", "",
             "| 플러그인 | 등급 | 상세 |", "|---|---|---|"]
    for r in results:
        note = f" ({r['note']})" if r.get("note") else ""
        lines.append(f"| {r['plugin']}{note} | **{r['grade']}** | {r['detail']} |")
    counts = {}
    for r in results:
        counts[r["grade"]] = counts.get(r["grade"], 0) + 1
    lines += ["", f"- 합계: {counts}",
              "- 엔진: pedalboard 0.9.23 (Python 3.14) — WaveShell 로드 지원 실측됨",
              "- 주입 레시피: load_preset → raw_state 캡처 → 새 인스턴스 raw_state 재주입 → 컨트롤러 동기화",
              "- 상세 값 샘플: spikes/out/host_poc_results.json"]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\ngrade table: {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
