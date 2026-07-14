"""버스 오토메이션 전송(S3b, US-V2-014) 테스트."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import MIXER_ENTRY, SongContainer, load_model
from engine.songcore.mixer_parser import parse_mixer
from engine.songcore.song_parser import SONG_XML_ENTRY, parse_tracks
from engine.songcore.transfer import transfer_subtree
from engine.songcore.uid_refs import errors_of, validate

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


def test_src_sbus_has_automation_track_ground_truth(src):
    """실측 확인 — naiite_14의 S.BUS는 AutomationTrack을 가진다(볼륨/팬)."""
    xml = src.read_text(SONG_XML_ENTRY)
    assert re.search(r'<AutomationTrack[^>]*name="S\.BUS"', xml)


def test_dst_has_no_sbus_automation_before_transfer(dst):
    xml = dst.read_text(SONG_XML_ENTRY)
    assert 'name="S.BUS"' not in xml or not re.search(
        r'<AutomationTrack[^>]*name="S\.BUS"', xml)


def test_transfer_drum_subtree_carries_sbus_automation(src, src_model, dst):
    dr_bus_uid = src_model.by_label("DR.B").uid
    result = transfer_subtree(src, src_model, dr_bus_uid, dst)

    new_sbus_uid = result.new_channel_uids[src_model.by_label("S.BUS").uid]
    dst_song_xml = dst.read_text(SONG_XML_ENTRY)

    # 1) 새 AutomationTrack이 삽입됨
    automation_blocks = re.findall(r"<AutomationTrack\b.*?</AutomationTrack>",
                                   dst_song_xml, re.S)
    matching = [b for b in automation_blocks if new_sbus_uid in b]
    assert len(matching) == 1, "S.BUS 오토메이션 트랙이 정확히 1개 전송되어야 함"

    # 2) identity가 새 채널 UID를 정확히 가리킴 (구 UID 잔존 없음)
    old_sbus_uid = src_model.by_label("S.BUS").uid
    assert old_sbus_uid not in matching[0]
    assert f"param:///AudioMixer/{new_sbus_uid}/" in matching[0]

    # 3) trackID는 신규 생성(원본과 다름) + 전역 유일
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    new_container_model = load_model(dst)
    tracks = parse_tracks(dst)
    ids = tracks.all_track_ids()
    assert len(ids) == len(set(ids))

    # 4) fail-closed 재검증: dangling 0
    errs = errors_of(validate(dst, new_container_model))
    assert errs == []

    # 5) Envelopes 파일도 함께 복사됨 (기존 3f 로직 재사용 확인)
    assert any(n.startswith("Envelopes/S.BUS/") for n in result.copied_entries)


def test_transfer_bus_without_automation_adds_no_automation_track(src, src_model, dst):
    """오토메이션 없는 버스(K.BUS 단독)만 전송하면 AutomationTrack이 추가되지 않는다."""
    kbus_uid = src_model.by_label("K.BUS").uid
    dst_song_xml_before = dst.read_text(SONG_XML_ENTRY)
    before_count = len(re.findall(r"<AutomationTrack\b", dst_song_xml_before))

    transfer_subtree(src, src_model, kbus_uid, dst)

    dst_song_xml_after = dst.read_text(SONG_XML_ENTRY)
    after_count = len(re.findall(r"<AutomationTrack\b", dst_song_xml_after))
    assert after_count == before_count
