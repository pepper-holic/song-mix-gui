"""S0.1(b)+(b-2) 최소 변형 쓰기 스파이크.

산출물 3종 (.omc/verify/):
  01-rename-bus.song                — K.BUS 라벨만 "K.BUS RT"로 변경
  02-duplicate-channel-full.song    — CYM.BUS 복제 + 동반 파일(mixerconsole/notepad) 기재
  03-duplicate-channel-mixeronly.song — CYM.BUS 복제, audiomixer.xml에만 기록 (b-2 실험)

원본은 절대 수정하지 않는다. 무수정 entry는 원시 바이트 보존(zipsurgery).
사용: python spikes/mutate_poc.py <원본.song> <출력디렉토리>
"""
import hashlib
import re
import sys
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from zipsurgery import SongZip

MIXER = "Devices/audiomixer.xml"
CONSOLE = "Devices/mixerconsole.xml"
NOTEPAD = "notepad.xml"


def new_guid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def read_entry(song: Path, name: str) -> bytes:
    with zipfile.ZipFile(song) as zf:
        return zf.read(name)


def find_channel_block(mixer: str, label: str) -> tuple[int, int, str]:
    """label을 가진 AudioGroupChannel 블록의 (시작, 끝, 텍스트). 파일은 CRLF."""
    for m in re.finditer(r'<AudioGroupChannel\b.*?</AudioGroupChannel>', mixer, re.S):
        if f'label="{label}"' in m.group(0)[:400]:
            return m.start(), m.end(), m.group(0)
    raise ValueError(f"channel not found: {label}")


def mutation_rename(src: Path, out: Path) -> None:
    sz = SongZip.read(src)
    mixer = read_entry(src, MIXER).decode("utf-8")
    assert mixer.count('label="K.BUS"') == 1
    sz.replace(MIXER, mixer.replace('label="K.BUS"', 'label="K.BUS RT"').encode("utf-8"))
    sz.write(out)


def build_duplicate(src: Path) -> tuple[str, str, str]:
    """CYM.BUS 복제 블록이 삽입된 새 audiomixer 텍스트와 (새 채널 UID, 새 preset 경로)."""
    mixer = read_entry(src, MIXER).decode("utf-8")
    start, end, block = find_channel_block(mixer, "CYM.BUS")

    # 모든 uniqueID 계열 UID 재생성 (deviceClassID/classID는 보존)
    new_block = block
    uid_map: dict[str, str] = {}
    for m in re.finditer(r'<UID x:id="uniqueID" uid="(\{[0-9A-F-]{36}\})"/>', block):
        old = m.group(1)
        if old not in uid_map:
            uid_map[old] = new_guid()
    for old, new in uid_map.items():
        new_block = new_block.replace(old, new)

    channel_uid_old = re.search(
        r'<UID x:id="uniqueID" uid="(\{[0-9A-F-]{36}\})"/>', block).group(1)
    channel_uid_new = uid_map[channel_uid_old]

    # 그룹 내 유일한 name, 새 라벨
    new_block = new_block.replace('name="Channel04"', 'name="Channel10"', 1)
    new_block = new_block.replace('label="CYM.BUS"', 'label="CYM.BUS COPY"', 1)

    # presetPath를 새 라벨 폴더로
    old_preset = "Presets/Channels/CYM.BUS/1 - Pro-Q 3 C.B.vstpreset"
    new_preset = "Presets/Channels/CYM.BUS COPY/1 - Pro-Q 3 C.B.vstpreset"
    assert old_preset in new_block
    new_block = new_block.replace(old_preset, new_preset)

    new_mixer = mixer[:end] + "\r\n\t\t\t" + new_block + mixer[end:]
    return new_mixer, channel_uid_new, new_preset


def add_companions(src: Path, sz: SongZip, channel_uid: str, label: str) -> None:
    console = read_entry(src, CONSOLE).decode("utf-8")
    dashless = channel_uid.strip("{}").replace("-", "")
    orders = [int(m.group(1)) for m in re.finditer(r'order="(\d+)"', console)]
    section = (f'\t\t<Section path="{dashless}">\r\n'
               f'\t\t\t<Attributes visible="1" expanded="0" order="{max(orders) + 1}"/>\r\n'
               f'\t\t</Section>\r\n')
    anchor = '\t</Attributes>\r\n\t<Attributes x:id="layoutSettings"'
    assert anchor in console
    console = console.replace(anchor, section + anchor)
    # ScreenBank/RemoteBank visible 리스트에 추가
    list_anchor = '\t\t\t</List>\r\n\t\t</ChannelShowHidePreset>'
    assert console.count(list_anchor) == 2
    console = console.replace(list_anchor,
                              f'\t\t\t\t<UID uid="{channel_uid}"/>\r\n' + list_anchor)
    sz.replace(CONSOLE, console.encode("utf-8"))

    notepad = read_entry(src, NOTEPAD).decode("utf-8-sig")
    item = f'\t<NotepadItem id="{channel_uid}" title="{label}" text=""/>\r\n'
    assert "</NotepadData>" in notepad
    notepad = notepad.replace("</NotepadData>", item + "</NotepadData>")
    sz.replace(NOTEPAD, "﻿".encode("utf-8") + notepad.encode("utf-8"))


def mutation_duplicate(src: Path, out: Path, with_companions: bool) -> None:
    sz = SongZip.read(src)
    new_mixer, channel_uid, new_preset = build_duplicate(src)
    sz.replace(MIXER, new_mixer.encode("utf-8"))
    old_preset = "Presets/Channels/CYM.BUS/1 - Pro-Q 3 C.B.vstpreset"
    sz.add(new_preset, read_entry(src, old_preset), template_name=old_preset,
           after=old_preset)
    if with_companions:
        add_companions(src, sz, channel_uid, "CYM.BUS COPY")
    sz.write(out)


def verify_untouched_entries(src: Path, dst: Path, expected_changed: set[str]) -> list[str]:
    problems = []
    with zipfile.ZipFile(src) as za, zipfile.ZipFile(dst) as zb:
        for name in za.namelist():
            a, b = za.read(name), zb.read(name)
            if name in expected_changed:
                if a == b:
                    problems.append(f"{name}: 변경 예정이었으나 동일")
            elif a != b:
                problems.append(f"{name}: 의도치 않은 변경")
        extra = set(zb.namelist()) - set(za.namelist())
        expected_extra = {n for n in expected_changed if n not in za.namelist()}
        if extra != expected_extra:
            problems.append(f"신규 entry 불일치: {extra} != {expected_extra}")
        # zip 무결성
        if zb.testzip() is not None:
            problems.append("zip CRC 불합격")
    return problems


def main() -> int:
    src = Path(sys.argv[1])
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    before = hashlib.md5(src.read_bytes()).hexdigest()

    jobs = [
        ("01-rename-bus.song", lambda o: mutation_rename(src, o), {MIXER}),
        ("02-duplicate-channel-full.song",
         lambda o: mutation_duplicate(src, o, True),
         {MIXER, CONSOLE, NOTEPAD, "Presets/Channels/CYM.BUS COPY/1 - Pro-Q 3 C.B.vstpreset"}),
        ("03-duplicate-channel-mixeronly.song",
         lambda o: mutation_duplicate(src, o, False),
         {MIXER, "Presets/Channels/CYM.BUS COPY/1 - Pro-Q 3 C.B.vstpreset"}),
    ]
    fail = False
    for fname, fn, changed in jobs:
        out = outdir / fname
        fn(out)
        problems = verify_untouched_entries(src, out, changed)
        status = "PASS" if not problems else "FAIL"
        fail |= bool(problems)
        print(f"{fname}: {status}")
        for p in problems:
            print("  -", p)

    after = hashlib.md5(src.read_bytes()).hexdigest()
    print(f"original untouched: {before == after}")
    return 1 if (fail or before != after) else 0


if __name__ == "__main__":
    sys.exit(main())
