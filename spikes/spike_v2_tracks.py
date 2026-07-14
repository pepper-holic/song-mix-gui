"""Phase 0-S 스파이크 — song.xml 신규 쓰기 축(AutomationTrack/MediaTrack) 최소 변형 파일 3종.

산출물 (.omc/verify/):
  05-automation-transfer.song   — naiite_14 S.BUS 볼륨 오토메이션을 대상의 DR BUS에 수동 이식
  06-track-transfer-empty.song  — 빈 MediaTrack + AudioTrackChannel 신규(이벤트 없음)
  07-track-transfer-events.song — 06 + Events List(기존 클립 참조 AudioEvent 1개)

원본 코퍼스는 절대 수정하지 않는다. 무수정 zip entry는 원시 바이트 보존(zipsurgery).
XML은 텍스트 수술만 — DOM 재직렬화 금지. CRLF/들여쓰기/BOM 보존.

사용: python spikes/spike_v2_tracks.py
"""
import re
import sys
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from zipsurgery import SongZip  # noqa: E402

SONGS = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")
SRC = SONGS / "NAIITE_EP" / "naiite_14" / "naiite_14.song"
TGT = SONGS / "NAIITE_HWA_SPLIT" / "sp_hwa_14" / "sp_hwa_14 (fixed).song"
OUT = Path(__file__).resolve().parent.parent / ".omc" / "verify"

MIXER = "Devices/audiomixer.xml"
CONSOLE = "Devices/mixerconsole.xml"
NOTEPAD = "notepad.xml"
SONGXML = "Song/song.xml"
MEDIAPOOL = "Song/mediapool.xml"
UID_RE = r"\{[0-9A-F-]{36}\}"


def new_guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def read_entry(song: Path, name: str) -> bytes:
    with zipfile.ZipFile(song) as zf:
        return zf.read(name)


def read_text_bom(song: Path, name: str) -> tuple[str, bytes]:
    """(text, bom) — BOM을 분리해 반환. 쓰기 시 bom+text.encode('utf-8')로 복원."""
    raw = read_entry(song, name)
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), b"\xef\xbb\xbf"
    return raw.decode("utf-8"), b""


def label_uid(mixer: str, tag: str, label: str) -> str:
    """audiomixer에서 tag/label로 채널 블록을 찾아 uniqueID를 반환."""
    for m in re.finditer(rf"<{tag}\b.*?</{tag}>", mixer, re.S):
        if f'label="{label}"' in m.group(0)[:400]:
            uid = re.search(rf'<UID x:id="uniqueID" uid="({UID_RE})"/>', m.group(0))
            return uid.group(1)
    raise ValueError(f"channel not found: {tag} {label}")


def channel_block(mixer: str, tag: str, label: str) -> str:
    for m in re.finditer(rf"<{tag}\b.*?</{tag}>", mixer, re.S):
        if f'label="{label}"' in m.group(0)[:400]:
            return m.group(0)
    raise ValueError(f"channel block not found: {tag} {label}")


def media_track_block(song: str, name: str) -> str:
    for m in re.finditer(r"<MediaTrack\b.*?</MediaTrack>", song, re.S):
        if f'name="{name}"' in m.group(0)[:400]:
            return m.group(0)
    raise ValueError(f"MediaTrack not found: {name}")


def next_channel_name(mixer: str) -> str:
    used = {int(x) for x in re.findall(r'name="Channel(\d+)"', mixer)}
    n = 1
    while n in used:
        n += 1
    return f"Channel{n:02d}"


def insert_before_tracks_close(song: str, block: str) -> str:
    """Tracks List의 닫는 태그(</MediaTrack>\\r\\n\\t\\t</List>) 앞에 트랙 블록 삽입."""
    launcher = song.find('<Attributes x:id="launcher"')
    close = song.rfind("\r\n\t\t</List>", 0, launcher)
    if close == -1:
        raise ValueError("Tracks List 닫는 태그를 찾을 수 없음")
    return song[:close] + "\r\n\t\t\t" + block + song[close:]


def insert_after_channel(mixer: str, tag: str, label: str, block: str) -> str:
    """지정 채널 블록의 </tag> 직후에 새 채널 블록 삽입 (같은 그룹 내, 들여쓰기 보존)."""
    anchor_block = channel_block(mixer, tag, label)
    idx = mixer.find(anchor_block) + len(anchor_block)
    return mixer[:idx] + "\r\n\t\t\t" + block + mixer[idx:]


def add_channel_companions(sz: SongZip, tgt: Path, channel_uid: str, label: str) -> None:
    """mixerconsole Section + ScreenBank/RemoteBank UID + notepad 항목 추가 (v1 02-spike 방식)."""
    console, cbom = read_text_bom(tgt, CONSOLE)
    dashless = channel_uid.strip("{}").replace("-", "")
    orders = [int(m.group(1)) for m in re.finditer(r'order="(\d+)"', console)]
    section = (f'\t\t<Section path="{dashless}">\r\n'
               f'\t\t\t<Attributes visible="1" expanded="0" order="{max(orders) + 1}"/>\r\n'
               f'\t\t</Section>\r\n')
    anchor = '\t</Attributes>\r\n\t<Attributes x:id="layoutSettings"'
    assert anchor in console, "console layoutSettings anchor 없음"
    console = console.replace(anchor, section + anchor)
    list_anchor = '\t\t\t</List>\r\n\t\t</ChannelShowHidePreset>'
    assert console.count(list_anchor) == 2, "ChannelShowHidePreset anchor 수 불일치"
    console = console.replace(list_anchor,
                              f'\t\t\t\t<UID uid="{channel_uid}"/>\r\n' + list_anchor)
    sz.replace(CONSOLE, cbom + console.encode("utf-8"))

    notepad, nbom = read_text_bom(tgt, NOTEPAD)
    item = f'\t<NotepadItem id="{channel_uid}" title="{label}" text=""/>\r\n'
    assert "</NotepadData>" in notepad
    notepad = notepad.replace("</NotepadData>", item + "</NotepadData>")
    sz.replace(NOTEPAD, nbom + notepad.encode("utf-8"))


def copy_entries(sz: SongZip, src: Path, prefix: str, new_prefix: str) -> list[str]:
    """src의 prefix 하위 entry들을 new_prefix로 대상에 추가(원시 바이트). 추가된 이름 목록 반환."""
    tmpl = sz.entries[0].name
    added = []
    with zipfile.ZipFile(src) as zf:
        for info in zf.infolist():
            if not info.filename.startswith(prefix):
                continue
            new_name = new_prefix + info.filename[len(prefix):]
            comp = zipfile.ZIP_STORED if info.compress_type == 0 else zipfile.ZIP_DEFLATED
            sz.add(new_name, zf.read(info.filename), template_name=tmpl, compress_type=comp)
            added.append(new_name)
    return added


# ---------------------------------------------------------------------------
# 05 — 오토메이션 전송 (S3a)
# ---------------------------------------------------------------------------
def build_05(out: Path) -> dict:
    src_song, _ = read_text_bom(SRC, SONGXML)
    tgt_song, sbom = read_text_bom(TGT, SONGXML)
    tgt_mixer, _ = read_text_bom(TGT, MIXER)

    block = re.search(r'<AutomationTrack\b[^>]*name="S\.BUS">.*?</AutomationTrack>',
                      src_song, re.S).group(0)
    src_uid = re.search(rf'param:///AudioMixer/({UID_RE})/', block).group(1)
    dst_uid = label_uid(tgt_mixer, "AudioGroupChannel", "DR BUS")
    new_track_id = new_guid()

    nb = block
    nb = re.sub(r'trackID="' + UID_RE + '"', f'trackID="{new_track_id}"', nb, count=1)
    nb = nb.replace(f'param:///AudioMixer/{src_uid}/', f'param:///AudioMixer/{dst_uid}/')
    nb = nb.replace('name="S.BUS">', 'name="DR BUS vol (spike)">', 1)

    assert dst_uid in nb and src_uid not in nb, "param UID 재매핑 실패"
    new_song = insert_before_tracks_close(tgt_song, nb)

    sz = SongZip.read(TGT)
    sz.replace(SONGXML, sbom + new_song.encode("utf-8"))
    env = "Envelopes/S.BUS/볼륨.envelopex"
    added = copy_entries(sz, SRC, env, env)
    assert added == [env], f"envelope 복사 불일치: {added}"
    sz.write(out)
    return {"changed": {SONGXML, env}, "src_uid": src_uid, "dst_uid": dst_uid,
            "track_id": new_track_id, "envelope": env}


# ---------------------------------------------------------------------------
# 06 — 빈 트랙 (S4a)
# ---------------------------------------------------------------------------
def _build_track(out: Path, label: str, with_events: bool) -> dict:
    tgt_song, sbom = read_text_bom(TGT, SONGXML)
    tgt_mixer, mbom = read_text_bom(TGT, MIXER)

    tomf_ch = channel_block(tgt_mixer, "AudioTrackChannel", "1 - TOM F")
    tomf_uid = re.search(rf'<UID x:id="uniqueID" uid="({UID_RE})"/>', tomf_ch).group(1)
    mt = media_track_block(tgt_song, "1 - TOM F")

    new_ch_uid = new_guid()
    new_track_id = new_guid()
    max_tn = max(int(x) for x in re.findall(r'trackNumber="(\d+)"', tgt_song))
    new_tn = max_tn + 1
    chan_name = next_channel_name(tgt_mixer)

    # --- AudioTrackChannel: 모든 uniqueID 재생성, name/label/uid 갱신 ---
    nb_ch = tomf_ch
    uid_map: dict[str, str] = {}
    for m in re.finditer(rf'<UID x:id="uniqueID" uid="({UID_RE})"/>', tomf_ch):
        uid_map.setdefault(m.group(1), new_ch_uid if m.group(1) == tomf_uid else new_guid())
    for old, new in uid_map.items():
        nb_ch = nb_ch.replace(old, new)
    nb_ch = nb_ch.replace('name="Channel13"', f'name="{chan_name}"', 1)
    nb_ch = nb_ch.replace('label="1 - TOM F"', f'label="{label}"', 1)

    # --- MediaTrack: trackID/trackNumber/channelID/name/오토메이션 param/Url 갱신 ---
    nb_mt = mt
    nb_mt = re.sub(r'trackID="' + UID_RE + '"', f'trackID="{new_track_id}"', nb_mt, count=1)
    nb_mt = re.sub(r'trackNumber="\d+"', f'trackNumber="{new_tn}"', nb_mt, count=1)
    nb_mt = nb_mt.replace(tomf_uid, new_ch_uid)  # channelID + AutomationRegion identity
    nb_mt = nb_mt.replace('name="1 - TOM F"', f'name="{label}"', 1)
    nb_mt = nb_mt.replace("Envelopes/1 - TOM F/", f"Envelopes/{label}/")

    events_note = "없음(빈 트랙)"
    clip_url = None
    mediapool_bumped = False
    if with_events:
        src_song_full, _ = read_text_bom(TGT, SONGXML)
        kick_mt = media_track_block(src_song_full, "1 - kick")
        events = re.search(r'<List x:id="Events">.*?</List>', kick_mt, re.S).group(0)
        clip_id = re.search(r'clipID="(' + UID_RE + ')"', events).group(1)
        # height Attributes 뒤(=MediaTrack 마지막 자식)로 Events List 삽입
        close = nb_mt.rfind("\r\n\t\t\t</MediaTrack>")
        nb_mt = nb_mt[:close] + "\r\n\t\t\t\t" + events + nb_mt[close:]
        events_note = f"AudioEvent 1개 → clipID {clip_id} (기존 클립 재사용)"

    new_song = insert_before_tracks_close(tgt_song, nb_mt)
    new_mixer = insert_after_channel(tgt_mixer, "AudioTrackChannel", "1 - TOM F", nb_ch)

    sz = SongZip.read(TGT)
    sz.replace(SONGXML, sbom + new_song.encode("utf-8"))
    sz.replace(MIXER, mbom + new_mixer.encode("utf-8"))
    changed = {SONGXML, MIXER, CONSOLE, NOTEPAD}
    add_channel_companions(sz, TGT, new_ch_uid, label)

    added = copy_entries(sz, TGT, "Envelopes/1 - TOM F/", f"Envelopes/{label}/")
    changed |= set(added)

    if with_events:
        pool, pbom = read_text_bom(TGT, MEDIAPOOL)
        clip_id = re.search(r'clipID="(' + UID_RE + ')"',
                            re.search(r'<List x:id="Events">.*?</List>',
                                      media_track_block(tgt_song, "1 - kick"), re.S).group(0)).group(1)
        clip_decl = re.search(r'<AudioClip mediaID="' + re.escape(clip_id) + r'" useCount="(\d+)"',
                              pool)
        old_uc = clip_decl.group(1)
        new_uc = str(int(old_uc) + 1)
        pool = pool.replace(
            f'mediaID="{clip_id}" useCount="{old_uc}"',
            f'mediaID="{clip_id}" useCount="{new_uc}"', 1)
        sz.replace(MEDIAPOOL, pbom + pool.encode("utf-8"))
        changed.add(MEDIAPOOL)
        mediapool_bumped = True
        url = re.search(r'mediaID="' + re.escape(clip_id) + r'".*?<Url x:id="path"[^>]*url="([^"]*)"',
                        pool, re.S).group(1)
        clip_url = url

    sz.write(out)
    return {"changed": changed, "channel_uid": new_ch_uid, "track_id": new_track_id,
            "track_number": new_tn, "label": label, "events": events_note,
            "clip_url": clip_url, "mediapool_bumped": mediapool_bumped,
            "envelopes": added}


def build_06(out: Path) -> dict:
    return _build_track(out, "NEW TRK", with_events=False)


def build_07(out: Path) -> dict:
    return _build_track(out, "NEW TRK EV", with_events=True)


# ---------------------------------------------------------------------------
# 검증
# ---------------------------------------------------------------------------
def _wellformed(song: Path, name: str) -> bool:
    """x: 접두사 xmlns 주입 후 파싱(읽기 전용 유효성 확인). 재직렬화하지 않음."""
    import xml.etree.ElementTree as ET
    txt = read_entry(song, name).decode("utf-8-sig")
    # 루트 시작 태그에 xmlns:x 선언 주입 (song.xml 등은 미선언)
    txt = re.sub(r"^(<\?xml[^>]*\?>\s*)?<(\w+)",
                 lambda m: (m.group(1) or "") + f'<{m.group(2)} xmlns:x="urn:x"',
                 txt, count=1)
    try:
        ET.fromstring(txt)
        return True
    except ET.ParseError as e:
        print(f"    XML parse FAIL {name}: {e}")
        return False


def verify(src_untouched: Path, out: Path, changed: set[str]) -> list[str]:
    problems: list[str] = []
    with zipfile.ZipFile(src_untouched) as za, zipfile.ZipFile(out) as zb:
        na, nb = set(za.namelist()), set(zb.namelist())
        for name in na:
            a, b = za.read(name), zb.read(name)
            if name in changed:
                if a == b:
                    problems.append(f"{name}: 변경 예정이나 동일")
            elif a != b:
                problems.append(f"{name}: 의도치 않은 변경")
        new_expected = {n for n in changed if n not in na}
        if (nb - na) != new_expected:
            problems.append(f"신규 entry 불일치: {nb - na} != {new_expected}")
        if zb.testzip() is not None:
            problems.append("zip CRC 불합격")
    for xml in (SONGXML, MIXER, MEDIAPOOL, NOTEPAD, CONSOLE):
        if xml in zipfile.ZipFile(out).namelist():
            if not _wellformed(out, xml):
                problems.append(f"{xml}: XML 파싱 실패")
    return problems


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("05-automation-transfer.song", build_05),
        ("06-track-transfer-empty.song", build_06),
        ("07-track-transfer-events.song", build_07),
    ]
    fail = False
    for fname, fn in jobs:
        outp = OUT / fname
        info = fn(outp)
        problems = verify(TGT, outp, info["changed"])
        status = "PASS" if not problems else "FAIL"
        fail |= bool(problems)
        print(f"\n=== {fname}: {status} ===")
        for k, v in info.items():
            if k != "changed":
                print(f"  {k}: {v}")
        print(f"  changed entries: {sorted(info['changed'])}")
        for p in problems:
            print("  ! ", p)
    # 원본 불변 확인
    import hashlib
    for p in (SRC, TGT):
        print(f"\noriginal untouched {p.name}: exists={p.exists()} "
              f"md5={hashlib.md5(p.read_bytes()).hexdigest()[:8]}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
