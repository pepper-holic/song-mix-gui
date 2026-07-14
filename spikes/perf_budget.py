"""P1 성능 계측 스크립트 (v2 Phase P, AC-5).

예산: 시작<3s, song 열기→그래프 표시<1s, 캐시 해석<0.3s, 전송+저장<3s.
실행: PYTHONIOENCODING=utf-8 python spikes/perf_budget.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")
DST_SRC = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_HWA_SPLIT/sp_hwa_14/sp_hwa_14 (fixed).song")

BUDGETS = {
    "startup": 3.0,
    "open_to_graph": 1.0,
    "cached_interpret": 0.3,
    "transfer_and_save": 3.0,
}


def measure_startup_and_open() -> dict[str, float]:
    """GUI 프로세스를 --self-test로 spawn해 main.py가 출력하는 [perf] 라인을 파싱."""
    cmd = [sys.executable, str(ROOT / "app/main.py"), "--self-test"]
    env = {"QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    import os
    full_env = {**os.environ, **env}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env=full_env)
    out = r.stdout
    results: dict[str, float] = {}
    for m in re.finditer(r"\[perf\] (\w+)=([\d.]+)s", out):
        results[m.group(1)] = float(m.group(2))
    if "SELF-TEST PASS" not in out:
        print("경고: self-test가 PASS로 끝나지 않음 — 계측치 신뢰도 낮음")
        print(out[-500:])
    return results


def measure_cached_interpret() -> float:
    """캐시 워밍 후 InterpretService.interpret() 1회 호출 시간(캐시 히트 경로)."""
    from engine.introspect import Inventory, InterpretService
    from engine.songcore import SongContainer, load_model

    container = SongContainer.read(NAIITE)
    model = load_model(container)
    kbus = model.by_label("K.BUS")
    ins = next(i for i in kbus.inserts if i.preset_path)

    service = InterpretService(Inventory())
    inserts = [(i.preset_path, i.plugin_name) for ch in model.channels
               for i in ch.inserts if i.preset_path]
    service.prewarm(NAIITE, inserts)  # 워밍 — 이 시간은 예산 대상 아님

    t0 = time.perf_counter()
    service.interpret(NAIITE, ins.preset_path, ins.plugin_name)
    return time.perf_counter() - t0


def measure_transfer_and_save() -> float:
    """엔진 레벨(GUI 없이) transfer_subtree + save_pipeline 동등 파이프라인 시간."""
    from engine.songcore import SongContainer, load_model
    from engine.songcore.transfer import transfer_subtree
    from engine.songcore.uid_refs import errors_of, validate

    tmpdir = Path(tempfile.mkdtemp(prefix="perf_budget_"))
    try:
        dst_path = tmpdir / "dst.song"
        shutil.copy2(DST_SRC, dst_path)

        src = SongContainer.read(NAIITE)
        src_model = load_model(src)
        kbus_uid = src_model.by_label("K.BUS").uid

        t0 = time.perf_counter()
        dst = SongContainer.read(dst_path)
        transfer_subtree(src, src_model, kbus_uid, dst)
        dst.save_over(dst_path)
        reread = SongContainer.read(dst_path)
        errs = errors_of(validate(reread, load_model(reread)))
        elapsed = time.perf_counter() - t0
        if errs:
            print(f"경고: 전송 후 검증 실패 — {errs[:2]}")
        return elapsed
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    print("=== P1 성능 계측 (spikes/perf_budget.py) ===\n")
    results: dict[str, float] = {}

    print("[1/3] 시작 + 열기→그래프 (GUI --self-test 서브프로세스)…")
    results.update(measure_startup_and_open())

    print("[2/3] 캐시 해석…")
    results["cached_interpret"] = measure_cached_interpret()

    print("[3/3] 전송+저장…")
    results["transfer_and_save"] = measure_transfer_and_save()

    print("\n--- 예산표 ---")
    all_pass = True
    for key, budget in BUDGETS.items():
        val = results.get(key)
        if val is None:
            print(f"  {key}: 측정 실패 (예산 {budget}s)")
            all_pass = False
            continue
        ok = val < budget
        all_pass = all_pass and ok
        print(f"  {key}: {val:.3f}s / 예산 {budget}s — {'PASS' if ok else 'FAIL'}")

    print(f"\n전체: {'PASS' if all_pass else 'FAIL'}")
    print(json.dumps(results, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
