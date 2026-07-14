"""introspect 인벤토리/해석 서비스 테스트 (US-023, US-024).

주의: 실제 플러그인 로드(서브프로세스)를 포함 — 수 초 소요.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.introspect import InterpretService, Inventory
from engine.songcore import SongContainer, load_model

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")


@pytest.fixture(scope="module")
def inventory():
    inv = Inventory()
    inv.load()
    return inv


def test_resolve_standalone_vst3(inventory):
    r = inventory.resolve("Pro-Q 3")
    assert r is not None and r.subname is None
    assert "Pro-Q 3" in r.path


def test_resolve_waveshell_subplugin(inventory):
    r = inventory.resolve("CLA-76 Stereo")
    assert r is not None
    assert r.subname is not None and r.subname.startswith("CLA-76")
    assert "WaveShell" in r.path


def test_resolve_naiite_insert_classnames(inventory):
    model = load_model(SongContainer.read(NAIITE))
    names = {i.plugin_name for ch in model.channels for i in ch.inserts}
    unresolved = {n for n in names if inventory.resolve(n) is None}
    # S0.2 등급표에서 바이너리 미발견은 De Esser뿐 (EQP-1A는 naiite_14에 없음)
    assert unresolved <= {"De Esser"}, f"미해석: {unresolved}"


def test_interpret_proq3_end_to_end():
    svc = InterpretService()
    model = load_model(SongContainer.read(NAIITE))
    kbus = model.by_label("K.BUS")
    ins = kbus.inserts[0]
    assert ins.plugin_name == "Pro-Q 3"
    out = svc.interpret(NAIITE, ins.preset_path, ins.plugin_name)
    assert out["status"] == "ok", out.get("message")
    assert out["params"], "파라미터가 비어 있음"
    names = {p["name"] for p in out["params"]}
    assert any("Band 1" in n for n in names)
    # 캐시 적중 (2회째는 즉시)
    out2 = svc.interpret(NAIITE, ins.preset_path, ins.plugin_name)
    assert out2 == out


def test_prewarm_batch_proq3():
    """배치 프리웜: 플러그인 1회 로드로 여러 프리셋 캐시 → interpret 즉시 응답."""
    from engine.introspect.service import CACHE_DIR, _cache_key

    svc = InterpretService()
    container = SongContainer.read(NAIITE)
    model = load_model(container)
    targets = []
    for label in ("K.BUS", "DR.B"):
        ins = model.by_label(label).inserts[0]
        assert ins.plugin_name == "Pro-Q 3"
        targets.append((ins.preset_path, ins.plugin_name))

    # 캐시 강제 초기화 → 배치 경로 실행 보장
    res = svc.inventory.resolve("Pro-Q 3")
    for entry, _name in targets:
        key = _cache_key(container.read_entry(entry), res)
        (CACHE_DIR / f"{key}.json").unlink(missing_ok=True)

    stats = svc.prewarm(NAIITE, targets)
    assert stats["warmed"] == 2, stats

    # 캐시 적중으로 즉시 해석 + 내용 유효
    out = svc.interpret(NAIITE, targets[0][0], "Pro-Q 3")
    assert out["status"] == "ok" and out["params"]


def test_interpret_unknown_plugin_degrades():
    svc = InterpretService()
    model = load_model(SongContainer.read(NAIITE))
    kbus = model.by_label("K.BUS")
    out = svc.interpret(NAIITE, kbus.inserts[0].preset_path, "존재하지않는플러그인XYZ")
    assert out["status"] == "uninterpretable"
    assert "복사" in out["message"]
