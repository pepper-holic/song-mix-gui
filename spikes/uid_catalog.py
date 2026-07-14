"""S0.1(b-3) UID 참조 문법 카탈로그 생성기.

audiomixer.xml의 모든 채널 UID를 추출한 뒤, zip 내 전 entry에서
braced GUID / dash-less hex 두 표기로 등장 위치를 전수 스캔해
문법 형태별 카탈로그를 마크다운으로 산출한다.

사용: python spikes/uid_catalog.py <song 경로> <출력.md>
"""
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

CHANNEL_RE = re.compile(
    r'<(?P<tag>Audio(?:Input|Output|Track|Group|Effect)Channel)\b(?P<attrs>.*?)>'
    r'(?P<body>.*?)</(?P=tag)>', re.S)
LABEL_RE = re.compile(r'label="(?P<label>[^"]*)"')
UID_RE = re.compile(r'<UID x:id="uniqueID" uid="\{(?P<uid>[0-9A-F-]{36})\}"/>')


def channel_uids(mixer_xml: str) -> list[tuple[str, str, str]]:
    """(태그, 라벨, UID) 목록 — 채널 최상위 uniqueID만."""
    out = []
    for m in CHANNEL_RE.finditer(mixer_xml):
        label_m = LABEL_RE.search(m.group("attrs"))
        uid_m = UID_RE.search(m.group("body"))
        if uid_m:
            out.append((m.group("tag"), label_m.group("label") if label_m else "?",
                        uid_m.group("uid")))
    return out


def classify(line: str, uid: str, dashless: str) -> set[str]:
    forms = set()
    if f'uid="{{{uid}}}"' in line:
        forms.add('uid="{G}"')
    if f'objectID="{{{uid}}}/' in line:
        m = re.search(r'objectID="\{' + re.escape(uid) + r'\}/(\w+)"', line)
        forms.add(f'objectID="{{G}}/{m.group(1) if m else "?"}"')
    if f'id="{{{uid}}}"' in line and 'objectID' not in line:
        forms.add('id="{G}"')
    if f'trackID="{{{uid}}}"' in line:
        forms.add('trackID="{G}"')
    if f'trackId="{{{uid}}}"' in line:
        forms.add('trackId="{G}"')
    if f'/AudioMixer/{{{uid}}}/' in line:
        forms.add('param:///AudioMixer/{G}/…')
    if f'outputList="{{{uid}}}"' in line:
        forms.add('outputList="{G}"')
    if f'previewChannel="{{{uid}}}"' in line:
        forms.add('previewChannel="{G}"')
    if f'PortAssignment name="{{{uid}}}"' in line:
        forms.add('PortAssignment name="{G}"')
    if dashless in line:
        if f'path="{dashless}"' in line:
            forms.add('path="HEX32"')
        elif f'windowID="{dashless}' in line:
            forms.add('windowID="HEX32…"')
        else:
            forms.add('…HEX32… (경로/복합 문자열 내 포함)')
    if not forms and f'{{{uid}}}' in line:
        forms.add('{G} (기타 컨텍스트)')
    return forms


def main() -> int:
    song = Path(sys.argv[1])
    out_md = Path(sys.argv[2])
    with zipfile.ZipFile(song) as zf:
        texts: dict[str, str] = {}
        for name in zf.namelist():
            raw = zf.read(name)
            try:
                texts[name] = raw.decode("utf-8")
            except UnicodeDecodeError:
                texts[name] = ""  # 바이너리(vstpreset 등)는 별도 처리
        mixer = texts["Devices/audiomixer.xml"]

    chans = channel_uids(mixer)
    # entry → form → [(uid, label, 예시라인)]
    catalog: dict[str, dict[str, list[tuple[str, str, str]]]] = defaultdict(lambda: defaultdict(list))
    for tag, label, uid in chans:
        dashless = uid.replace("-", "")
        for name, text in texts.items():
            if not text:
                continue
            for line in text.splitlines():
                if uid in line or dashless in line:
                    for form in classify(line, uid, dashless):
                        catalog[name][form].append((uid, label, line.strip()[:160]))

    lines = ["# UID 참조 문법 카탈로그 (S0.1(b-3))", "",
             f"- 소스: `{song}`", f"- 채널 수: {len(chans)}", ""]
    lines.append("## 채널 UID 목록")
    lines.append("")
    lines.append("| 태그 | 라벨 | UID |")
    lines.append("|---|---|---|")
    for tag, label, uid in chans:
        lines.append(f"| {tag} | {label} | `{{{uid}}}` |")
    lines.append("")
    lines.append("## entry별 참조 형태")
    lines.append("")
    for name in sorted(catalog):
        lines.append(f"### `{name}`")
        for form, hits in sorted(catalog[name].items()):
            uniq_uids = sorted({u for u, _, _ in hits})
            lines.append(f"- **`{form}`** — {len(hits)}회, 대상 UID {len(uniq_uids)}종")
            lines.append(f"  - 예: `{hits[0][2]}`")
        lines.append("")

    # Open Question 3 판정
    lines.append("## Open Question 3 판정 (settings/editor/perspective)")
    for probe in ["settings.xml", "Song/editor.xml", "Workspace/perspective.xml"]:
        has = probe in catalog and catalog[probe]
        verdict = "채널 UID 참조 있음" if has else "채널 UID 참조 없음 (순수 워크스페이스 상태로 판정)"
        lines.append(f"- `{probe}`: {verdict}")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"catalog written: {out_md} ({len(chans)} channels, {len(catalog)} entries with refs)")
    for name in sorted(catalog):
        print(f"  {name}: {sorted(catalog[name])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
