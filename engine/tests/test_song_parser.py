"""song_parser.py (읽기 전용 트랙 파서) 테스트 — v2 US-V2-013."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import SongContainer
from engine.songcore.song_parser import parse_tracks

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")
SONGS_DIR = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")
ALL_SONGS = sorted(SONGS_DIR.rglob("*.song"))

_UID_RE_BODY = r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"


def _looks_like_braced_uid(s: str) -> bool:
    import re
    return bool(re.fullmatch(r"\{" + _UID_RE_BODY + r"\}", s))


@pytest.fixture(scope="module")
def naiite():
    return SongContainer.read(NAIITE)


def test_naiite_media_tracks_extracted(naiite):
    model = parse_tracks(naiite)
    assert len(model.media_tracks) == 19  # 실측: trackNumber 1~19
    numbers = sorted(t.track_number for t in model.media_tracks)
    assert numbers == list(range(1, 20))
    first = next(t for t in model.media_tracks if t.name == "kick out")
    assert first.channel_id == "{A4F85CCD-6C62-4145-9187-03C58A2B71B5}"


def test_naiite_automation_tracks_extracted(naiite):
    model = parse_tracks(naiite)
    names = {t.name for t in model.automation_tracks}
    assert "S.BUS" in names
    sbus = next(t for t in model.automation_tracks if t.name == "S.BUS")
    assert sbus.track_id == "{9E216095-0354-420F-A52D-9801EA3592DD}"


def test_all_track_ids_globally_unique(naiite):
    model = parse_tracks(naiite)
    ids = model.all_track_ids()
    assert len(ids) == len(set(ids))


def test_track_number_no_duplicates(naiite):
    model = parse_tracks(naiite)
    numbers = [t.track_number for t in model.media_tracks]
    assert len(numbers) == len(set(numbers))


@pytest.mark.parametrize("song", ALL_SONGS, ids=lambda p: p.stem[:40])
def test_corpus_parse_no_false_positive(song):
    """원본 코퍼스 전체 파싱 무오탐: 크래시 없음, trackID/channelID는 braced UID
    형태, trackID 전역 유일, trackNumber 중복 없음."""
    container = SongContainer.read(song)
    model = parse_tracks(container)
    ids = model.all_track_ids()
    assert len(ids) == len(set(ids))
    for tid in ids:
        assert _looks_like_braced_uid(tid), f"{song}: 비정상 trackID 형식 {tid!r}"
    for mt in model.media_tracks:
        if mt.channel_id is not None:
            assert _looks_like_braced_uid(mt.channel_id), \
                f"{song}: 비정상 channelID 형식 {mt.channel_id!r}"
    numbers = [t.track_number for t in model.media_tracks]
    assert len(numbers) == len(set(numbers)), f"{song}: trackNumber 중복"
