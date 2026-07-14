"""Song/song.xml <List x:id="Tracks"> 파서 (읽기 전용).

v2 S3b(버스 오토메이션 전송)의 uid_refs.validate() fail-closed 확장 3종이
필요로 하는 트랙 메타데이터(trackID/channelID/trackNumber)를 추출한다.
mixer_parser.py와 동일하게 x: 접두사 미선언 XML에 xmlns:x를 주입해 표준
ElementTree로 파싱한다 — 읽기 전용이므로 원형 훼손(재직렬화) 위험 없음.

실측 근거(naiite_14.song, 2026-07-12):
  - MediaTrack: trackID, trackNumber(1부터 순번), 자식 <UID x:id="channelID" uid="{G}"/>
  - AutomationTrack: trackID, name(=버스 라벨) — trackNumber 속성 없음(실측 확인),
    channelID 자식 없음(대신 AutomationRegion identity의 param:///AudioMixer/{UID}가
    대상 채널을 가리킴 — uid_refs.py가 이미 이 형태를 스캔함)
  - MediaTrack mediaType: "Audio"인 경우만 channelID가 audiomixer.xml 채널을 가리킨다.
    "Music"(악기/MIDI 트랙, song3/song1.song "MODO DRUM" 실측)은 channelID가
    Devices/musictrackdevice.xml에 정의된 별도 채널을 가리키며 audiomixer 모델 밖이다 —
    v2 범위(오디오 트랙 전송)에서는 out-of-scope이므로 dangling 검사 대상에서 제외해야 함.
"""
from xml.etree import ElementTree as ET
from dataclasses import dataclass

from .container import SongContainer
from .mixer_parser import XID, parse_xml as _parse_xml

SONG_XML_ENTRY = "Song/song.xml"


@dataclass(frozen=True)
class MediaTrackInfo:
    track_id: str
    track_number: int
    channel_id: str | None
    name: str
    media_type: str


@dataclass(frozen=True)
class AutomationTrackInfo:
    track_id: str
    name: str


@dataclass(frozen=True)
class TrackModel:
    media_tracks: tuple[MediaTrackInfo, ...]
    automation_tracks: tuple[AutomationTrackInfo, ...]

    def all_track_ids(self) -> list[str]:
        return [t.track_id for t in self.media_tracks] + \
               [t.track_id for t in self.automation_tracks]


def _find_tracks_list(root: ET.Element) -> ET.Element | None:
    for el in root.iter("List"):
        if el.get(XID) == "Tracks":
            return el
    return None


def _channel_id_of(track_el: ET.Element) -> str | None:
    for uid_el in track_el.findall("UID"):
        if uid_el.get(XID) == "channelID":
            return uid_el.get("uid")
    return None


def parse_tracks(container: SongContainer) -> TrackModel:
    """song.xml의 Tracks 리스트에서 MediaTrack/AutomationTrack 메타데이터 추출.

    Tracks 리스트가 없는 song(오디오/오토메이션 트랙 없음)은 빈 TrackModel 반환.
    """
    if not container.has(SONG_XML_ENTRY):
        return TrackModel(media_tracks=(), automation_tracks=())
    root = _parse_xml(container.read_text(SONG_XML_ENTRY))
    tracks_list = _find_tracks_list(root)
    if tracks_list is None:
        return TrackModel(media_tracks=(), automation_tracks=())

    media: list[MediaTrackInfo] = []
    automation: list[AutomationTrackInfo] = []
    for el in tracks_list:
        if el.tag == "MediaTrack":
            track_number_raw = el.get("trackNumber")
            media.append(MediaTrackInfo(
                track_id=el.get("trackID", ""),
                track_number=int(track_number_raw) if track_number_raw else -1,
                channel_id=_channel_id_of(el),
                name=el.get("name", ""),
                media_type=el.get("mediaType", ""),
            ))
        elif el.tag == "AutomationTrack":
            automation.append(AutomationTrackInfo(
                track_id=el.get("trackID", ""),
                name=el.get("name", ""),
            ))
    return TrackModel(media_tracks=tuple(media), automation_tracks=tuple(automation))
