"""UID 참조 전수 스캐너 + 구조 무결성 검사 (fail-closed).

S0.1(b-3) 카탈로그 근거 참조 형태:
  - braced: uid="{G}" / objectID="{G}/…" / id="{G}" / trackID="{G}" / param:///AudioMixer/{G}/…
  - dashless HEX32: mixerconsole Section path / perspective windowID·복합 경로

검사 방향 (계획 1.5):
  ① dangling — 존재하지 않는 대상을 가리키는 참조
  ② 구조적 불완전성 — 채널 존재 but 동반 entry(콘솔 Section, preset 파일) 누락
naiite_14 실측 기준선: 채널 33 == 콘솔 Section 33, 고아 preset/Envelopes 폴더 0,
미참조 preset 파일 0 — 이 정합 상태를 불변식으로 삼는다.
"""
import re
from dataclasses import dataclass

from .container import SongContainer
from .mixer_parser import MixerModel
from .song_parser import SONG_XML_ENTRY, parse_tracks

TEXT_ENTRIES_HINT = (".xml", ".txt")
BRACED_RE_TMPL = r"\{%s\}"
AUTOMATION_IDENTITY_RE = re.compile(r'identity="param:///AudioMixer/(\{[0-9A-F-]{36}\})/')


@dataclass(frozen=True)
class Ref:
    entry: str
    line_no: int
    form: str
    context: str


@dataclass(frozen=True)
class Problem:
    severity: str  # "error" | "warning"
    code: str
    message: str


def _dashless(uid: str) -> str:
    return uid.strip("{}").replace("-", "")


def _iter_text_entries(container: SongContainer):
    for name in container.names():
        if not name.lower().endswith(TEXT_ENTRIES_HINT):
            continue
        try:
            yield name, container.read_entry(name).decode("utf-8-sig")
        except UnicodeDecodeError:
            continue


def scan_references(container: SongContainer, uid: str) -> list[Ref]:
    """주어진 채널 UID의 모든 zip entry 내 등장 위치를 전수 열거."""
    bare = uid.strip("{}")
    braced = "{" + bare + "}"
    dashless = _dashless(uid)
    refs: list[Ref] = []
    for name, text in _iter_text_entries(container):
        for i, line in enumerate(text.splitlines(), 1):
            hit_braced = braced in line
            hit_dashless = dashless in line
            if not hit_braced and not hit_dashless:
                continue
            if f'uid="{braced}"' in line:
                form = 'uid="{G}"'
            elif f'objectID="{braced}/' in line:
                form = 'objectID="{G}/…"'
            elif f'id="{braced}"' in line:
                form = 'id="{G}"'
            elif f"/AudioMixer/{braced}/" in line:
                form = "param:///AudioMixer/{G}/…"
            elif hit_dashless and f'path="{dashless}"' in line:
                form = 'Section path="HEX32"'
            elif hit_dashless:
                form = "HEX32(복합)"
            else:
                form = "{G}(기타)"
            refs.append(Ref(name, i, form, line.strip()[:160]))
    return refs


def validate(container: SongContainer, model: MixerModel,
             require_console_for: set[str] | None = None) -> list[Problem]:
    """무결성 검사. error가 하나라도 있으면 쓰기를 거부해야 한다(fail-closed).

    require_console_for: 콘솔/뱅크 동반 기재를 필수(error)로 강제할 UID 집합
    (전송 엔진이 새로 만든 채널). 그 외 채널의 콘솔 누락은 warning
    (원본 코퍼스에 예외가 존재할 수 있으므로 전송 산출물만 엄격 검사).
    """
    problems: list[Problem] = []
    chan_by_uid = model.by_uid()
    names = set(container.names())
    require_console_for = require_console_for or set()

    # ① dangling: destination/send 대상 존재
    for ch in model.channels:
        targets = []
        if ch.destination_uid:
            targets.append(("destination", ch.destination_uid))
        targets += [("send", s.destination_uid) for s in ch.sends]
        for kind, target in targets:
            if target not in chan_by_uid:
                problems.append(Problem(
                    "error", "dangling-route",
                    f"{ch.label}({ch.uid})의 {kind} 대상 {target}이 존재하지 않음"))

    # ① dangling: 인서트 presetPath 실재
    for ch in model.channels:
        for ins in ch.inserts:
            if ins.preset_path and ins.preset_path not in names:
                problems.append(Problem(
                    "error", "missing-preset",
                    f"{ch.label} 인서트 {ins.plugin_name}의 presetPath 부재: {ins.preset_path}"))

    # ② 구조: 콘솔 Section / 뱅크
    console = container.read_text("Devices/mixerconsole.xml") \
        if container.has("Devices/mixerconsole.xml") else ""
    sections = set(re.findall(r'Section path="([0-9A-F]{32})"', console))
    for ch in model.channels:
        if _dashless(ch.uid) not in sections:
            severity = "error" if ch.uid in require_console_for else "warning"
            problems.append(Problem(
                severity, "missing-console-section",
                f"{ch.label}({ch.uid}) 콘솔 Section 누락"))
    for uid in require_console_for:
        if uid in chan_by_uid and console.count(f'uid="{uid}"') < 2:
            problems.append(Problem(
                "error", "missing-console-bank",
                f"{chan_by_uid[uid].label}({uid}) ScreenBank/RemoteBank 기재 누락"))

    # ② 구조: UID 전역 유일성
    uids = [c.uid for c in model.channels]
    for dup in {u for u in uids if uids.count(u) > 1}:
        problems.append(Problem("error", "duplicate-uid", f"채널 UID 중복: {dup}"))

    # ② 구조: 라벨 폴더 축 — 참조된 preset 파일이 실제 폴더와 정합한지는
    # missing-preset에서 커버. 역방향(고아 폴더)은 정보성 경고.
    labels = {c.label for c in model.channels}
    preset_dirs = {n.split("/")[2] for n in names
                   if n.startswith("Presets/Channels/") and n.count("/") >= 3}
    for orphan in preset_dirs - labels:
        problems.append(Problem("warning", "orphan-preset-dir",
                                f"채널 없는 프리셋 폴더: Presets/Channels/{orphan}/"))

    # ③ v2 확장 — song.xml 트랙/오토메이션 구조 fail-closed 검사 (S3b/S4)
    # dangling-automation-identity/dangling-track-channel은 missing-console-section과
    # 동일한 비대칭 원칙 적용: 원본 코퍼스에 스테일 참조가 실존함이 실측됨
    # (naiite_20의 삭제된 구 S.BUS UID {7AEF0C5E-…} 오토메이션 리전 — progress.txt의
    # notepad.xml 스테일 UID와 동일 현상, Studio One이 허용하는 정상 상태).
    # 따라서 require_console_for(이 전송이 새로 만든 채널)에 속할 때만 error, 그 외 warning.
    if container.has(SONG_XML_ENTRY):
        song_xml = container.read_text(SONG_XML_ENTRY)
        for m in AUTOMATION_IDENTITY_RE.finditer(song_xml):
            target = m.group(1)
            if target not in chan_by_uid:
                severity = "error" if target in require_console_for else "warning"
                problems.append(Problem(
                    severity, "dangling-automation-identity",
                    f"AutomationRegion identity가 존재하지 않는 채널 UID 참조: {target}"))

        tracks = parse_tracks(container)
        for mt in tracks.media_tracks:
            # mediaType="Audio"만 audiomixer 채널을 가리킨다 — "Music"(악기/MIDI) 트랙은
            # Devices/musictrackdevice.xml의 별도 채널을 참조하며 v2 범위 밖(실측: song3/song1.song)
            if mt.media_type == "Audio" and mt.channel_id and mt.channel_id not in chan_by_uid:
                severity = "error" if mt.channel_id in require_console_for else "warning"
                problems.append(Problem(
                    severity, "dangling-track-channel",
                    f"MediaTrack({mt.name}, trackID={mt.track_id})의 channelID가 "
                    f"존재하지 않는 채널: {mt.channel_id}"))

        all_track_ids = tracks.all_track_ids()
        for dup in {t for t in all_track_ids if all_track_ids.count(t) > 1}:
            problems.append(Problem("error", "duplicate-track-id", f"trackID 중복: {dup}"))

        # -1 = trackNumber 속성 없음(song_parser.py의 결측 센티널) — 실제 값이 아니므로
        # 여러 트랙이 결측이어도 중복으로 오판하지 않도록 제외
        track_numbers = [mt.track_number for mt in tracks.media_tracks if mt.track_number != -1]
        for dup in {n for n in track_numbers if track_numbers.count(n) > 1}:
            problems.append(Problem("error", "duplicate-track-number",
                                    f"trackNumber 중복: {dup}"))
    return problems


def errors_of(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.severity == "error"]
