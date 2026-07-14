"""uid_refs.validate() v2 확장 3종(S3b) 테스트 — 트랙/오토메이션 구조 fail-closed 검사.

확장 코드: dangling-automation-identity, dangling-track-channel,
duplicate-track-id, duplicate-track-number.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import SongContainer, load_model
from engine.songcore.song_parser import parse_tracks
from engine.songcore.uid_refs import errors_of, validate

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")
SONGS_DIR = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")
ALL_SONGS = sorted(SONGS_DIR.rglob("*.song"))
V2_CODES = {"dangling-automation-identity", "dangling-track-channel",
            "duplicate-track-id", "duplicate-track-number"}


@pytest.fixture(scope="module")
def naiite():
    return SongContainer.read(NAIITE)


@pytest.fixture(scope="module")
def naiite_model(naiite):
    return load_model(naiite)


def test_naiite_pristine_no_v2_errors(naiite, naiite_model):
    codes = {p.code for p in validate(naiite, naiite_model) if p.severity == "error"}
    assert not (codes & V2_CODES)


def test_detects_dangling_automation_identity(naiite, naiite_model):
    """require_console_for(전송 산출물 UID)에 속한 대상만 error — 원본 코퍼스에
    스테일 오토메이션 참조가 실존하므로(naiite_20) 전송 산출물만 엄격 검사한다."""
    broken_uid = "{00000000-0000-0000-0000-000000000000}"
    song_xml = naiite.read_text("Song/song.xml")
    broken = song_xml.replace(
        'identity="param:///AudioMixer/{7AEF0C5E-EB34-4154-A665-BA83580E883D}/volume"',
        f'identity="param:///AudioMixer/{broken_uid}/volume"')
    assert broken != song_xml
    c = SongContainer.read(NAIITE)
    c.replace_text("Song/song.xml", broken)
    # require_console_for 없음 → 원본 코퍼스 예외와 동일하게 warning 취급(에러 아님)
    assert not any(p.code == "dangling-automation-identity"
                   for p in errors_of(validate(c, naiite_model)))
    # require_console_for에 포함되면(이 전송이 새로 만든 채널) error로 승격
    errs = errors_of(validate(c, naiite_model, require_console_for={broken_uid}))
    assert any(p.code == "dangling-automation-identity" for p in errs)


def test_detects_dangling_track_channel(naiite, naiite_model):
    """require_console_for에 속한 channelID만 error (S3b 시 문서화된 비대칭과 동일 원칙)."""
    broken_uid = "{00000000-0000-0000-0000-000000000000}"
    song_xml = naiite.read_text("Song/song.xml")
    broken = song_xml.replace(
        '<UID x:id="channelID" uid="{A4F85CCD-6C62-4145-9187-03C58A2B71B5}"/>',
        f'<UID x:id="channelID" uid="{broken_uid}"/>', 1)
    assert broken != song_xml
    c = SongContainer.read(NAIITE)
    c.replace_text("Song/song.xml", broken)
    assert not any(p.code == "dangling-track-channel"
                   for p in errors_of(validate(c, naiite_model)))
    errs = errors_of(validate(c, naiite_model, require_console_for={broken_uid}))
    assert any(p.code == "dangling-track-channel" for p in errs)


def test_detects_duplicate_track_id(naiite, naiite_model):
    song_xml = naiite.read_text("Song/song.xml")
    broken = song_xml.replace(
        'trackID="{063BB65D-BAD2-4B5A-B5F8-B4C66494F287}"',
        'trackID="{821EA896-7FE7-4C2F-B412-2610A05FBA0E}"')  # 트랙#1과 동일 trackID로 충돌
    assert broken != song_xml
    c = SongContainer.read(NAIITE)
    c.replace_text("Song/song.xml", broken)
    errs = [p for p in validate(c, naiite_model) if p.severity == "error"]
    assert any(p.code == "duplicate-track-id" for p in errs)


def test_detects_duplicate_track_number(naiite, naiite_model):
    song_xml = naiite.read_text("Song/song.xml")
    broken = song_xml.replace('trackNumber="2"', 'trackNumber="1"')
    assert broken != song_xml
    c = SongContainer.read(NAIITE)
    c.replace_text("Song/song.xml", broken)
    errs = [p for p in validate(c, naiite_model) if p.severity == "error"]
    assert any(p.code == "duplicate-track-number" for p in errs)


def test_missing_track_number_sentinel_not_treated_as_duplicate(naiite, naiite_model):
    """trackNumber 속성 결측(-1 센티널)인 트랙이 2개 이상이어도 중복으로 오판하지 않는다
    (아키텍트 리뷰 지적 — 실제 코퍼스엔 결측 사례가 없어 방어적으로 합성 검증)."""
    song_xml = naiite.read_text("Song/song.xml")
    broken = song_xml.replace('trackNumber="1" ', "", 1).replace('trackNumber="2" ', "", 1)
    assert broken != song_xml
    c = SongContainer.read(NAIITE)
    c.replace_text("Song/song.xml", broken)
    tracks = parse_tracks(c)
    assert sum(1 for t in tracks.media_tracks if t.track_number == -1) == 2
    errs = [p for p in validate(c, naiite_model) if p.severity == "error"]
    assert not any(p.code == "duplicate-track-number" for p in errs)


@pytest.mark.parametrize("song", ALL_SONGS, ids=lambda p: p.stem[:40])
def test_corpus_no_v2_false_positive(song):
    """원본 코퍼스 전체(116곡)에 v2 확장 검사가 오탐 없이 통과해야 한다."""
    container = SongContainer.read(song)
    model = load_model(container)
    codes = {p.code for p in validate(container, model) if p.severity == "error"}
    assert not (codes & V2_CODES), f"{song}: {codes & V2_CODES}"
