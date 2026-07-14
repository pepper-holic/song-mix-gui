# 동반 파일 정적 분석 (S0.1(b-2))

naiite_14 실측 기준, 채널/버스 UID가 등장하는 entry와 역할:

| Entry | 참조 형태 | 역할 | 전송 시 처리 |
|---|---|---|---|
| `Devices/audiomixer.xml` | `<UID x:id="uniqueID" uid="{G}"/>`, `Connection objectID="{G}/Input\|Output"` | 채널 정의 본체 + 라우팅 | **필수 작성** |
| `Devices/mixerconsole.xml` | `Section path="HEX32"`(대시 제거 UID), `<UID uid="{G}"/>`(ScreenBank/RemoteBank visible 목록) | 콘솔 표시/순서/뱅크 | S0.1(b-2) 실험으로 필수성 판정 (03 파일) |
| `notepad.xml` | `NotepadItem id="{G}"` | 채널 메모 | 스테일 항목 존재 실측(S.BUS/MIXOUT 구 UID 잔존) → **비필수 추정**, 실험으로 확인 |
| `Song/song.xml` | `UID x:id="channelID" uid="{G}"`(MediaTrack→채널 바인딩), `param:///AudioMixer/{G}/…`(오토메이션 identity), `trackID="{G}"` | 트랙↔채널 연결 | 버스/FX 채널 전송에는 불필요(트랙 없음). 트랙 채널은 2차 범위 |
| `Workspace/perspective.xml` | `windowID="HEX32.o"`, `Section path="…HEX32"` | 창 위치/보기 상태 | 워크스페이스 상태 — 스테일 허용 추정, 작성 불필요 |
| `settings.xml` | `outputList="{G}"` (믹스다운 출력 = AudioOutput 채널) | 렌더 설정 | AudioOutput 전송 비범위 → 영향 없음 |
| `Devices/audioiomanager.xml` | `previewChannel="{G}"`, `PortAssignment name="{G}"` (AudioInput/Output만) | 오디오 IO 배정 | 입출력 채널 전송 비범위 → 영향 없음 |
| `Envelopes/<라벨>/` | 폴더명이 **채널 라벨**(UID 아님) | 볼륨/팬 오토메이션 | 기본 동반 복사 (라벨 축 충돌 별도 검사) |
| `Presets/Channels/<라벨>/` | 폴더명이 **채널 라벨**, audiomixer의 `String x:id="presetPath"`가 명시 경로 참조 | 인서트 프리셋 | **필수 복사** + presetPath 갱신 |

## 스테일 참조 실측 증거 (원본 naiite_14)
- notepad.xml의 `S.BUS` 항목 id `{9E216095-…}` ≠ audiomixer S.BUS UID `{7AEF0C5E-…}`
- notepad.xml의 `MIXOUT` 항목 id `{45A6A67A-…}` ≠ audiomixer MIXOUT UID `{1A082A8E-…}`
- → Studio One은 notepad의 dangling UID를 허용함 (원본 자체에 존재). notepad 미기재는 안전할 가능성 높음.
- 반대 방향(채널 존재 + notepad 항목 없음)도 원본에서 확인: kick 등 트랙 항목은 **trackID** 기준으로 기재되어 있어 채널 UID 기재가 전 채널에 일관되지 않음.

## 결론 (수동 실험 전 가설)
- 필수 집합: `Devices/audiomixer.xml` + `Presets/Channels/<라벨>/*` (+ Envelopes는 오토메이션 보존용)
- mixerconsole/notepad는 UI 편의 항목으로 추정 — 03 파일 수동 확인으로 최종 판정.
- transfer 엔진은 안전 측으로 **항상 동반 작성**(02 방식)을 기본값으로 한다.
