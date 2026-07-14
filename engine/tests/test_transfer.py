"""uid_refs 스캐너(US-012) + transfer 엔진(US-013) 테스트."""
import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import MIXER_ENTRY, SongContainer, load_model
from engine.songcore.mixer_parser import parse_mixer
from engine.songcore.topology import build_graph
from engine.songcore.transfer import (TransferError, replace_insert_chain,
                                      subtree_transfer_set, transfer_subtree)
from engine.songcore.uid_refs import errors_of, scan_references, validate

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")
DST_SONG = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_HWA_SPLIT/sp_hwa_14/sp_hwa_14 (fixed).song")


@pytest.fixture(scope="module")
def src():
    return SongContainer.read(NAIITE)


@pytest.fixture(scope="module")
def src_model(src):
    return load_model(src)


@pytest.fixture()
def dst(tmp_path):
    copy = tmp_path / "dst.song"
    copy.write_bytes(DST_SONG.read_bytes())
    return SongContainer.read(copy)


# ---- US-012 uid_refs ----

def test_scan_finds_known_kbus_locations(src, src_model):
    kbus = src_model.by_label("K.BUS")
    refs = scan_references(src, kbus.uid)
    entries = {r.entry for r in refs}
    assert {"Devices/audiomixer.xml", "Devices/mixerconsole.xml",
            "notepad.xml"} <= entries
    forms = {r.form for r in refs}
    assert 'Section path="HEX32"' in forms  # 대시 없는 형태도 검출


def test_validate_pristine_no_errors(src, src_model):
    assert errors_of(validate(src, src_model)) == []


def test_validate_detects_dangling_route(src):
    mixer = src.read_text(MIXER_ENTRY)
    broken = mixer.replace(
        'objectID="{9F3D103A-DB25-4F36-A270-E810C3AE5D47}/Input"',
        'objectID="{00000000-0000-0000-0000-000000000000}/Input"')
    model = parse_mixer(broken)
    c = SongContainer.read(NAIITE)
    c.replace_text(MIXER_ENTRY, broken)
    errs = errors_of(validate(c, model))
    assert any(p.code == "dangling-route" for p in errs)


def test_validate_detects_missing_preset(src):
    mixer = src.read_text(MIXER_ENTRY)
    broken = mixer.replace(
        "Presets/Channels/K.BUS/1 - Pro-Q 3 K.B.vstpreset",
        "Presets/Channels/K.BUS/1 - NOPE.vstpreset")
    c = SongContainer.read(NAIITE)
    c.replace_text(MIXER_ENTRY, broken)
    errs = errors_of(validate(c, parse_mixer(broken)))
    assert any(p.code == "missing-preset" for p in errs)


# ---- US-013 transfer ----

def drum_root_uid(src_model):
    return src_model.by_label("DR.B").uid


def test_subtree_set_is_five_buses(src_model):
    uids = subtree_transfer_set(src_model, drum_root_uid(src_model))
    labels = {src_model.by_uid()[u].label for u in uids}
    assert labels == {"K.BUS", "S.BUS", "T.BUS", "CYM.BUS", "DR.B"}


def test_transfer_drum_subtree(src, src_model, dst):
    result = transfer_subtree(src, src_model, drum_root_uid(src_model), dst)
    assert len(result.new_channel_uids) == 5
    # 재파싱 그래프 동등성
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    graph = build_graph(new_model)
    drb = new_model.by_label("DR.B")
    children = {new_model.by_uid()[u].label for u in graph.children_of(drb.uid)}
    assert children == {"K.BUS", "S.BUS", "T.BUS", "CYM.BUS"}
    # root 접합: 대상엔 MIXOUT이 없으므로 메인으로
    assert drb.destination_name == "메인"
    # 인서트 체인 보존 + preset 실재
    kbus = new_model.by_label("K.BUS")
    assert [i.plugin_name for i in kbus.inserts] == \
        ["Pro-Q 3", "SPL Transient Designer Plus", "CLA-76 Stereo", "JST Clip"]
    names = set(dst.names())
    for ch_label in ("K.BUS", "S.BUS", "T.BUS", "CYM.BUS", "DR.B"):
        ch = new_model.by_label(ch_label)
        for ins in ch.inserts:
            assert ins.preset_path in names
    # 외부 send(DR.B→DR Parallel)는 제거 기록
    assert any("DR Parallel" in s for s in result.dropped_sends)
    # 무결성: dangling 0
    assert errors_of(validate(dst, new_model)) == []


# ---- US-V2-016 S2: 외부 send 보존 옵션 ----

def test_transfer_preserves_external_send_when_same_label_exists(src, src_model, dst):
    """preserve_external_sends=True + 대상에 동명 채널("DR Parallel") 존재 → send 유지+재배선."""
    dst_before = parse_mixer(dst.read_text(MIXER_ENTRY))
    dr_parallel_uid = dst_before.by_label("DR Parallel").uid

    result = transfer_subtree(src, src_model, drum_root_uid(src_model), dst,
                              preserve_external_sends=True)

    assert result.dropped_sends == []
    assert any("DR Parallel" in n for n in result.notes)
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    drb = new_model.by_label("DR.B")
    assert any(s.destination_uid == dr_parallel_uid for s in drb.sends)
    assert errors_of(validate(dst, new_model)) == []


def test_transfer_drops_external_send_without_matching_label(src, src_model, dst):
    """preserve_external_sends=True여도 대상에 동명 채널이 없으면 기존대로 제거+기록."""
    # DR Parallel 채널의 표시 라벨을 바꿔 "동명 없음" 상태를 만든다
    dst_mixer = dst.read_text(MIXER_ENTRY)
    dst.replace_text(MIXER_ENTRY, dst_mixer.replace(
        'label="DR Parallel"', 'label="DR Parallel Renamed"'))

    result = transfer_subtree(src, src_model, drum_root_uid(src_model), dst,
                              preserve_external_sends=True)

    assert any("DR Parallel" in s for s in result.dropped_sends)
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert errors_of(validate(dst, new_model)) == []


def test_transfer_result_roundtrips(src, src_model, dst, tmp_path):
    transfer_subtree(src, src_model, drum_root_uid(src_model), dst)
    out = tmp_path / "out.song"
    dst.write_to(out)
    reread = SongContainer.read(out)
    model = load_model(reread)
    assert model.by_label("DR.B") is not None
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
    # UID 유일성 전역 확인
    uids = [c.uid for c in model.channels]
    assert len(uids) == len(set(uids))


def test_transfer_conflict_requires_confirmation(src, src_model, dst):
    transfer_subtree(src, src_model, drum_root_uid(src_model), dst)
    # 같은 서브트리를 한 번 더 → 라벨 충돌 → 미승인 시 거부
    model2 = parse_mixer(src.read_text(MIXER_ENTRY))
    with pytest.raises(TransferError, match="충돌"):
        transfer_subtree(src, model2, drum_root_uid(model2), dst)


def test_transfer_overwrite_replaces(src, src_model, dst):
    transfer_subtree(src, src_model, drum_root_uid(src_model), dst)
    before = parse_mixer(dst.read_text(MIXER_ENTRY))
    n_before = len(before.channels)
    result = transfer_subtree(src, src_model, drum_root_uid(src_model), dst,
                              overwrite_confirmed=True)
    after = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert len(after.channels) == n_before  # 교체이지 증식이 아님
    assert sorted(result.replaced_labels) == \
        ["CYM.BUS", "DR.B", "K.BUS", "S.BUS", "T.BUS"]
    assert errors_of(validate(dst, after)) == []


def test_replace_insert_chain(src, src_model, dst):
    dst_model = load_model(dst)
    target = next(c for c in dst_model.channels if c.group == "AudioGroup")
    kbus = src_model.by_label("K.BUS")
    result = replace_insert_chain(src, src_model, kbus.uid, dst, target.uid)
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    new_target = new_model.by_uid()[target.uid]
    assert [i.plugin_name for i in new_target.inserts] == \
        [i.plugin_name for i in kbus.inserts]
    # presetPath가 대상 라벨 폴더로 이식되고 파일 실재
    names = set(dst.names())
    for ins in new_target.inserts:
        assert ins.preset_path.startswith(f"Presets/Channels/{target.label}/")
        assert ins.preset_path in names
    assert errors_of(validate(dst, new_model)) == []
