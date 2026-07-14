"""compare.py 체인 비교 서비스 테스트 — v2 U4(AC-4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.introspect.compare import ParamDiff, compare_chains
from engine.songcore.mixer_parser import Insert


def _insert(chain_index: int, plugin_name: str, preset_path: str | None = None) -> Insert:
    return Insert(
        slot_name=f"FX{chain_index:02d}", chain_index=chain_index,
        uid=f"{{INS-{chain_index}}}", class_id="cls", device_name=plugin_name,
        plugin_name=plugin_name, sub_category="EQ", preset_path=preset_path,
    )


def _ok(params: dict[str, str]) -> dict:
    return {"status": "ok", "pluginName": "x",
            "params": [{"name": k, "value": v} for k, v in params.items()]}


def test_same_plugin_same_values_is_match():
    left = [_insert(0, "Pro-Q 3", "a.vstpreset")]
    right = [_insert(0, "Pro-Q 3", "b.vstpreset")]
    lookup = {"a.vstpreset": _ok({"gain": "1.0"}), "b.vstpreset": _ok({"gain": "1.0"})}
    rows = compare_chains(left, right, lambda ins: lookup.get(ins.preset_path))
    assert len(rows) == 1
    assert rows[0].row_type == "match"
    assert rows[0].interpretable is True
    assert rows[0].diffs == ()


def test_same_plugin_different_values_is_value_diff():
    left = [_insert(0, "Pro-Q 3", "a.vstpreset")]
    right = [_insert(0, "Pro-Q 3", "b.vstpreset")]
    lookup = {"a.vstpreset": _ok({"gain": "1.0"}), "b.vstpreset": _ok({"gain": "2.0"})}
    rows = compare_chains(left, right, lambda ins: lookup.get(ins.preset_path))
    assert rows[0].row_type == "value-diff"
    assert rows[0].diffs == (ParamDiff("gain", "1.0", "2.0"),)


def test_different_plugin_is_chain_mismatch():
    left = [_insert(0, "Pro-Q 3")]
    right = [_insert(0, "CLA-76")]
    rows = compare_chains(left, right, lambda ins: None)
    assert rows[0].row_type == "chain-mismatch"
    assert rows[0].left_plugin == "Pro-Q 3"
    assert rows[0].right_plugin == "CLA-76"
    assert rows[0].interpretable is False


def test_missing_slot_on_one_side_is_chain_mismatch():
    left = [_insert(0, "Pro-Q 3"), _insert(1, "CLA-76")]
    right = [_insert(0, "Pro-Q 3")]
    rows = compare_chains(left, right, lambda ins: None)
    assert len(rows) == 2
    assert rows[1].row_type == "chain-mismatch"
    assert rows[1].left_plugin == "CLA-76"
    assert rows[1].right_plugin is None


def test_uninterpretable_plugin_falls_back_to_structural_match():
    left = [_insert(0, "EQP-1A", "a.vstpreset")]
    right = [_insert(0, "EQP-1A", "b.vstpreset")]
    rows = compare_chains(left, right, lambda ins: None)  # 둘 다 미해석
    assert rows[0].row_type == "match"
    assert rows[0].interpretable is False
    assert rows[0].diffs == ()


def test_one_side_uninterpretable_falls_back():
    left = [_insert(0, "Pro-Q 3", "a.vstpreset")]
    right = [_insert(0, "Pro-Q 3", "b.vstpreset")]
    lookup = {"a.vstpreset": _ok({"gain": "1.0"})}  # b는 미해석
    rows = compare_chains(left, right, lambda ins: lookup.get(ins.preset_path))
    assert rows[0].row_type == "match"
    assert rows[0].interpretable is False
