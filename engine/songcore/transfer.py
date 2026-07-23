"""전송 엔진 — 버스/FX 채널 서브트리 삽입 + 기존 채널 인서트 체인 교체 + 트랙 채널 전송.

방식: audiomixer.xml/song.xml 텍스트 수술(원형 보존) + 동반 entry(mixerconsole/notepad)
작성 + Presets/Envelopes 라벨 폴더 복사 + fail-closed 재검증.

1차 범위(계획 1.6): AudioGroupChannel/AudioEffectChannel 서브트리 전송, 기존 채널 인서트 교체.
v2 확장(S3b/S4b): 버스 오토메이션(AutomationTrack) 동반 전송, 단일 트랙 채널(AudioTrackChannel)
전송(transfer_track — 기본 빈 트랙, 이벤트 제외).
"""
import re
import uuid
import zipfile
from dataclasses import dataclass, field

from .container import SongContainer
from .mixer_parser import Channel, MixerModel, parse_mixer
from .song_parser import SONG_XML_ENTRY, parse_tracks
from .topology import build_graph
from .uid_refs import errors_of, validate

MIXER = "Devices/audiomixer.xml"
CONSOLE = "Devices/mixerconsole.xml"
NOTEPAD = "notepad.xml"
TRANSFERABLE_TAGS = ("AudioGroupChannel", "AudioEffectChannel")
UID_PATTERN = r"\{[0-9A-F-]{36}\}"
AUTOMATION_TRACK_RE = re.compile(r"<AutomationTrack\b.*?</AutomationTrack>", re.S)
LIST_TAG_RE = re.compile(r"<(/?)List\b[^>]*?(/?)>")
ATTR_TAG_RE = re.compile(r"<(/?)Attributes\b[^>]*?(/?)>")


class TransferError(RuntimeError):
    """전송 불가/무결성 실패 (fail-closed)."""


@dataclass
class Conflict:
    label: str
    dst_uid: str
    kind: str  # "channel-label" | "preset-folder" | "envelope-folder"


@dataclass
class TransferResult:
    new_channel_uids: dict[str, str] = field(default_factory=dict)  # old→new
    replaced_labels: list[str] = field(default_factory=list)
    dropped_sends: list[str] = field(default_factory=list)
    copied_entries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def new_guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def _find_channel_block(mixer: str, uid: str) -> tuple[int, int, str, str]:
    """UID로 채널 블록을 찾아 (start, end, tag, block) 반환."""
    for tag in ("AudioInputChannel", "AudioOutputChannel", "AudioTrackChannel",
                "AudioGroupChannel", "AudioEffectChannel"):
        for m in re.finditer(rf"<{tag}\b.*?</{tag}>", mixer, re.S):
            if f'uid="{uid}"' in m.group(0):
                return m.start(), m.end(), tag, m.group(0)
    raise TransferError(f"채널 블록을 찾을 수 없음: {uid}")


# audiomixer.xml의 <ChannelGroup> 표준 순서(실제 코퍼스로 확인) — 대상 song에 해당
# 종류 채널이 하나도 없으면 Studio One이 그룹 자체를 아예 생략하므로, 새로 만들 때
# 형제 그룹 중 어디에 끼워 넣어야 할지 판단하는 기준으로 쓴다.
GROUP_ORDER = ("AudioInput", "AudioOutput", "AudioTrack", "AudioGroup", "AudioEffect")


def _ensure_channel_group(mixer: str, group_name: str) -> str:
    """group_name의 <ChannelGroup>이 통째로 없으면(대상에 그 종류 채널이 하나도
    없어 Studio One이 그룹 자체를 생략한 경우 — 예: FX 채널이 전혀 없던 곡에
    버스/FX 서브트리를 처음 이식) GROUP_ORDER 순서에 맞는 위치에 빈 그룹을 새로
    만들어 삽입한다. 이미 있으면 그대로 반환."""
    if re.search(rf'<ChannelGroup name="{group_name}"[^>]*>', mixer):
        return mixer
    idx = GROUP_ORDER.index(group_name)
    new_group = f'<ChannelGroup name="{group_name}" flags="1">\r\n\t\t</ChannelGroup>'
    for later in GROUP_ORDER[idx + 1:]:
        m = re.search(rf'\r\n(\t+)<ChannelGroup name="{later}"[^>]*>', mixer)
        if m:
            return mixer[:m.start()] + f"\r\n{m.group(1)}" + new_group + mixer[m.start():]
    for earlier in reversed(GROUP_ORDER[:idx]):
        m = re.search(rf'\r\n(\t+)<ChannelGroup name="{earlier}"[^>]*>.*?</ChannelGroup>',
                      mixer, re.S)
        if m:
            return mixer[:m.end()] + f"\r\n{m.group(1)}" + new_group + mixer[m.end():]
    raise TransferError(f"ChannelGroup을 삽입할 기준 위치를 찾을 수 없음: {group_name}")


def _group_insert_pos(mixer: str, group_name: str) -> tuple[str, int]:
    """해당 ChannelGroup의 닫는 태그 직전 삽입 위치. 반환: (갱신된 mixer, 위치) —
    그룹이 없던 경우 _ensure_channel_group이 새로 만들므로 mixer가 바뀔 수 있다."""
    mixer = _ensure_channel_group(mixer, group_name)
    m = re.search(rf'<ChannelGroup name="{group_name}"[^>]*>(.*?)</ChannelGroup>',
                  mixer, re.S)
    assert m is not None  # _ensure_channel_group가 존재를 보장
    inner_end = m.end(1)
    # 닫는 태그 앞의 들여쓰기(\r\n\t\t)를 보존하기 위해 마지막 개행 위치로 후퇴
    tail = mixer.rfind("\r\n", m.start(1), inner_end)
    return mixer, (tail if tail != -1 else inner_end)


def _used_channel_names(mixer: str, group_name: str) -> set[str]:
    m = re.search(rf'<ChannelGroup name="{group_name}"[^>]*>(.*?)</ChannelGroup>',
                  mixer, re.S)
    return set(re.findall(r'name="(Channel\d+)"', m.group(1))) if m else set()


def _next_channel_name(used: set[str]) -> str:
    n = 1
    while f"Channel{n:02d}" in used:
        n += 1
    used.add(f"Channel{n:02d}")
    return f"Channel{n:02d}"


def _next_send_name(used: set[str]) -> str:
    n = 1
    while f"Send{n:02d}" in used:
        n += 1
    used.add(f"Send{n:02d}")
    return f"Send{n:02d}"


def _attributes_span(xml: str, open_pattern: str) -> tuple[int, int, int]:
    """open_pattern(정규식)으로 찾은 <Attributes ...> 여는 태그의
    (여는태그 시작, 내용 시작, 닫는 태그 시작) 오프셋.

    Attributes는 서로 중첩되므로(예: Sends 안의 SendNN 안의 Panner) 첫 </Attributes>로
    단순 검색하면 중첩된 자식의 닫는 태그를 오판한다 — 태그 깊이를 세어 진짜 닫는
    태그를 찾는다(_list_content_span과 동일한 패턴, 대상 태그만 다름).
    """
    m = re.search(open_pattern, xml)
    if not m:
        raise TransferError(f"Attributes 블록을 찾을 수 없음: {open_pattern}")
    content_start = m.end()
    depth = 1
    for tm in ATTR_TAG_RE.finditer(xml, content_start):
        is_close, is_selfclose = tm.group(1) == "/", tm.group(2) == "/"
        if is_selfclose:
            continue
        depth += -1 if is_close else 1
        if depth == 0:
            return m.start(), content_start, tm.start()
    raise TransferError(f"Attributes 닫는 태그를 찾지 못함: {open_pattern}")


def _top_level_attr_children(xml: str, start: int, end: int) -> list[tuple[int, int]]:
    """[start, end) 구간에서 depth 1(바로 아래) 자식 <Attributes>...</Attributes>
    블록들의 (시작, 끝) 오프셋 목록 — Sends 안의 개별 SendNN 블록을 열거하는 데 쓴다."""
    depth = 0
    cur_start = None
    spans: list[tuple[int, int]] = []
    for tm in ATTR_TAG_RE.finditer(xml, start, end):
        is_close, is_selfclose = tm.group(1) == "/", tm.group(2) == "/"
        if is_selfclose:
            continue
        if not is_close:
            if depth == 0:
                cur_start = tm.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                spans.append((cur_start, tm.end()))
    return spans


def _carry_over_sends(src_block: str, dst_block: str, bus_uid_map: dict[str, str],
                      ch_label: str, result: TransferResult) -> str:
    """src_block(소스 채널)의 send 중 이번 배치에서 함께 이식된 버스/FX(bus_uid_map의
    키)를 향하던 것만 골라 dst_block(대상 채널)에 새로 추가한다.

    체인 교체(replace_insert_chain)는 인서트 체인만 다루고 send는 그대로 두므로,
    소스 트랙이 이번에 새로 이식된 FX 리턴 버스로 보내던 send가 대상에는 없어
    "반영 안 됨"으로 보이는 문제(실사용 리포트)를 메운다. 대상에 이미 있던
    무관한 send나, 이번 배치 밖의(이미 대상에 존재하는) 채널로의 send는 건드리지
    않는다 — 이번에 새로 이식된 대상만 자동 연결(범위를 최소화, YAGNI).
    """
    if not bus_uid_map:
        return dst_block
    try:
        _o, src_start, src_end = _attributes_span(src_block, r'<Attributes x:id="Sends">')
    except TransferError:
        return dst_block

    new_sends: list[str] = []
    for c_start, c_end in _top_level_attr_children(src_block, src_start, src_end):
        send_block = src_block[c_start:c_end]
        conn_m = re.search(
            rf'<Connection x:id="destination" objectID="({UID_PATTERN})/Input" friendlyName="([^"]*)"',
            send_block)
        if not conn_m or conn_m.group(1) not in bus_uid_map:
            continue
        new_target = bus_uid_map[conn_m.group(1)]
        nb = send_block.replace(conn_m.group(1), new_target)
        for um in re.finditer(rf'<UID x:id="uniqueID" uid="({UID_PATTERN})"/>', nb):
            nb = nb.replace(um.group(1), new_guid())
        new_sends.append(nb)
        result.notes.append(f"{ch_label} send→{conn_m.group(2)} 자동 연결(신규 이식분)")

    if not new_sends:
        return dst_block
    try:
        _o, dst_start, dst_end = _attributes_span(dst_block, r'<Attributes x:id="Sends">')
    except TransferError:
        return dst_block  # 대상에 Sends 블록 자체가 없으면 조용히 스킵(관측상 항상 존재)

    used = {m.group(1) for m in re.finditer(r'name="(Send\d+)"',
                                            dst_block[dst_start:dst_end])}
    renamed = []
    for nb in new_sends:
        name = _next_send_name(used)
        renamed.append(re.sub(r'name="Send\d+"', f'name="{name}"', nb, count=1))
    insert_at = dst_end
    return (dst_block[:insert_at] + "\r\n\t\t\t\t\t"
           + "\r\n\t\t\t\t\t".join(renamed) + dst_block[insert_at:])


def safe_label_path(label: str) -> str:
    """zip 경로에 쓰이는 라벨 그대로 사용하되 경로 탈출 문자를 방어."""
    if "/" in label or "\\" in label or ".." in label:
        raise TransferError(f"라벨에 경로 문자 포함 — 전송 불가: {label!r}")
    return label


def _copy_channel_files(src: SongContainer, dst: SongContainer, label: str,
                        result: TransferResult) -> None:
    """Presets/Envelopes 라벨 폴더 복사 (덮어쓰기: 대상의 기존 entry 교체)."""
    dst_names_now = dst.names()
    for prefix in (f"Presets/Channels/{label}/", f"Envelopes/{label}/"):
        for name in src.names():
            if not name.startswith(prefix):
                continue
            data = src.read_entry(name)
            if dst.has(name):
                dst.replace(name, data)
            else:
                comp = (zipfile.ZIP_STORED if name.endswith(".vstpreset")
                        else zipfile.ZIP_DEFLATED)
                dst.add(name, data, template_name=dst_names_now[0], compress_type=comp)
            result.copied_entries.append(name)


def detect_conflicts(src_model: MixerModel, transfer_uids: list[str],
                     dst: SongContainer, dst_model: MixerModel) -> list[Conflict]:
    """대상에 동명 채널/폴더가 있는지 검사 (승인 후 덮어쓰기 대상 목록)."""
    conflicts: list[Conflict] = []
    src_by_uid = src_model.by_uid()
    dst_labels = {c.label: c for c in dst_model.channels}
    dst_names = dst.names()
    for uid in transfer_uids:
        label = src_by_uid[uid].label
        if label in dst_labels:
            conflicts.append(Conflict(label, dst_labels[label].uid, "channel-label"))
        else:
            if any(n.startswith(f"Presets/Channels/{label}/") for n in dst_names):
                conflicts.append(Conflict(label, "", "preset-folder"))
            if any(n.startswith(f"Envelopes/{label}/") for n in dst_names):
                conflicts.append(Conflict(label, "", "envelope-folder"))
    return conflicts


def subtree_transfer_set(src_model: MixerModel, root_uid: str) -> list[str]:
    """전송 대상 UID 목록 (그룹/FX 채널만, 소스 XML 순서 유지)."""
    graph = build_graph(src_model)
    subtree = graph.subtree_uids(root_uid)
    by_uid = src_model.by_uid()
    return [c.uid for c in src_model.channels
            if c.uid in subtree and c.tag in TRANSFERABLE_TAGS]


def _remove_channel_from_dst(dst_mixer: str, console: str, notepad: str,
                             ch: Channel,
                             result: TransferResult) -> tuple[str, str, str]:
    """덮어쓰기: 기존 동명 채널 블록과 콘솔/notepad 동반 항목을 제거."""
    start, end, _tag, _block = _find_channel_block(dst_mixer, ch.uid)
    # 블록 앞 개행+들여쓰기까지 제거
    lead = dst_mixer.rfind("\r\n", 0, start)
    dst_mixer = dst_mixer[:lead] + dst_mixer[end:]
    dashless = ch.uid.strip("{}").replace("-", "")
    console = re.sub(
        rf'\t\t<Section path="{dashless}">.*?</Section>\r\n', "", console, flags=re.S)
    console = console.replace(f'\t\t\t\t<UID uid="{ch.uid}"/>\r\n', "")
    notepad = re.sub(rf'\t<NotepadItem id="{re.escape(ch.uid)}"[^>]*/>\r\n', "", notepad)
    result.replaced_labels.append(ch.label)
    return dst_mixer, console, notepad


def _find_automation_tracks_for_channels(song_xml: str,
                                         uids: set[str]) -> list[tuple[str, str]]:
    """uids 중 하나라도 AutomationRegion identity로 참조하는 AutomationTrack 블록을
    (old_track_id, block_text) 목록으로 반환 (S3a 실측: 채널당 최대 1개, 여러 파라미터의
    AutomationRegion을 자식으로 가질 수 있음)."""
    results: list[tuple[str, str]] = []
    for m in AUTOMATION_TRACK_RE.finditer(song_xml):
        block = m.group(0)
        tid_m = re.search(r'trackID="([^"]+)"', block)
        if not tid_m:
            continue
        refs = set(re.findall(r"/AudioMixer/(" + UID_PATTERN + r")/", block))
        if refs & uids:
            results.append((tid_m.group(1), block))
    return results


def _list_content_span(xml: str, list_id: str) -> tuple[int, int]:
    """<List x:id="{list_id}">…</List>의 (내용 시작, 내용 끝) 오프셋.

    List는 서로 중첩되므로(Tracks 안에 MediaTrack의 Events 등) 태그 균형을 세어
    진짜 닫는 태그를 찾는다 — 첫 </List>로 단순 검색하면 중첩된 자식의 닫는 태그를
    오판할 수 있다.
    """
    start_m = re.search(rf'<List x:id="{list_id}"[^>]*>', xml)
    if not start_m:
        raise TransferError(f"song.xml에 List(x:id={list_id})가 없음")
    pos = start_m.end()
    depth = 1
    for m in LIST_TAG_RE.finditer(xml, pos):
        is_close, is_selfclose = m.group(1) == "/", m.group(2) == "/"
        if is_selfclose:
            continue  # 자기 닫힘 <List .../> — 깊이 변화 없음
        depth += -1 if is_close else 1
        if depth == 0:
            return start_m.end(), m.start()
    raise TransferError(f"List(x:id={list_id}) 닫는 태그를 찾지 못함")


def _strip_list(xml: str, list_id: str) -> str:
    """<List x:id="{list_id}">…</List> 블록 전체를 텍스트에서 제거(중첩 안전).

    _list_content_span과 동일한 태그 깊이 카운팅을 사용 — 단순 정규식(.*?</List>)은
    List가 중첩된 경우(예: 다른 x:id의 자식 List) 첫 닫는 태그를 오판할 수 있다.
    해당 리스트가 없으면 원본을 그대로 반환.
    """
    if f'<List x:id="{list_id}"' not in xml:
        return xml
    open_m = re.search(rf'<List x:id="{list_id}"[^>]*>', xml)
    _content_start, content_end = _list_content_span(xml, list_id)
    close_end = xml.index("</List>", content_end) + len("</List>")
    lead = xml.rfind("\r\n", 0, open_m.start())
    cut_start = lead if lead != -1 else open_m.start()
    return xml[:cut_start] + xml[close_end:]


def _transfer_automation_tracks(src_song_xml: str, dst: SongContainer,
                                uid_map: dict[str, str], transfer_uids: set[str],
                                result: TransferResult) -> None:
    """전송된 채널의 AutomationTrack을 dst song.xml의 Tracks 리스트 말미에 삽입.

    Open Question 1(계획 문서): 삽입 순서는 무관하다고 가정 — 말미 삽입으로 충분한지는
    S3a 스파이크(.omc/verify/05-automation-transfer.song)의 수동 게이트로 최종 확인.
    """
    blocks = _find_automation_tracks_for_channels(src_song_xml, transfer_uids)
    if not blocks or not dst.has(SONG_XML_ENTRY):
        return
    new_blocks: list[str] = []
    for old_track_id, block in blocks:
        nb = block.replace(f'trackID="{old_track_id}"', f'trackID="{new_guid()}"')
        for old_uid, new_uid in uid_map.items():
            nb = nb.replace(old_uid, new_uid)
        new_blocks.append(nb)

    dst_song_xml = dst.read_text(SONG_XML_ENTRY)
    _content_start, content_end = _list_content_span(dst_song_xml, "Tracks")
    insert_pos = dst_song_xml.rfind("\r\n", 0, content_end)
    if insert_pos == -1:
        insert_pos = content_end
    insertion = "".join(f"\r\n\t\t\t{b}" for b in new_blocks)
    dst_song_xml = dst_song_xml[:insert_pos] + insertion + dst_song_xml[insert_pos:]
    dst.replace_text(SONG_XML_ENTRY, dst_song_xml)
    result.notes.append(f"오토메이션 트랙 {len(new_blocks)}개 전송")


def transfer_subtree(src: SongContainer, src_model: MixerModel, root_uid: str,
                     dst: SongContainer, overwrite_confirmed: bool = False,
                     preserve_external_sends: bool = False) -> TransferResult:
    """소스의 버스/FX 서브트리를 대상 컨테이너에 기록한다 (메모리 상 변경).

    저장은 호출자가 dst.save_over()/write_to()로 수행.
    이름 충돌이 있는데 overwrite_confirmed=False면 TransferError (UI가 확인 후 재호출).
    preserve_external_sends: 서브트리 밖(전송 집합 외부)을 향하던 send 중 대상과
    동명 채널이 dst에 있으면 그 채널로 재배선(옵션 off/미존재 시 기존대로 제거+기록).
    """
    result = TransferResult()
    transfer_uids = subtree_transfer_set(src_model, root_uid)
    if not transfer_uids:
        raise TransferError("전송 가능한 그룹/FX 채널이 서브트리에 없음")
    src_by_uid = src_model.by_uid()
    src_mixer = src.read_text(MIXER)

    dst_model = parse_mixer(dst.read_text(MIXER))
    conflicts = detect_conflicts(src_model, transfer_uids, dst, dst_model)
    if conflicts and not overwrite_confirmed:
        raise TransferError(
            "이름 충돌 — 확인 필요: " + ", ".join(f"{c.label}({c.kind})" for c in conflicts))

    dst_mixer = dst.read_text(MIXER)
    console = dst.read_text(CONSOLE) if dst.has(CONSOLE) else ""
    notepad = dst.read_entry(NOTEPAD).decode("utf-8-sig") if dst.has(NOTEPAD) else ""

    # 0) 덮어쓰기: 동명 채널 제거 + 유입 라우팅 재배선 맵 (old dst uid → new uid)
    inbound_rewire: dict[str, str] = {}
    dst_by_label = {c.label: c for c in dst_model.channels}
    for uid in transfer_uids:
        label = src_by_uid[uid].label
        old = dst_by_label.get(label)
        if old is not None:
            dst_mixer, console, notepad = _remove_channel_from_dst(
                dst_mixer, console, notepad, old, result)
            inbound_rewire[old.uid] = uid  # 일단 old→src uid, 아래에서 new uid로 재매핑

    # 1) UID 재생성 맵
    uid_map: dict[str, str] = {}
    blocks: list[tuple[str, str, str]] = []  # (group, new_block, src_uid)
    for uid in transfer_uids:
        _s, _e, tag, block = _find_channel_block(src_mixer, uid)
        for m in re.finditer(rf'<UID x:id="uniqueID" uid="({UID_PATTERN})"/>', block):
            uid_map.setdefault(m.group(1), new_guid())
        blocks.append((src_by_uid[uid].group, block, uid))
    for old_dst_uid, src_uid in list(inbound_rewire.items()):
        inbound_rewire[old_dst_uid] = uid_map[src_uid]

    # 2) 대상 라우팅 종단 결정: 소스 root의 destination 라벨과 동명 채널 → 없으면 대상의 MIXOUT류 → 메인
    root_ch = src_by_uid[root_uid]
    dst_model_now = parse_mixer(dst_mixer)
    terminal = None
    if root_ch.destination_name:
        terminal = dst_model_now.by_label(root_ch.destination_name)
    if terminal is None:
        # 동명 종단이 없으면 대상의 메인 아웃으로 직결 (MIXOUT→메인과 동일 패턴)
        outs = dst_model_now.group("AudioOutput")
        terminal = outs[0] if outs else None
    if terminal is None:
        raise TransferError("대상 song에서 라우팅 종단을 찾을 수 없음")
    result.notes.append(f"root 라우팅 접합: {root_ch.label} → {terminal.label}")

    # 3) 블록 변환 + 삽입
    for group, block, src_uid in blocks:
        nb = block
        ch = src_by_uid[src_uid]
        safe_label_path(ch.label)
        # 3a) uniqueID 치환
        for old, new in uid_map.items():
            nb = nb.replace(old, new)
        # 3b) Connection 재배선 — 내부 대상(전송 집합)은 3a에서 새 UID로 치환 완료.
        # root의 외부 destination은 terminal로 접합, 그 외 외부 send는 제거.
        if src_uid == root_uid:
            nb = re.sub(
                rf'(<Connection x:id="destination" objectID=")({UID_PATTERN})(/Input" friendlyName=")[^"]*(")',
                lambda m: m.group(1) + terminal.uid + m.group(3) + terminal.label + m.group(4),
                nb, count=1)
        # Sends 블록 내 외부 대상 send 처리: 전송 집합 내부면 유지, 외부면
        # preserve_external_sends 옵션에 따라 동명 채널로 재배선하거나 제거+기록
        def clean_sends(m: re.Match) -> str:
            sends_block = m.group(0)
            def check(conn: re.Match) -> str:
                target, label = conn.group(1), conn.group(2)
                if target in uid_map.values():
                    return conn.group(0)
                if preserve_external_sends and label in dst_by_label:
                    new_target = dst_by_label[label].uid
                    result.notes.append(f"{ch.label} send→{label} 보존(동명 채널 재배선)")
                    return conn.group(0).replace(f'objectID="{target}/', f'objectID="{new_target}/')
                result.dropped_sends.append(f"{ch.label} send→{label}")
                return ""
            return re.sub(
                rf'\r\n\s*<Connection x:id="destination" objectID="({UID_PATTERN})/Input" friendlyName="([^"]*)"\s*/>',
                check, sends_block)
        nb = re.sub(r'<Attributes x:id="Sends">.*?</Attributes>', clean_sends, nb, flags=re.S)
        # 3c) 그룹 내 name 유일화
        used = _used_channel_names(dst_mixer, group)
        new_name = _next_channel_name(used)
        nb = re.sub(r'name="Channel\d+"', f'name="{new_name}"', nb, count=1)
        # 3d) 삽입
        dst_mixer, pos = _group_insert_pos(dst_mixer, group)
        dst_mixer = dst_mixer[:pos] + "\r\n\t\t\t" + nb + dst_mixer[pos:]

        new_uid = uid_map[src_uid]
        result.new_channel_uids[src_uid] = new_uid

        # 3e) 동반 entry
        dashless = new_uid.strip("{}").replace("-", "")
        orders = [int(x) for x in re.findall(r'order="(\d+)"', console)] or [0]
        section = (f'\t\t<Section path="{dashless}">\r\n'
                   f'\t\t\t<Attributes visible="1" expanded="0" order="{max(orders) + 1}"/>\r\n'
                   f'\t\t</Section>\r\n')
        anchor = '\t</Attributes>\r\n\t<Attributes x:id="layoutSettings"'
        if anchor in console:
            console = console.replace(anchor, section + anchor)
        list_anchor = '\t\t\t</List>\r\n\t\t</ChannelShowHidePreset>'
        console = console.replace(
            list_anchor, f'\t\t\t\t<UID uid="{new_uid}"/>\r\n' + list_anchor)
        if "</NotepadData>" in notepad:
            notepad = notepad.replace(
                "</NotepadData>",
                f'\t<NotepadItem id="{new_uid}" title="{ch.label}" text=""/>\r\n</NotepadData>')

        # 3f) Presets/Envelopes 라벨 폴더 복사 (덮어쓰기: 대상의 기존 entry 교체)
        _copy_channel_files(src, dst, ch.label, result)

    # 4) 유입 라우팅 재배선 (덮어쓴 채널로 들어오던 dst 채널들의 destination)
    for old_uid, new_uid in inbound_rewire.items():
        dst_mixer = dst_mixer.replace(f'objectID="{old_uid}/', f'objectID="{new_uid}/')

    # 4b) 버스 오토메이션(S3b): 전송된 채널의 AutomationTrack을 song.xml Tracks에 이식
    if src.has(SONG_XML_ENTRY):
        _transfer_automation_tracks(src.read_text(SONG_XML_ENTRY), dst, uid_map,
                                    set(transfer_uids), result)

    # 5) 기록
    dst.replace_text(MIXER, dst_mixer)
    if console:
        dst.replace_text(CONSOLE, console)
    if notepad:
        dst.replace(NOTEPAD, "﻿".encode("utf-8") + notepad.encode("utf-8"))

    # 6) fail-closed 재검증
    new_model = parse_mixer(dst.read_text(MIXER))
    problems = validate(dst, new_model,
                        require_console_for=set(result.new_channel_uids.values()))
    errs = errors_of(problems)
    if errs:
        raise TransferError("전송 후 무결성 실패(fail-closed): "
                            + "; ".join(p.message for p in errs[:5]))
    return result


def replace_insert_chain(src: SongContainer, src_model: MixerModel, src_uid: str,
                         dst: SongContainer, dst_uid: str,
                         bus_uid_map: dict[str, str] | None = None) -> TransferResult:
    """소스 채널의 인서트 체인/세팅을 대상 채널에 이식 (기존 체인 교체).

    bus_uid_map: 같은 배치에서 함께 이식된 버스/FX의 (소스 uid → 대상 신규 uid) 맵.
    지정하면 소스 채널이 그 대상들로 보내던 send만 골라 대상 채널에도 새로 연결한다
    (bulk_apply에서 사용 — 인서트 체인 교체만으로는 send가 이식되지 않는 문제 보완).
    단일 채널 GUI 체인 복사(Ctrl+우클릭)에서는 이 문맥이 없으므로 생략(None)해도 무방.
    """
    result = TransferResult()
    src_by_uid = src_model.by_uid()
    src_ch = src_by_uid[src_uid]
    dst_model = parse_mixer(dst.read_text(MIXER))
    dst_ch = dst_model.by_uid().get(dst_uid)
    if dst_ch is None:
        raise TransferError(f"대상 채널 없음: {dst_uid}")
    safe_label_path(src_ch.label)
    safe_label_path(dst_ch.label)

    src_mixer = src.read_text(MIXER)
    dst_mixer = dst.read_text(MIXER)
    _s, _e, _t, src_block = _find_channel_block(src_mixer, src_uid)
    ds, de, _dt, dst_block = _find_channel_block(dst_mixer, dst_uid)

    dst_block = _carry_over_sends(src_block, dst_block, bus_uid_map or {},
                                  src_ch.label, result)

    ins_re = re.compile(r'<Attributes x:id="Inserts">.*?\r\n\t{4}</Attributes>', re.S)
    src_ins = ins_re.search(src_block)
    dst_ins = ins_re.search(dst_block)  # send 삽입으로 오프셋이 바뀌었을 수 있어 재탐색
    if not src_ins or not dst_ins:
        raise TransferError("Inserts 블록을 찾을 수 없음")
    new_ins = src_ins.group(0)
    # 인서트 내부 uniqueID 재생성 (deviceClassID 보존)
    for m in re.finditer(rf'<UID x:id="uniqueID" uid="({UID_PATTERN})"/>', new_ins):
        new_ins = new_ins.replace(m.group(1), new_guid())
    # presetPath를 대상 라벨 폴더로 치환 + preset 파일 복사
    src_prefix = f"Presets/Channels/{src_ch.label}/"
    dst_prefix = f"Presets/Channels/{dst_ch.label}/"
    # 대상 채널의 기존 preset entry 제거는 하지 않되(원시 보존 원칙), 참조가 교체되므로
    # 고아 폴더는 warning 수준 (uid_refs.orphan-preset-dir와 일관)
    for name in src.names():
        if name.startswith(src_prefix):
            new_name = dst_prefix + name[len(src_prefix):]
            data = src.read_entry(name)
            if dst.has(new_name):
                dst.replace(new_name, data)
            else:
                dst.add(new_name, data, template_name=dst.names()[0])
            result.copied_entries.append(new_name)
    new_ins = new_ins.replace(f'text="{src_prefix}', f'text="{dst_prefix}')

    new_dst_block = dst_block[:dst_ins.start()] + new_ins + dst_block[dst_ins.end():]
    dst_mixer = dst_mixer[:ds] + new_dst_block + dst_mixer[de:]
    dst.replace_text(MIXER, dst_mixer)

    new_model = parse_mixer(dst.read_text(MIXER))
    problems = validate(dst, new_model)
    errs = errors_of(problems)
    if errs:
        raise TransferError("체인 교체 후 무결성 실패: " + "; ".join(p.message for p in errs[:5]))
    result.notes.append(f"{src_ch.label} 체인({len(src_ch.inserts)}개) → {dst_ch.label}")
    return result


MEDIAPOOL = "Song/mediapool.xml"


def _is_media_path_external(clip_url: str, dst_song_path) -> bool:
    """클립 Url이 dst song 파일과 같은 폴더 트리 밖(또는 절대경로 미확인)인지 판정."""
    if not clip_url.startswith("file:///"):
        return True  # 알 수 없는 스킴 — 안전 측에서 경고
    from pathlib import Path as _P
    try:
        clip_path = _P(clip_url[len("file:///"):]).resolve()
        clip_path.relative_to(dst_song_path.resolve().parent)
        return False
    except (ValueError, OSError):
        return True


def _copy_clip_to_mediapool(src_mp: str, dst_mp: str, clip_id: str,
                            dst_song_path, result: TransferResult) -> str:
    """이벤트가 참조하는 AudioClip을 dst mediapool에 이식(신규 삽입 또는 useCount+1).

    미디어 파일 자체 복사는 비범위(계획 명시) — url이 대상 song 폴더 밖이면 경고만 기록.
    """
    clip_m = re.search(rf'<AudioClip\b[^>]*mediaID="{re.escape(clip_id)}".*?</AudioClip>',
                       src_mp, re.S)
    if not clip_m:
        result.notes.append(f"경고: mediapool에서 클립 정보를 찾지 못함(clipID={clip_id})")
        return dst_mp
    clip_block = clip_m.group(0)
    url_m = re.search(r'<Url x:id="path"[^>]*url="([^"]+)"', clip_block)
    if url_m and _is_media_path_external(url_m.group(1), dst_song_path):
        result.notes.append(
            f"경고: 이벤트 클립의 미디어 경로가 대상 song 폴더 밖입니다 — "
            f"파일이 없으면 열 때 미싱 미디어로 표시될 수 있음: {url_m.group(1)}")
    existing_m = re.search(rf'<AudioClip mediaID="{re.escape(clip_id)}" useCount="(\d+)"', dst_mp)
    if existing_m:
        old_count = int(existing_m.group(1))
        return dst_mp.replace(existing_m.group(0),
                              f'<AudioClip mediaID="{clip_id}" useCount="{old_count + 1}"', 1)
    anchor = '<MediaFolder name="Audio">'
    if anchor not in dst_mp:
        result.notes.append("경고: 대상 mediapool에 Audio 폴더가 없어 클립을 추가하지 못함")
        return dst_mp
    return dst_mp.replace(anchor, anchor + "\r\n\t\t\t" + clip_block, 1)


def _find_media_track_block(song_xml: str, channel_uid: str) -> tuple[str, str] | None:
    """channelID가 channel_uid인 MediaTrack 블록을 (원래 trackID, 블록 텍스트)로 반환.

    없으면 None(예: 해당 채널이 트랙 채널이 아니거나 소스에 song.xml Tracks가 없음).
    """
    for m in re.finditer(r"<MediaTrack\b.*?</MediaTrack>", song_xml, re.S):
        block = m.group(0)
        if f'x:id="channelID" uid="{channel_uid}"' in block:
            tid_m = re.search(r'trackID="([^"]+)"', block)
            return (tid_m.group(1) if tid_m else ""), block
    return None


def transfer_track(src: SongContainer, src_model: MixerModel, src_channel_uid: str,
                   dst: SongContainer, include_events: bool = False) -> TransferResult:
    """단일 트랙 채널(AudioTrackChannel)을 대상에 전송 (S4b/S4d, AC-6).

    기본(include_events=False)은 빈 트랙: 채널+인서트 체인+라우팅만 이식하고 song.xml
    Events 리스트는 제거한다. include_events=True(S4d)면 소스 MediaTrack의 Events를
    그대로 유지한다 — 단, 참조된 미디어 파일 자체 복사는 비범위(계획 명시)이므로
    clipID/mediapool 참조가 유효한지는 이 함수가 검사하지 않는다(호출자가 사전 경고).
    RecordUnit(녹음 입력 라우팅)은 소스 전용 하드웨어 참조라 전송하지 않는다
    (v1 채널 COPY의 "입력 없음" 설계 원칙과 동일 — 재배선은 out of scope).
    현재는 덮어쓰기를 지원하지 않는다(동명 채널 존재 시 TransferError).
    """
    result = TransferResult()
    src_by_uid = src_model.by_uid()
    src_ch = src_by_uid.get(src_channel_uid)
    if src_ch is None or src_ch.tag != "AudioTrackChannel":
        raise TransferError(f"트랙 채널이 아님: {src_channel_uid}")
    safe_label_path(src_ch.label)

    if not src.has(SONG_XML_ENTRY):
        raise TransferError("소스에 song.xml이 없음 — 트랙 전송 불가")
    found = _find_media_track_block(src.read_text(SONG_XML_ENTRY), src_channel_uid)
    if found is None:
        raise TransferError(f"소스에 대응하는 MediaTrack이 없음: {src_ch.label}")
    old_track_id, media_block = found

    dst_mixer = dst.read_text(MIXER)
    dst_model = parse_mixer(dst_mixer)
    conflicts = detect_conflicts(src_model, [src_channel_uid], dst, dst_model)
    if conflicts:
        raise TransferError(
            "이름 충돌 — 트랙 전송은 덮어쓰기를 지원하지 않음: "
            + ", ".join(f"{c.label}({c.kind})" for c in conflicts))
    if not dst.has(SONG_XML_ENTRY):
        raise TransferError("대상에 song.xml이 없음 — 트랙 전송 불가")

    console = dst.read_text(CONSOLE) if dst.has(CONSOLE) else ""
    notepad = dst.read_entry(NOTEPAD).decode("utf-8-sig") if dst.has(NOTEPAD) else ""
    src_mixer = src.read_text(MIXER)
    _s, _e, _tag, block = _find_channel_block(src_mixer, src_channel_uid)

    # 1) UID 재생성
    uid_map: dict[str, str] = {}
    for m in re.finditer(rf'<UID x:id="uniqueID" uid="({UID_PATTERN})"/>', block):
        uid_map.setdefault(m.group(1), new_guid())
    new_uid = uid_map[src_channel_uid]

    # 2) 라우팅 종단 결정 (버스 전송과 동일 패턴: 동명 종단 우선, 없으면 메인)
    terminal = None
    if src_ch.destination_name:
        terminal = dst_model.by_label(src_ch.destination_name)
    if terminal is None:
        outs = dst_model.group("AudioOutput")
        terminal = outs[0] if outs else None
    if terminal is None:
        raise TransferError("대상 song에서 라우팅 종단을 찾을 수 없음")

    # 3) 채널 블록 변환
    nb = block
    for old, new in uid_map.items():
        nb = nb.replace(old, new)
    nb = re.sub(
        rf'(<Connection x:id="destination" objectID=")({UID_PATTERN})(/Input" friendlyName=")[^"]*(")',
        lambda m: m.group(1) + terminal.uid + m.group(3) + terminal.label + m.group(4),
        nb, count=1)
    # 입력 라우팅은 소스 전용 하드웨어 참조 — 빈 채널로 전송(재배선은 out of scope)
    nb = re.sub(r'<Attributes x:id="RecordUnit">.*?</Attributes>',
               '<Attributes x:id="RecordUnit"/>', nb, count=1, flags=re.S)

    def clean_sends(m: re.Match) -> str:
        def check(conn: re.Match) -> str:
            result.dropped_sends.append(f"{src_ch.label} send→{conn.group(2)}")
            return ""
        return re.sub(
            rf'\r\n\s*<Connection x:id="destination" objectID="({UID_PATTERN})/Input" friendlyName="([^"]*)"\s*/>',
            check, m.group(0))
    nb = re.sub(r'<Attributes x:id="Sends">.*?</Attributes>', clean_sends, nb, flags=re.S)

    used = _used_channel_names(dst_mixer, "AudioTrack")
    new_name = _next_channel_name(used)
    nb = re.sub(r'name="Channel\d+"', f'name="{new_name}"', nb, count=1)

    dst_mixer, pos = _group_insert_pos(dst_mixer, "AudioTrack")
    dst_mixer = dst_mixer[:pos] + "\r\n\t\t\t" + nb + dst_mixer[pos:]
    result.new_channel_uids[src_channel_uid] = new_uid

    # 4) 동반 entry (버스 전송과 동일 패턴)
    dashless = new_uid.strip("{}").replace("-", "")
    orders = [int(x) for x in re.findall(r'order="(\d+)"', console)] or [0]
    section = (f'\t\t<Section path="{dashless}">\r\n'
               f'\t\t\t<Attributes visible="1" expanded="0" order="{max(orders) + 1}"/>\r\n'
               f'\t\t</Section>\r\n')
    anchor = '\t</Attributes>\r\n\t<Attributes x:id="layoutSettings"'
    if anchor in console:
        console = console.replace(anchor, section + anchor)
    list_anchor = '\t\t\t</List>\r\n\t\t</ChannelShowHidePreset>'
    console = console.replace(
        list_anchor, f'\t\t\t\t<UID uid="{new_uid}"/>\r\n' + list_anchor)
    if "</NotepadData>" in notepad:
        notepad = notepad.replace(
            "</NotepadData>",
            f'\t<NotepadItem id="{new_uid}" title="{src_ch.label}" text=""/>\r\n</NotepadData>')

    # 5) Presets/Envelopes 라벨 폴더 복사
    _copy_channel_files(src, dst, src_ch.label, result)

    # 6) 기록 (mixer/console/notepad)
    dst.replace_text(MIXER, dst_mixer)
    if console:
        dst.replace_text(CONSOLE, console)
    if notepad:
        dst.replace(NOTEPAD, "﻿".encode("utf-8") + notepad.encode("utf-8"))

    # 7) song.xml: 신규 MediaTrack 삽입
    new_track_id = new_guid()
    new_media_block = media_block if include_events else _strip_list(media_block, "Events")
    new_media_block = new_media_block.replace(f'trackID="{old_track_id}"',
                                              f'trackID="{new_track_id}"')
    new_media_block = new_media_block.replace(
        f'<UID x:id="channelID" uid="{src_channel_uid}"/>',
        f'<UID x:id="channelID" uid="{new_uid}"/>')

    dst_song_xml = dst.read_text(SONG_XML_ENTRY)
    max_number = max((t.track_number for t in parse_tracks(dst).media_tracks), default=0)
    new_media_block = re.sub(r'trackNumber="\d+"', f'trackNumber="{max_number + 1}"',
                             new_media_block, count=1)
    _content_start, content_end = _list_content_span(dst_song_xml, "Tracks")
    insert_pos = dst_song_xml.rfind("\r\n", 0, content_end)
    if insert_pos == -1:
        insert_pos = content_end
    dst_song_xml = (dst_song_xml[:insert_pos] + f"\r\n\t\t\t{new_media_block}"
                    + dst_song_xml[insert_pos:])
    dst.replace_text(SONG_XML_ENTRY, dst_song_xml)
    result.notes.append(f"MediaTrack 생성: {src_ch.label} (trackNumber={max_number + 1}"
                        f"{', 이벤트 포함' if include_events else ''})")

    # 7b) 이벤트 포함 모드: 참조된 클립을 mediapool에 이식(+경로 외부 경고)
    if include_events and src.has(MEDIAPOOL) and dst.has(MEDIAPOOL):
        clip_ids = set(re.findall(r'clipID="([^"]+)"', new_media_block))
        if clip_ids:
            src_mp = src.read_text(MEDIAPOOL)
            dst_mp = dst.read_text(MEDIAPOOL)
            for clip_id in clip_ids:
                dst_mp = _copy_clip_to_mediapool(src_mp, dst_mp, clip_id,
                                                 dst.source_path, result)
            dst.replace_text(MEDIAPOOL, dst_mp)

    # 8) fail-closed 재검증
    new_model = parse_mixer(dst.read_text(MIXER))
    problems = validate(dst, new_model, require_console_for={new_uid})
    errs = errors_of(problems)
    if errs:
        raise TransferError("트랙 전송 후 무결성 실패(fail-closed): "
                            + "; ".join(p.message for p in errs[:5]))
    return result
