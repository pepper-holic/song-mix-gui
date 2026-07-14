"""트랙 채널 전송(S4b/S4d, US-V2-017/018) 테스트."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import MIXER_ENTRY, SongContainer, load_model
from engine.songcore.mixer_parser import parse_mixer
from engine.songcore.song_parser import SONG_XML_ENTRY, parse_tracks
from engine.songcore.transfer import (TransferError, TransferResult,
                                      _copy_clip_to_mediapool, transfer_track)
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


def kick_out_uid(src_model):
    return src_model.by_label("kick out").uid


def test_transfer_track_empty_default(src, src_model, dst):
    before_numbers = [t.track_number for t in parse_tracks(dst).media_tracks]
    max_before = max(before_numbers, default=0)

    result = transfer_track(src, src_model, kick_out_uid(src_model), dst)

    new_uid = result.new_channel_uids[kick_out_uid(src_model)]
    new_model = parse_mixer(dst.read_text(MIXER_ENTRY))
    new_ch = new_model.by_uid()[new_uid]
    assert new_ch.tag == "AudioTrackChannel"
    assert new_ch.label == "kick out"

    tracks = parse_tracks(dst)
    new_tracks = [t for t in tracks.media_tracks if t.channel_id == new_uid]
    assert len(new_tracks) == 1
    assert new_tracks[0].track_number == max_before + 1

    # 기본 모드 = 빈 트랙: Events 없음
    song_xml = dst.read_text(SONG_XML_ENTRY)
    block = next(m.group(0) for m in re.finditer(r"<MediaTrack\b.*?</MediaTrack>",
                                                  song_xml, re.S)
                 if new_uid in m.group(0))
    assert '<List x:id="Events">' not in block

    # fail-closed 재검증
    container_model = load_model(dst)
    assert errors_of(validate(dst, container_model)) == []


def test_transfer_track_with_events(src, src_model, dst):
    result = transfer_track(src, src_model, kick_out_uid(src_model), dst,
                            include_events=True)
    new_uid = result.new_channel_uids[kick_out_uid(src_model)]
    song_xml = dst.read_text(SONG_XML_ENTRY)
    block = next(m.group(0) for m in re.finditer(r"<MediaTrack\b.*?</MediaTrack>",
                                                  song_xml, re.S)
                 if new_uid in m.group(0))
    assert "<AudioEvent" in block

    container_model = load_model(dst)
    assert errors_of(validate(dst, container_model)) == []


def test_transfer_track_with_events_copies_mediapool_clip_and_warns_external_path(
        src, src_model, dst):
    """이벤트 클립이 mediapool에 이식되고, 경로가 대상 폴더 밖이면 경고가 기록된다
    (실측: naiite_14의 클립 경로는 tmp dst 폴더 밖 — 07 스파이크와 동일 현상)."""
    clip_id = "{748F275E-7028-4A9F-9088-46DC17B234E4}"  # kick out.wav
    result = transfer_track(src, src_model, kick_out_uid(src_model), dst,
                            include_events=True)

    dst_mp = dst.read_text("Song/mediapool.xml")
    assert clip_id in dst_mp
    assert any("경고" in n and "미디어 경로" in n for n in result.notes)


def test_transfer_track_reuses_existing_mediapool_clip_bumps_usecount(src, src_model, dst):
    """대상에 동일 clipID가 이미 있으면 새 AudioClip을 추가하지 않고 useCount만 증가."""
    clip_id = "{748F275E-7028-4A9F-9088-46DC17B234E4}"
    transfer_track(src, src_model, kick_out_uid(src_model), dst, include_events=True)
    dst_mp_after_first = dst.read_text("Song/mediapool.xml")
    count_after_first = dst_mp_after_first.count(f'mediaID="{clip_id}"')
    assert count_after_first == 1

    # 두 번째 전송은 채널명 충돌로 막히므로, useCount 재사용 경로만 직접 검증
    src_mp = src.read_text("Song/mediapool.xml")
    updated = _copy_clip_to_mediapool(src_mp, dst_mp_after_first, clip_id,
                                      dst.source_path, result=TransferResult())
    assert updated.count(f'mediaID="{clip_id}"') == 1
    assert f'mediaID="{clip_id}" useCount="2"' in updated


def test_transfer_track_no_input_routing_bleed(src, src_model, dst):
    """RecordUnit(입력 라우팅)은 소스 전용 하드웨어 참조라 전송하지 않는다."""
    result = transfer_track(src, src_model, kick_out_uid(src_model), dst)
    new_uid = result.new_channel_uids[kick_out_uid(src_model)]
    mixer = dst.read_text(MIXER_ENTRY)
    block = next(m.group(0) for m in
                 re.finditer(r"<AudioTrackChannel\b.*?</AudioTrackChannel>", mixer, re.S)
                 if f'uid="{new_uid}"' in m.group(0))
    assert "recordPort" not in block


def test_transfer_track_conflict_on_duplicate_label(src, src_model, dst):
    transfer_track(src, src_model, kick_out_uid(src_model), dst)
    with pytest.raises(TransferError):
        transfer_track(src, src_model, kick_out_uid(src_model), dst)


def test_transfer_track_rejects_non_track_channel(src, src_model, dst):
    kbus_uid = src_model.by_label("K.BUS").uid  # 버스 채널 — 트랙 채널 아님
    with pytest.raises(TransferError):
        transfer_track(src, src_model, kbus_uid, dst)


def test_transfer_track_corpus_regression_track_numbers_unique(src, src_model, dst):
    """전송 후 trackNumber/trackID 전역 유일성이 유지된다 (S4 fail-closed 확장 재확인)."""
    transfer_track(src, src_model, kick_out_uid(src_model), dst)
    tracks = parse_tracks(dst)
    ids = tracks.all_track_ids()
    assert len(ids) == len(set(ids))
    numbers = [t.track_number for t in tracks.media_tracks]
    assert len(numbers) == len(set(numbers))
