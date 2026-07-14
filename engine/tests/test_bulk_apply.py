"""bulk_apply(US-V3-001): 한 곡의 믹스 세팅을 여러 곡에 라벨 매칭 기준으로 일괄 적용.

라벨은 곡마다 표기가 다를 수 있어("kick" vs "1 - kick") 정확 일치만 인정하고,
불일치는 사전에 "no-match"로 보고해 사용자가 확인하도록 한다(자동 유사매칭 금지).
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import MIXER_ENTRY, SongContainer, load_model
from engine.songcore.bulk_apply import (ChannelPlan, apply_recipe,
                                        apply_recipe_to_songs, bus_channel_tree,
                                        find_bus_roots, plan_recipe)
from engine.songcore.mixer_parser import Channel, MixerModel, parse_mixer
from engine.songcore.transfer import TransferError
from engine.songcore.uid_refs import errors_of, validate

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")
DST_SONG = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_HWA_SPLIT/sp_hwa_14/sp_hwa_14 (fixed).song")


def _ch(tag, label, uid, dest_uid=None, group="G"):
    return Channel(tag=tag, group=group, name="Channel01", label=label, uid=uid,
                   speaker_type=None, destination_uid=dest_uid, destination_name=None)


# ---- 순수 계획 로직 (hand-built model) ----

def test_find_bus_roots_returns_only_top_level():
    model = MixerModel(channels=[
        _ch("AudioGroupChannel", "K.BUS", "{K}", dest_uid="{DRB}"),
        _ch("AudioGroupChannel", "DR.B", "{DRB}", dest_uid="{MIX}"),
        _ch("AudioGroupChannel", "GT.B", "{GT}", dest_uid="{MIX}"),
        _ch("AudioOutputChannel", "MIXOUT", "{MIX}", dest_uid=None),
        _ch("AudioTrackChannel", "kick", "{TRK}", dest_uid="{K}"),
    ])
    roots = find_bus_roots(model)
    assert {c.label for c in roots} == {"DR.B", "GT.B"}


def test_bus_channel_tree_exposes_nested_buses_with_depth():
    model = MixerModel(channels=[
        _ch("AudioGroupChannel", "K.BUS", "{K}", dest_uid="{DRB}"),
        _ch("AudioGroupChannel", "DR.B", "{DRB}", dest_uid="{MIX}"),
        _ch("AudioGroupChannel", "GT.B", "{GT}", dest_uid="{MIX}"),
        _ch("AudioOutputChannel", "MIXOUT", "{MIX}", dest_uid=None),
        _ch("AudioTrackChannel", "kick", "{TRK}", dest_uid="{K}"),
    ])
    tree = bus_channel_tree(model)
    by_label = {ch.label: depth for ch, depth, _ in tree}
    # 최상위 루트(DR.B, GT.B)는 depth 0, DR.B 아래 중첩된 K.BUS는 depth 1로 노출되어야
    # find_bus_roots만으로는 숨겨졌던 중첩 버스도 "직접 선택" UI에서 고를 수 있다.
    assert by_label == {"DR.B": 0, "GT.B": 0, "K.BUS": 1}
    # DFS(부모 먼저) 순서: K.BUS는 부모 DR.B 바로 다음, 다른 루트 GT.B보다 앞에 나와야 한다.
    labels_in_order = [ch.label for ch, _, _ in tree]
    assert labels_in_order == ["DR.B", "K.BUS", "GT.B"]
    # 부모 라벨: 최상위는 None, K.BUS의 부모는 DR.B — 프론트가 상위 체크 시 하위를
    # 자동으로 "포함됨" 처리하려면 이 관계가 필요하다.
    parent_by_label = {ch.label: parent for ch, _, parent in tree}
    assert parent_by_label == {"DR.B": None, "GT.B": None, "K.BUS": "DR.B"}


def test_plan_recipe_categorizes_bus_chain_exclude_and_nomatch():
    src = MixerModel(channels=[
        _ch("AudioGroupChannel", "DR.B", "{DRB}", dest_uid="{MIX_S}"),
        _ch("AudioOutputChannel", "MIXOUT", "{MIX_S}"),
        _ch("AudioTrackChannel", "kick", "{KICK_S}", dest_uid="{DRB}"),
        _ch("AudioTrackChannel", "SN T", "{SNT_S}", dest_uid="{DRB}"),
        _ch("AudioTrackChannel", "extra_track", "{EXTRA_S}", dest_uid="{DRB}"),
    ])
    dst = MixerModel(channels=[
        _ch("AudioGroupChannel", "DR.B", "{DRB_D}", dest_uid="{MIX_D}"),
        _ch("AudioOutputChannel", "MIXOUT", "{MIX_D}"),
        _ch("AudioTrackChannel", "kick", "{KICK_D}", dest_uid="{DRB_D}"),
        _ch("AudioTrackChannel", "SN T", "{SNT_D}", dest_uid="{DRB_D}"),
    ])
    plans = plan_recipe(src, dst, exclude_labels={"SN T"})
    by_label = {p.label: p for p in plans}
    assert by_label["DR.B"] == ChannelPlan("DR.B", "bus-subtree", "{DRB}")
    assert by_label["kick"] == ChannelPlan("kick", "chain-replace", "{KICK_S}", "{KICK_D}")
    assert by_label["SN T"] == ChannelPlan("SN T", "excluded", "{SNT_S}")
    assert by_label["extra_track"] == ChannelPlan("extra_track", "no-match", "{EXTRA_S}")


# ---- 실제 코퍼스 통합 테스트 ----

@pytest.fixture(scope="module")
def src():
    return SongContainer.read(NAIITE)


@pytest.fixture(scope="module")
def src_model(src):
    return load_model(src)


def _dst_with_kick_relabeled(tmp_path, name="dst.song"):
    """DST_SONG 사본에서 '1 - kick' 라벨만 소스와 동일한 'kick'으로 맞춰
    최소 하나의 트랙 채널 매칭을 실증 가능하게 한다(원본 라벨 표기가 서로 달라서).

    DST_SONG에는 AudioEffect 채널그룹(FX 버스 컨테이너)이 아예 없어(이 곡엔 FX
    버스가 없음) 소스의 "FX 1" 버스를 실을 자리가 없다 — 빈 그룹을 주입해 실제
    "FX 버스가 있는 곡 → 있는 곡" 상황을 재현한다.
    """
    copy = tmp_path / name
    copy.write_bytes(DST_SONG.read_bytes())
    c = SongContainer.read(copy)
    mixer = c.read_text(MIXER_ENTRY)
    assert mixer.count('label="1 - kick"') == 1
    mixer = mixer.replace('label="1 - kick"', 'label="kick"', 1)
    anchor = '</Attributes>\r\n\t<Attributes x:id="ListenBusManager"'
    assert anchor in mixer and '<ChannelGroup name="AudioEffect"' not in mixer
    mixer = mixer.replace(
        anchor, '\t\t<ChannelGroup name="AudioEffect" flags="1">\r\n\t\t</ChannelGroup>\r\n'
        + anchor, 1)
    c.replace_text(MIXER_ENTRY, mixer)
    c.write_to(copy)  # 배치 테스트가 경로만 받아 재오픈하므로 디스크에도 반영
    return SongContainer.read(copy)


@pytest.fixture()
def dst(tmp_path):
    return _dst_with_kick_relabeled(tmp_path)


def test_apply_recipe_transfers_bus_subtree_and_matched_chain(src, src_model, dst):
    result = apply_recipe(src, src_model, dst, exclude_labels=set())
    by_label = {p.label: p for p in result.plans}
    assert by_label["kick"].action == "chain-replace"
    # MIXOUT은 실제 종단 마스터버스라 유일한 최상위 루트 — DR.B/GT.B/BASS.B/FX 1 등
    # 하위 버스/병렬 구조 전체를 한 번의 서브트리 전송으로 데려온다.
    assert by_label["MIXOUT"].action == "bus-subtree"

    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    kick = new_model.by_label("kick")
    assert [i.plugin_name for i in kick.inserts] == ["Pro-Q 3"]
    drb = new_model.by_label("DR.B")
    assert drb is not None and drb.destination_name == "MIXOUT"
    fx1 = new_model.by_label("FX 1")
    assert fx1 is not None
    assert errors_of(validate(dst, new_model)) == []


def test_apply_recipe_excludes_labels_from_chain_replace(src, src_model, dst):
    dst_model_before = parse_mixer(dst.read_text(MIXER_ENTRY))
    kick_before = dst_model_before.by_label("kick").inserts

    result = apply_recipe(src, src_model, dst, exclude_labels={"kick"})
    by_label = {p.label: p for p in result.plans}
    assert by_label["kick"].action == "excluded"

    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert new_model.by_label("kick").inserts == kick_before  # 미변경


def test_apply_recipe_reports_unmatched_labels(src, src_model, dst):
    result = apply_recipe(src, src_model, dst, exclude_labels=set())
    by_label = {p.label: p for p in result.plans}
    # "SN T"는 dst에 "1 - SN T"로만 존재 — 정확 일치 실패 → no-match
    assert by_label["SN T"].action == "no-match"


# ---- 배치(여러 dst 파일) ----

def test_apply_recipe_to_songs_batch_isolates_failures(tmp_path, src_model):
    ok_dst = _dst_with_kick_relabeled(tmp_path, "ok.song").source_path
    missing_dst = tmp_path / "does_not_exist.song"

    outcomes = apply_recipe_to_songs(NAIITE, [ok_dst, missing_dst], exclude_labels=set())

    assert outcomes[ok_dst].ok is True
    assert outcomes[ok_dst].backup_path is not None
    assert outcomes[missing_dst].ok is False
    assert outcomes[missing_dst].error


def _dst_with_broken_kick_inserts(tmp_path, name="broken.song"):
    """kick 채널의 Inserts 블록 x:id를 깨서 chain-replace 단계에서 확실히
    TransferError가 나도록 만든다 — 버스 서브트리(선행 단계)는 정상 성공한 뒤
    후행 단계에서 실패하는 상황을 재현해 fail-closed를 실제로 검증한다."""
    c = _dst_with_kick_relabeled(tmp_path, name)
    mixer = c.read_text(MIXER_ENTRY)
    for m in re.finditer(r"<AudioTrackChannel\b.*?</AudioTrackChannel>", mixer, re.S):
        if 'label="kick"' in m.group(0):
            broken_block = m.group(0).replace(
                '<Attributes x:id="Inserts">', '<Attributes x:id="InsertsBroken">', 1)
            mixer = mixer[:m.start()] + broken_block + mixer[m.end():]
            break
    else:
        raise AssertionError("kick 채널 블록을 찾지 못함")
    c.replace_text(MIXER_ENTRY, mixer)
    c.write_to(c.source_path)
    return SongContainer.read(c.source_path)


def test_apply_recipe_to_songs_fails_closed_when_later_step_errors(tmp_path):
    """버스 서브트리 전송(선행)은 성공하지만 kick 체인교체(후행)가 실패하는 경우 —
    dst 실제 파일은 한 바이트도 바뀌면 안 되고 .bak도 생기면 안 된다."""
    broken_path = _dst_with_broken_kick_inserts(tmp_path).source_path
    before = broken_path.read_bytes()

    outcomes = apply_recipe_to_songs(NAIITE, [broken_path], exclude_labels=set())

    assert outcomes[broken_path].ok is False
    assert "Inserts" in outcomes[broken_path].error
    assert broken_path.read_bytes() == before
    assert not broken_path.with_suffix(".song.bak").exists()


def test_plan_recipe_rejects_duplicate_labels_in_destination():
    src = MixerModel(channels=[
        _ch("AudioTrackChannel", "kick", "{KICK_S}", dest_uid="{OUT_S}"),
    ])
    dst = MixerModel(channels=[
        _ch("AudioTrackChannel", "kick", "{KICK_D1}", dest_uid="{OUT_D}"),
        _ch("AudioTrackChannel", "kick", "{KICK_D2}", dest_uid="{OUT_D}"),
    ])
    with pytest.raises(ValueError, match="라벨 중복"):
        plan_recipe(src, dst, exclude_labels=set())


# ---- include_bus_labels: 버스 루트 선택적 적용 ----

def test_plan_recipe_include_bus_labels_filters_unselected_roots():
    src = MixerModel(channels=[
        _ch("AudioGroupChannel", "DR.B", "{DRB}", dest_uid="{MIX_S}"),
        _ch("AudioGroupChannel", "GT.B", "{GTB}", dest_uid="{MIX_S}"),
        _ch("AudioOutputChannel", "MIXOUT", "{MIX_S}"),
    ])
    dst = MixerModel(channels=[_ch("AudioOutputChannel", "MIXOUT", "{MIX_D}")])

    plans = plan_recipe(src, dst, exclude_labels=set(), include_bus_labels={"DR.B"})
    by_label = {p.label: p for p in plans}
    assert by_label["DR.B"].action == "bus-subtree"
    assert by_label["GT.B"].action == "not-selected"


def test_plan_recipe_include_bus_labels_none_means_all(src_model):
    dst_model = MixerModel(channels=[_ch("AudioOutputChannel", "MIXOUT", "{MIX_D}")])
    plans = plan_recipe(src_model, dst_model, exclude_labels=set(), include_bus_labels=None)
    by_label = {p.label: p for p in plans}
    assert by_label["MIXOUT"].action == "bus-subtree"


def test_plan_recipe_include_bus_labels_accepts_nested_bus_directly(src_model, dst):
    """"DR.B"는 naiite_14의 최상위 루트가 아니다(유일한 최상위 루트는 "MIXOUT" —
    그 아래 DR.B/GT.B/BASS.B/FX 1 등이 전부 중첩돼 있음). 그래도 사용자가 명시
    지정하면 최상위 제한을 우회해 DR.B 자체를 서브트리 루트로 써야 한다."""
    assert "DR.B" not in {c.label for c in find_bus_roots(src_model)}
    dst_model = parse_mixer(dst.read_text(MIXER_ENTRY))

    plans = plan_recipe(src_model, dst_model, exclude_labels=set(),
                        include_bus_labels={"DR.B"})
    by_label = {p.label: p for p in plans}
    assert by_label["DR.B"].action == "bus-subtree"
    assert by_label["MIXOUT"].action == "not-selected"
    assert "GT.B" not in by_label  # 선택 안 된 비-루트 버스는 아예 계획에 안 나타남


def test_plan_recipe_include_bus_labels_reports_unknown_label(src_model, dst):
    dst_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    plans = plan_recipe(src_model, dst_model, exclude_labels=set(),
                        include_bus_labels={"이런버스없음"})
    by_label = {p.label: p for p in plans}
    assert by_label["이런버스없음"].action == "unknown-bus-label"


def test_plan_recipe_include_bus_labels_rejects_ancestor_descendant_overlap(src_model, dst):
    """"MIXOUT"(최상위)과 "DR.B"(그 서브트리 내부)를 동시에 지정하면 어느 쪽이
    최종 결과로 남을지 모호해지므로 조용히 하나를 고르지 않고 명시적으로 거부한다."""
    dst_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    with pytest.raises(ValueError, match="중첩"):
        plan_recipe(src_model, dst_model, exclude_labels=set(),
                   include_bus_labels={"MIXOUT", "DR.B"})


def test_plan_recipe_rejects_duplicate_bus_labels_in_source():
    src = MixerModel(channels=[
        _ch("AudioGroupChannel", "DUP", "{A}", dest_uid="{OUT}"),
        _ch("AudioGroupChannel", "DUP", "{B}", dest_uid="{OUT}"),
        _ch("AudioOutputChannel", "OUT", "{OUT}"),
    ])
    dst = MixerModel(channels=[_ch("AudioOutputChannel", "OUT", "{OUT_D}")])
    with pytest.raises(ValueError, match="라벨 중복"):
        plan_recipe(src, dst, exclude_labels=set(), include_bus_labels={"DUP"})


def test_apply_recipe_include_bus_labels_transfers_nested_bus_only(src, src_model, dst):
    """"DR.B"(최상위 루트가 아닌 중첩 버스)만 선택해도 실제로 그 서브트리(드럼버스
    +K/S/T/CYM.BUS)만 전송되고, 선택 안 한 GT.B/BASS.B/FX 1/MIXOUT은 전혀 생성되지
    않아야 한다 — transfer_subtree가 루트 위치에 무관하게 정상 동작함을 실제 적용
    경로(apply_recipe)로 검증."""
    result = apply_recipe(src, src_model, dst, exclude_labels=set(),
                          include_bus_labels={"DR.B"})
    by_label = {p.label: p for p in result.plans}
    assert by_label["DR.B"].action == "bus-subtree"
    assert by_label["MIXOUT"].action == "not-selected"

    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert new_model.by_label("DR.B") is not None
    assert new_model.by_label("K.BUS") is not None  # DR.B 서브트리에 중첩된 버스
    for untouched in ("GT.B", "BASS.B", "FX 1", "MIXOUT"):
        assert new_model.by_label(untouched) is None
    assert errors_of(validate(dst, new_model)) == []


def test_apply_recipe_include_bus_labels_skips_unselected_bus(src, src_model, dst):
    """MIXOUT 루트를 선택하지 않으면 버스/병렬 구조는 전혀 건드리지 않고
    트랙 채널 chain-replace만 수행되어야 한다."""
    result = apply_recipe(src, src_model, dst, exclude_labels=set(), include_bus_labels=set())
    by_label = {p.label: p for p in result.plans}
    assert by_label["MIXOUT"].action == "not-selected"
    assert by_label["kick"].action == "chain-replace"

    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert new_model.by_label("DR.B") is None  # 버스는 생성되지 않음
    assert new_model.by_label("kick").inserts[0].plugin_name == "Pro-Q 3"


# ---- exclude_labels가 버스 서브트리 내부까지는 못 거르는 것을 경고 + 기본 차단으로 알림 ----

def test_apply_recipe_blocks_by_default_when_excluded_label_nested_in_bus_subtree(
        src, src_model, dst):
    """"FX 1"은 MIXOUT 서브트리 내부(최상위 루트가 아님) 라벨 — exclude해도 실제로는
    서브트리에 그대로 딸려간다. 사용자가 "제외했다"고 믿고 모르는 채 실제 전송되는
    사고를 막기 위해 기본값은 아무 것도 쓰지 않고 안전하게 거부해야 한다."""
    before = parse_mixer(dst.read_text(MIXER_ENTRY))

    with pytest.raises(TransferError, match="FX 1"):
        apply_recipe(src, src_model, dst, exclude_labels={"FX 1"})

    after = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert after == before  # 아무 전송도 시도되지 않음(메모리 상태도 미변경)


def test_apply_recipe_allows_nested_exclusion_warning_when_explicitly_overridden(
        src, src_model, dst):
    result = apply_recipe(src, src_model, dst, exclude_labels={"FX 1"},
                          allow_nested_exclusion_warnings=True)
    assert any("FX 1" in w for w in result.warnings)
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    assert new_model.by_label("FX 1") is not None  # 명시적으로 허용했으니 경고대로 전송됨


def test_apply_recipe_no_warning_when_exclude_label_is_top_level(src, src_model, dst):
    result = apply_recipe(src, src_model, dst, exclude_labels={"kick"})
    assert result.warnings == []


def test_apply_recipe_to_songs_dry_run_does_not_write(tmp_path):
    ok_dst = _dst_with_kick_relabeled(tmp_path, "dry.song").source_path
    before = ok_dst.read_bytes()

    outcomes = apply_recipe_to_songs(NAIITE, [ok_dst], exclude_labels=set(), dry_run=True)

    assert outcomes[ok_dst].ok is True
    assert outcomes[ok_dst].backup_path is None
    assert ok_dst.read_bytes() == before
    assert not ok_dst.with_suffix(".song.bak").exists()
