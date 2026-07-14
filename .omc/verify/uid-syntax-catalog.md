# UID 참조 문법 카탈로그 (S0.1(b-3))

- 소스: `C:\Users\yhkze\Documents\Studio Pro\Songs\NAIITE_EP\naiite_14\naiite_14.song`
- 채널 수: 33

## 채널 UID 목록

| 태그 | 라벨 | UID |
|---|---|---|
| AudioInputChannel | 입력 L+R | `{BE06072A-9254-414A-A16C-7C3D51EAAA09}` |
| AudioInputChannel | 입력 L | `{E20AFF6F-7795-4E1F-BF01-3268A31F3526}` |
| AudioInputChannel | 입력 R | `{521E0F46-541D-4ADD-81DB-01E49C5A93F8}` |
| AudioOutputChannel | 메인 | `{0B817B30-0B67-449C-A8D4-9C39E1F5185D}` |
| AudioTrackChannel | bass | `{A75B03A1-5951-4D06-81EF-56E2143FB17D}` |
| AudioTrackChannel | guitar dud | `{1357DA61-A6CE-46AD-B652-3F99ABC4AD1D}` |
| AudioTrackChannel | guitar | `{AB01A55D-CD1D-4B98-88EE-683ACDDD0352}` |
| AudioTrackChannel | HI HAT | `{2E8F63DD-4AFB-4960-A66A-967EA8BDFC7A}` |
| AudioTrackChannel | kick out | `{A4F85CCD-6C62-4145-9187-03C58A2B71B5}` |
| AudioTrackChannel | kick | `{95A18FF1-10A7-4EFB-AB95-EB2E8E0D2672}` |
| AudioTrackChannel | OVER L | `{0A38CC4F-CFED-4B81-8D2F-746F10BB5915}` |
| AudioTrackChannel | OVER R | `{2F711B67-C039-4C56-91D0-D7B7BA45FF21}` |
| AudioTrackChannel | RIDE | `{791DA8DE-43B4-44F6-A54C-E37040E30A58}` |
| AudioTrackChannel | SN B | `{B694C1C8-6983-4EFB-A566-D64823E368EE}` |
| AudioTrackChannel | SN T | `{A67F73BB-D340-4957-B2C8-B08C4D8CE90A}` |
| AudioTrackChannel | TOM F | `{9DB57DD6-8C2A-40B8-8F8D-E990A14431D4}` |
| AudioTrackChannel | TOM M | `{0D1FBA1E-C8E1-45D2-9C32-B96132634120}` |
| AudioTrackChannel | TOM S | `{5A618BED-1121-4B57-BDCB-01C578BC466A}` |
| AudioTrackChannel | bass 2 | `{3335ECD4-5358-443C-87B5-FC64563FC0EB}` |
| AudioTrackChannel | The Kill - Make &apos;Em Suffer (2012) Full Album HQ (Grindcore) | `{B30EB9C6-ACC0-49FA-970B-84988C90965F}` |
| AudioTrackChannel | SN T 2 | `{43A81524-DD6A-4DAE-B91B-A20CE263C516}` |
| AudioTrackChannel | vox | `{3380E327-576C-4209-B35D-AC94C82E4AF1}` |
| AudioTrackChannel | SN T 3 | `{1C6B7BFF-B6FE-4364-B64E-861B79E26A3B}` |
| AudioGroupChannel | K.BUS | `{5496AF91-0BE5-402C-914F-663C21E37C8C}` |
| AudioGroupChannel | S.BUS | `{7AEF0C5E-EB34-4154-A665-BA83580E883D}` |
| AudioGroupChannel | T.BUS | `{233A6A9F-74C9-40FB-A963-DDCE1EF10C12}` |
| AudioGroupChannel | CYM.BUS | `{DA135823-E87E-4D04-9FE3-D8C4E12FA785}` |
| AudioGroupChannel | DR.B | `{9F3D103A-DB25-4F36-A270-E810C3AE5D47}` |
| AudioGroupChannel | GT.B | `{C50694B1-0EED-4F53-88FB-F97328ADC50F}` |
| AudioGroupChannel | BASS.B | `{7249DE44-E4B1-4BC8-8228-C4F5423E99FC}` |
| AudioGroupChannel | MIXOUT | `{1A082A8E-F03C-4579-A4E3-095C2EAA078E}` |
| AudioGroupChannel | DR Parallel | `{CB2FF5C4-6662-4F15-A2B5-B63B5DDE0CFA}` |
| AudioEffectChannel | FX 1 | `{6C7B8872-21F3-4745-AF84-7A0462C9F793}` |

## entry별 참조 형태

### `Devices/audioiomanager.xml`
- **`PortAssignment name="{G}"`** — 4회, 대상 UID 4종
  - 예: `<PortAssignment name="{BE06072A-9254-414A-A16C-7C3D51EAAA09}">`
- **`previewChannel="{G}"`** — 1회, 대상 UID 1종
  - 예: `<AudioIOManager previewChannel="{0B817B30-0B67-449C-A8D4-9C39E1F5185D}">`

### `Devices/audiomixer.xml`
- **`id="{G}"`** — 33회, 대상 UID 33종
  - 예: `<UID x:id="uniqueID" uid="{BE06072A-9254-414A-A16C-7C3D51EAAA09}"/>`
- **`objectID="{G}/Input"`** — 31회, 대상 UID 11종
  - 예: `<Connection x:id="destination" objectID="{0B817B30-0B67-449C-A8D4-9C39E1F5185D}/Input" friendlyName="메인"/>`
- **`objectID="{G}/Output"`** — 19회, 대상 UID 1종
  - 예: `<Connection x:id="recordPort" objectID="{E20AFF6F-7795-4E1F-BF01-3268A31F3526}/Output" friendlyName="입력 L">`
- **`uid="{G}"`** — 33회, 대상 UID 33종
  - 예: `<UID x:id="uniqueID" uid="{BE06072A-9254-414A-A16C-7C3D51EAAA09}"/>`

### `Devices/mixerconsole.xml`
- **`id="{G}"`** — 58회, 대상 UID 29종
  - 예: `<UID uid="{A75B03A1-5951-4D06-81EF-56E2143FB17D}"/>`
- **`path="HEX32"`** — 33회, 대상 UID 33종
  - 예: `<Section path="BE06072A9254414AA16C7C3D51EAAA09">`
- **`uid="{G}"`** — 58회, 대상 UID 29종
  - 예: `<UID uid="{A75B03A1-5951-4D06-81EF-56E2143FB17D}"/>`

### `Song/song.xml`
- **`id="{G}"`** — 19회, 대상 UID 19종
  - 예: `<UID x:id="channelID" uid="{A75B03A1-5951-4D06-81EF-56E2143FB17D}"/>`
- **`param:///AudioMixer/{G}/…`** — 40회, 대상 UID 21종
  - 예: `<AutomationRegion title="볼륨" identity="param:///AudioMixer/{A75B03A1-5951-4D06-81EF-56E2143FB17D}/volume"`
- **`uid="{G}"`** — 19회, 대상 UID 19종
  - 예: `<UID x:id="channelID" uid="{A75B03A1-5951-4D06-81EF-56E2143FB17D}"/>`

### `Workspace/perspective.xml`
- **`windowID="HEX32…"`** — 5회, 대상 UID 5종
  - 예: `<FrameItem::ViewState windowID="A4F85CCD6C624145918703C58A2B71B5.o" W="820" H="492" X="830" Y="389"`
- **`…HEX32… (경로/복합 문자열 내 포함)`** — 23회, 대상 UID 23종
  - 예: `<Section path="Console47EditorZone47PrePostInserts0B817B300B67449CA8D49C39E1F5185D">`

### `notepad.xml`
- **`id="{G}"`** — 12회, 대상 UID 12종
  - 예: `<NotepadItem id="{BE06072A-9254-414A-A16C-7C3D51EAAA09}" title="입력 L+R" text=""/>`

### `settings.xml`
- **`outputList="{G}"`** — 1회, 대상 UID 1종
  - 예: `<Attributes markerIndex="0" outputList="{0B817B30-0B67-449C-A8D4-9C39E1F5185D}" fileName="naiite_14_w_vox">`

## Open Question 3 판정 (settings/editor/perspective)
- `settings.xml`: 채널 UID 참조 있음
- `Song/editor.xml`: 채널 UID 참조 없음 (순수 워크스페이스 상태로 판정)
- `Workspace/perspective.xml`: 채널 UID 참조 있음