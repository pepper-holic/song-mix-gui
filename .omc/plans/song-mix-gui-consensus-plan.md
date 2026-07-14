# Plan: Studio One .song 믹스 분석·시각화·병렬 전개 GUI 툴

- Status: **pending approval (컨센서스 도달 — Architect APPROVE, Critic APPROVED)**
- Source spec: `.omc/specs/deep-interview-song-mix-gui.md` (딥 인터뷰 완료, 모호성 15.9%)
- Date: 2026-07-11

## Requirements Summary

Studio Pro 8.1(.song, FormatVersion 9) 파일을 열어 (1) 채널→버스→MIXOUT 라우팅과 채널별 플러그인 체인을 계층 그래프로 시각화하고, (2) 여러 song을 탭/좌우 스플릿으로 열어 채널·버스 서브트리를 드래그앤드롭/복붙으로 다른 song에 직접 기록하며, (3) 사용자 라이브러리(116 songs)에 실사용된 약 22종 플러그인의 vstpreset 세팅값을 파라미터 이름/값으로 해석해 표시하는 Windows GUI 툴.

핵심 정책(스펙 확정): 자동 백업(.bak)+덮어쓰기, Studio One이 파일을 열고 있으면 쓰기 차단, 이름 충돌 시 확인 후 덮어쓰기, 미해석 플러그인은 "해석 불가(복사 가능)" 표시.

## RALPLAN-DR Summary

### Principles
1. **무손실 라운드트립이 쓰기 기능의 전제** — 수정하지 않는 zip entry는 바이트 그대로 보존하고, 쓰기 검증 없이는 어떤 전송 기능도 출시하지 않는다.
2. **해석 실패는 저하(degrade)이지 차단이 아니다** — 파라미터 해석이 안 되는 플러그인도 바이너리 복사/전송은 항상 가능해야 한다.
3. **스파이크 게이트 통과 전 본 구현 금지** — 라운드트립과 VST 호스팅 두 가지 최대 리스크를 Phase 0에서 검증한 후 스택을 확정한다.
4. **사용자의 실제 라이브러리가 테스트 코퍼스** — 116개 .song과 22종 플러그인이 회귀 테스트의 기준이다.
5. **가장 단순한 동작 우선** — 이름 매칭 덮어쓰기+확인 팝업, 자동 백업. 병합/리네임 등 복잡한 정책은 비범위.

### Decision Drivers (Top 3)
1. `.song` 재작성 후 Studio Pro 8.1이 정상으로 열고 재생하는가 (라운드트립 무손실성)
2. 설치된 VST(특히 WaveShell 구조의 Waves 10종)를 로드해 vstpreset을 주입하고 파라미터를 읽을 수 있는가
3. 듀얼 패널 계층 그래프 + 드래그앤드롭 UI를 솔로 개발 속도로 구현 가능한가

### Viable Options

**Option A: Electron + React + React Flow (GUI) + Python 사이드카(pedalboard) (권고)**
- Pros: React Flow는 계층 노드 그래프·드래그앤드롭에 가장 성숙한 라이브러리. 파싱/해석은 Python(zipfile, lxml, pedalboard)으로 생태계가 완비됨. GUI와 엔진의 관심사 분리.
- Cons: 두 런타임(Node+Python) 배포·IPC 복잡도. pedalboard의 WaveShell 지원은 미검증(스파이크 필요).
- (Tauri를 채택하지 않은 이유(Critic m3): Python 사이드카가 어차피 필요해 Tauri의 Rust 코어는 제3의 언어만 추가하며, 번들 경량화 이점은 A′안이 단일 런타임으로 더 크게 달성)

**Option B: 전체 Python (PySide6 + NodeGraphQt + pedalboard)**
- Pros: 단일 스택, 배포 단순(PyInstaller), 엔진과 GUI 사이 IPC 불필요.
- Cons: NodeGraphQt는 React Flow 대비 계층 레이아웃·커스텀 노드·DnD 유연성이 떨어져 UI 요구(탭/스플릿+그래프+드래그)를 만족시키는 비용이 큼.

**Option A′ (Architect 합성안): PySide6 + QWebEngineView(React Flow 호스팅) + pedalboard 인프로세스**
- Pros: React Flow의 그래프 성숙도와 Python 엔진 생태계를 유지하면서 **프로세스 경계를 제거** — 단일 런타임, 단일 PyInstaller 아티팩트, stdio JSON-RPC 대신 QWebChannel 인프로세스 브리지. 솔로 개발자의 통합 표면 최소화.
- Cons: QWebChannel 브리지 학습 비용, Chromium 임베드는 여전히 존재.

**Option C: JUCE (C++ 단일 앱)**
- Pros: VST2/VST3/WaveShell 호스팅이 가장 견고(업계 표준 호스트 SDK). 네이티브 단일 배포.
- Cons: 솔로 개발 속도 최악. 노드 그래프 GUI를 사실상 처음부터 제작. 파서·GUI·호스팅 전부 C++ 비용.

**선택 방침**: 프론트는 React Flow로 확정하되, **런타임 구조(A: Electron+사이드카 vs A′: PySide6+QWebEngineView 인프로세스)는 Phase 0 게이트에서 확정**한다. 상위 2개 결정 동인(라운드트립, 호스팅)은 두 안에서 동일한 Python 코드이므로, 게이트 판단 기준은 배포·브리지 실험 결과다. Waves WaveShell을 pedalboard가 처리하지 못하면 JUCE 기반 해석 헬퍼 CLI(옵션 C의 호스팅 부분만 축소 채용)를 결합한다. Option B(NodeGraphQt)는 UI 요구 대비 성숙도 열세로 invalidated — A′가 동일한 단일 런타임 이점을 React Flow와 함께 제공하므로 B를 선택할 이유가 소멸.

## Implementation Steps

### Phase 0 — 리스크 스파이크 (게이트) `spikes/`
- **S0.1 라운드트립 + 최소 변형 스파이크** `spikes/roundtrip_poc.py`
  - (a) 무수정 재작성: naiite_14.song을 열어 비수정 entry는 원본 바이트 복사로 재작성 → 기능 동일성 확인.
  - (b) **최소 변형 쓰기(Architect 요구)**: 버스 1개 리네임 또는 채널 1개 복제(UID 재생성 + `Connection` 재배선 포함)를 실제로 수행한 파일을 생성 → **Studio Pro 8.1에서 열어 정상 재생 확인(사용자 수동)**. XML 재직렬화 허용 범위(속성 순서, `x:id` 네임스페이스, 공백, self-closing 태그)를 이 단계에서 검증한다. 무수정 통과만으로는 변형 쓰기 경로를 전혀 검증하지 못하기 때문.
  - (b-2) **동반 파일 필수성 실험(Critic M1)**: 복제 채널을 의도적으로 audiomixer.xml에만 기록(mixerconsole.xml/notepad.xml 미기재)한 파일을 만들어 Studio One이 수용하는지 기록 → 전송 시 반드시 함께 작성해야 하는 동반 파일 집합을 경험적으로 확정. (실측: 버스 UID는 audiomixer.xml 외에 mixerconsole.xml, notepad.xml의 `NotepadItem id="{UID}"`에서도 참조됨)
  - (b-3) **UID 참조 문법 카탈로그 산출(Architect note #1)**: UID 하나를 압축 해제본 전체에서 grep해 등장하는 모든 문법 형태를 아티팩트로 기록(현재 확인된 형태: `uid="{G}"`, `objectID="{G}/Input|Output"`, `NotepadItem id="{G}"`). 1.5 스캐너의 형태 목록은 이 카탈로그를 근거로 하며 감사 가능해야 한다.
  - 근거 구조(실측): zip 컨테이너 내 `Devices/audiomixer.xml`(채널 5그룹: AudioInput/AudioOutput/AudioTrack/AudioGroup/AudioEffect, `Connection x:id="destination"` 라우팅, `classInfo classID/name` 인서트), `Presets/Channels/<라벨>/<N> - <플러그인>.vstpreset`.
- **S0.2 호스팅 + 파라미터 품질 스파이크** `spikes/host_poc.py`
  - pedalboard로 ① FabFilter Pro-Q 3(VST3) ② Waves CLA-76(WaveShell) 로드 → 파라미터 열거 → naiite_14의 실제 vstpreset 주입(`load_preset` 또는 state 설정) → 값 일치 확인.
  - **파라미터 이름 품질 등급화(Architect 요구)**: 로드 성공 여부만이 아니라, 노출된 파라미터가 사람이 읽을 수 있는 이름인지(`Attack`, `Ratio`) vs 불투명한지(`Param 34 = 0.62`)를 플러그인별로 기록 → 22종에 대해 "해석 가능 / 부분 해석 / 복사만 가능" 3단계 등급표 산출. 이 등급표가 AC-7의 정직한 범위가 된다.
  - 실패 시: JUCE `AudioPluginHost` 기반 헬퍼 CLI(플러그인 로드→preset 주입→파라미터 JSON 덤프) PoC로 대체 평가.
- **S0.3 잠금 감지 스파이크(Architect 요구)** `spikes/lock_poc.py`
  - Studio One이 .song을 열었을 때 OS 파일 핸들을 유지하는지 실측(열기 전/후 쓰기 시도, `openfiles`/handle 검사). 배타 핸들이 없으면(임시 폴더로 추출해 편집할 가능성) 대체 휴리스틱 설계: Studio One 프로세스 존재 + 해당 파일의 최근 열람 여부 조합 등. AC-5의 "쓰기 차단" 보장 메커니즘을 여기서 확정.
- **게이트 판정**: S0.1(a)+(b) 통과 필수(실패 시 쓰기 기능 전면 재설계). S0.2 결과로 해석 엔진(pedalboard vs JUCE 헬퍼) 확정. S0.3으로 잠금 감지 메커니즘 확정. **런타임 구조(A vs A′)도 이 게이트에서 확정**(QWebChannel 브리지 간이 실험 포함).

### Phase 1 — 코어 파서 라이브러리 `engine/songcore/`
- 1.1 `container.py`: .song zip 리더/라이터. 수정 대상 외 entry는 바이트 보존. 쓰기 전 원본 `.bak` 생성, 대상 파일 잠금(Studio One 열림) 감지 시 거부.
- 1.2 `mixer_parser.py`: audiomixer.xml → 모델. `ChannelGroup`별 채널(UID/name/label/type), `Attributes x:id="Inserts"` 체인(classID, 플러그인명, 슬롯 순서), `Connection x:id="destination"` → 라우팅 엣지, `Presets/Channels/<라벨>/` 프리셋 파일 매핑.
- 1.3 `topology.py`: 채널→버스→MIXOUT 트리 + FX 센드(AudioEffectChannel) 그래프 빌드.
- 1.4 `test_roundtrip.py`: **116개 .song 파일 전체**에 대해 read→무수정 write→바이트/기능 동일성 자동 테스트, **그리고 최소 1개의 변형 쓰기 파일이 Studio Pro 8.1에서 수동 확인 통과(Architect 요구)**. 두 조건 모두 충족해야 Phase 1 완료 게이트 통과 — 무수정 코퍼스 테스트만으로는 변형 경로를 검증하지 못함. (코퍼스 구성 주의(Critic m1): 116파일 = 고유 프로젝트 29 + History/Autosave 사본 87. 직렬화 커버리지로는 유효하나, 플러그인 사용 빈도 수치는 사본으로 부풀려진 값이므로 고유 프로젝트 기준으로 재집계해 해석 우선순위에 사용)
- 1.5 `uid_refs.py` **(Architect 요구, 전송의 정합성 척추)**: 주어진 채널/버스 UID에 대해 **모든 zip entry**(audiomixer.xml, mixerconsole.xml, notepad.xml, Song/song.xml, Envelopes/ 등)를 스캔해 참조 위치를 전수 열거하는 스캐너. 형태 목록은 S0.1(b-3) 카탈로그 기반. 검사는 두 방향 모두: ① **dangling 참조**(존재하지 않는 대상을 가리킴) ② **구조적 불완전성(Critic M1)** — 채널 UID가 존재하는데 스파이크에서 필수로 판명된 동반 entry(mixerconsole/notepad 등)가 없는 경우. 어느 쪽이든 발견 시 **fail-closed**(쓰기 거부).
- 1.6 `transfer.py`: 쓰기 API — 버스 서브트리/채널 인서트 체인 삽입·교체. 작업 내역:
  - UID 재생성, 서브트리 내부 `Connection` 재배선, 서브트리 출력의 대상 라우팅 접합
  - `Presets/Channels/<라벨>/` 파일 복사 + **동반 파일 작성(Critic M1)**: S0.1(b-2)에서 필수로 판명된 entry(mixerconsole.xml 채널 항목, notepad.xml `NotepadItem` 등)를 함께 생성
  - **Envelopes/<라벨>/ 오토메이션 정책(Critic M2)**: 전송 채널의 볼륨/팬 오토메이션 폴더는 **기본 함께 복사**(믹서 인접 상태로 간주). 복사 제외 옵션 제공 시에는 관련 참조를 제거해 스캐너가 유효한 전송을 차단하지 않도록 보장
  - **라벨 축 처리(Critic m2 / Architect note #2)**: `Presets/Channels/`와 `Envelopes/`는 UID가 아닌 **채널 라벨**로 키가 잡히므로(실측: `The Kill - Make 'Em Suffer (2012) Full Album HQ (Grindcore)/` 같은 특수문자 라벨 존재) 경로 안전화 + 라벨 충돌을 UID 충돌과 별개 축으로 검사
  - 1.5 스캐너로 참조 정합 + 구조 완전성 검증
  - **1차 범위: 버스(AudioGroupChannel)·FX 채널 생성 + 기존 채널의 인서트 체인/세팅 교체. 새 오디오 트랙(AudioTrackChannel) 생성은 Song/song.xml 트랙 정의와 얽혀 있어 2차로 보류. AudioInput/AudioOutput 채널 그룹의 전송도 비범위(라우팅 종단은 대상 song의 기존 입출력을 사용).**

### Phase 2 — GUI 셸 + 시각화 `app/`
- 2.1 Phase 0 게이트에서 확정된 런타임 구조로 스캐폴드: A안이면 Electron + React + TypeScript(+Python 사이드카, JSON-RPC over stdio), A′안이면 PySide6 + QWebEngineView + React 번들(QWebChannel 브리지). 두 경우 모두 React Flow가 그래프 레이어.
- 2.2 song 열기 → React Flow 계층 그래프: 좌측 트랙/채널 → 버스 → MIXOUT 우측 종단, 노드에 인서트 체인 뱃지(순서 표시).
- 2.3 노드 상세 패널: 인서트 체인 목록(슬롯 순서, 플러그인명, 프리셋명).
- 2.4 멀티 문서: 탭 + 좌우 스플릿 뷰(두 song 동시 표시).

### Phase 3 — 병렬 전개 (전송) `app/` + `engine/`
- 3.1 드래그앤드롭: 소스 패널의 채널 노드/버스 서브트리 선택 → 대상 패널에 드롭. 복붙(Ctrl+C/V) 동일 경로.
- 3.2 충돌 감지: 대상에 동명 채널/버스 존재 시 확인 다이얼로그 → 승인 시 인서트 체인·세팅·라우팅 교체.
- 3.3 저장 파이프라인: 잠금 검사(S0.3에서 확정된 메커니즘) → `.bak` 백업 → 덮어쓰기 → 즉시 재파싱해 그래프 재검증 + UID 참조 스캐너(1.5) 무결성 검사(불일치 시 백업 복원 안내). **주의: 재파싱 동등성은 자기 일관성 검증일 뿐 Studio One 수용을 보장하지 않으므로, 마일스톤마다 변형 파일의 Studio Pro 8.1 수동 개봉 체크포인트를 둔다(Phase 5까지 미루지 않음).**
- 3.4 전송 통합 테스트: naiite_14의 드럼 버스 서브트리(K.BUS+S.BUS+T.BUS+CYM.BUS→DR.B)를 다른 song 사본에 전송 → 재파싱 그래프 동등성 자동 검증 + 전송 결과물 1건 Studio Pro 8.1 수동 확인.

### Phase 4 — 파라미터 해석 `engine/introspect/`
- 4.1 인벤토리 스캔: `C:\Program Files\FabFilter`, `C:\Program Files\VstPlugIns`, `C:\Program Files\Common Files\VST3`, WaveShell 경로 스캔 → classID↔플러그인 바이너리 매핑 캐시.
- 4.2 해석 서비스: vstpreset → 해당 플러그인 로드 → state 주입 → 파라미터 이름/값/단위 JSON 덤프. 결과 캐시(파일 해시 키). 우선순위: 사용 빈도순(CLA-76 554회, Decapitator 238, SSLComp 217, Maag 179, Pro-Q 3 159 …).
- 4.3 UI: 인서트 클릭 → 파라미터 테이블. 미해석 시 "해석 불가(복사 가능)" 배지.

### Phase 5 — 합격 검증
- 스펙 AC-1~AC-7 전체 체크리스트 실행. 최종 수동 검증(사용자): 전송된 song을 Studio Pro 8.1에서 열어 라우팅·플러그인·세팅 확인 및 재생.

## Risks and Mitigations
| Risk | Mitigation |
|------|------------|
| **XML 재직렬화를 Studio One이 거부(변형 쓰기 경로)** | S0.1(b) 최소 변형 스파이크로 최우선 검증. 속성 순서/네임스페이스/공백 보존 직렬화 전략. Phase 1 게이트에 변형 파일 수동 수용 확인 포함 |
| WaveShell(Waves 10종) 로드/주입 실패 또는 파라미터 이름 불투명 | Phase 0 S0.2에서 로드+이름 품질 등급화. 실패 시 JUCE 헬퍼 CLI 전환, 그것도 실패 시 해당 플러그인은 "해석 불가(복사 가능)"로 저하 운영 |
| UID 참조 누락(Envelopes/, song.xml, mixerconsole.xml)으로 오토메이션·콘솔 고아화 | 1.5 UID 참조 전수 스캐너 + fail-closed 전송. 재파싱 + 무결성 검사(3.3) |
| Studio One이 열림 상태에서 OS 잠금을 안 잡아 쓰기 차단이 무력화 | S0.3 잠금 감지 스파이크로 실제 메커니즘 확정(핸들 검사 실패 시 프로세스+휴리스틱 조합) |
| 오디오 트랙 채널 전송이 song.xml 트랙 정의와 충돌 | 1차 범위를 버스/FX 채널 생성 + 기존 채널 체인 교체로 한정(1.6), 트랙 생성은 2차 |
| pedalboard의 vstpreset 주입 미지원 | 스파이크에서 `load_preset` API 검증, 불가 시 VST3 컨테이너에서 chunk 추출 후 state API로 주입 |
| 듀얼 런타임(Electron+Python) 배포 복잡도 | Phase 0 게이트에서 A′(PySide6+QWebEngineView 인프로세스) 대안과 비교 확정 |
| **동반 파일 불완전성 — 채널이 audiomixer.xml에만 존재하고 mixerconsole/notepad 항목 누락(Critic M1)** | S0.1(b-2)에서 필수 동반 집합을 경험적으로 확정, 1.5 구조 완전성 검사로 fail-closed, 1.6에서 동반 entry 작성 |
| Envelopes/<라벨>/ 오토메이션이 전송에서 누락되거나 dangling 참조로 유효 전송 차단 | 1.6에서 기본 함께 복사 정책 명시, 제외 시 참조 정리 보장 |

## Verification Steps
- **Unit**: mixer_parser가 naiite_14에서 19 AudioTrackChannel, 9 AudioGroupChannel, 1 AudioEffectChannel, 50 Connection을 정확히 추출하는지; 인서트 체인 순서가 `Presets/Channels/` 순번과 일치하는지; UID 참조 스캐너가 알려진 참조 위치(Connection, Envelopes 경로, mixerconsole)를 모두 찾는지.
- **Integration (자동)**: 116곡 라운드트립 무손실 테스트; 드럼 버스 서브트리 전송 후 재파싱 그래프 동등성 + dangling 참조 0건.
- **Studio One 수용 체크포인트 (수동, 각 마일스톤)**: S0.1(b) 최소 변형 파일, Phase 1 게이트 변형 파일, Phase 3 전송 결과물 — 각각 Studio Pro 8.1에서 개봉·재생 확인. 재파싱 동등성만으로는 수용을 보장하지 못하므로 Phase 5까지 미루지 않는다.
- **E2E (수동, 사용자)**: 최종 전송·저장된 .song을 Studio Pro 8.1에서 열어 정상 재생 — AC-5의 최종 판정.
- **해석 검증**: Pro-Q 3, CLA-76의 표시 파라미터 값이 Studio One 내 실제 플러그인 UI 값과 일치(샘플 대조); S0.2 등급표와 UI 배지 표시 일치.

## Acceptance Criteria
스펙의 AC-1 ~ AC-7을 그대로 승계 (`.omc/specs/deep-interview-song-mix-gui.md` 참조).

## Open Questions (S0.1 스파이크에서 해결)
1. Studio One은 채널마다 mixerconsole.xml 항목을 요구하는가, 아니면 열 때 콘솔 레이아웃을 재생성하는가? → S0.1(b-2)에서 판정 (동반 파일 작성이 필수인지 결정)
2. 한 song 안에서 두 채널이 동일 라벨을 가질 수 있는가? (`Presets/Channels/<라벨>/`, `Envelopes/<라벨>/` 충돌 축) → 코퍼스 전수 스윕으로 확인
3. `settings.xml` / `Song/editor.xml` / `Workspace/perspective.xml`이 전송에 영향을 주는 UID를 갖는가, 순수 워크스페이스 상태인가? → S0.1(b-3) 카탈로그로 판정

## ADR

- **Decision**: React Flow를 그래프 레이어로 확정한 웹뷰 기반 GUI + Python 엔진(zipfile/lxml/pedalboard) 구조를 채택하고, 런타임 구조(A: Electron+Python 사이드카 vs A′: PySide6+QWebEngineView 인프로세스)는 Phase 0 스파이크 게이트에서 실증 데이터로 확정한다. 쓰기 안전은 "무수정 entry 바이트 보존 + 변형 쓰기 스파이크 + UID/구조 완전성 fail-closed 스캐너 + 마일스톤별 Studio One 수동 수용 체크포인트"의 4중 방어로 보장한다.
- **Drivers**: ① .song 라운드트립 무손실 쓰기 ② VST 호스팅 파라미터 해석(WaveShell 포함) ③ 듀얼 패널 그래프 + DnD UI 개발 속도 — 상위 2개 동인은 A/A′ 어느 쪽에서도 동일한 Python 코드이므로 런타임 결정은 3번 동인과 배포 비용으로만 판단.
- **Alternatives considered**: Option B(PySide6+NodeGraphQt) — A′가 단일 런타임 이점을 React Flow와 함께 제공해 invalidated. Option C(JUCE 단일 앱) — 솔로 개발 속도 비용 과대, 단 호스팅 헬퍼 CLI로 축소 채용 가능성은 S0.2 실패 시 예비. Tauri — Python 사이드카가 필수라 제3 언어(Rust)만 추가.
- **Why chosen**: 계획의 최대 리스크(재직렬화 수용, UID 참조 완전성, WaveShell 해석)는 전부 엔진 계층 문제로, GUI 선택과 무관. 따라서 리스크는 Phase 0 스파이크로 조기 소진하고, GUI는 성숙도가 검증된 React Flow로 고정하되 런타임 결합 방식만 실측으로 결정하는 것이 솔로 개발자의 통합 표면을 최소화한다.
- **Consequences**: (+) 최대 리스크가 Phase 0에서 판명되어 늦은 재설계 확률 최소화, 해석 불가 플러그인도 복사 기능은 항상 동작. (−) 스파이크 3종 + 수동 체크포인트로 초기 속도는 느림, Chromium 임베드는 어느 안에서도 유지, 파라미터 해석 범위는 S0.2 등급표에 종속.
- **Follow-ups**: S0.1(b-2) 동반 파일 필수성 판정 결과를 1.5/1.6에 반영; 고유 프로젝트 29개 기준 플러그인 빈도 재집계; 코퍼스 라벨 중복 스윕; A/A′ 게이트 판정 기록.

## Changelog (컨센서스 반영 내역)

- **Architect 1차(REVISE) 반영**: S0.1(b) 최소 변형 쓰기 스파이크 추가, 1.4 게이트에 변형 파일 수용 조건 추가, 1.5 UID 참조 전수 스캐너 신설(fail-closed), S0.3 잠금 감지 스파이크 신설, S0.2 파라미터 이름 품질 3단계 등급화, Option A′(PySide6+QWebEngineView) 추가 및 런타임 결정을 Phase 0 게이트로 이관, 마일스톤별 Studio One 수동 수용 체크포인트 명문화.
- **Critic(APPROVED, 병합 필수) 반영**: M1 — S0.1(b-2) 동반 파일 필수성 실험 + 1.5 구조 완전성 검사 + 1.6 동반 entry 작성(mixerconsole.xml/notepad.xml, 실측 근거: `NotepadItem id="{UID}"`); M2 — Envelopes/<라벨>/ 오토메이션 기본 동반 복사 정책 명시; m1 — 코퍼스 구성 주석(고유 29 + 사본 87) 및 빈도 재집계; m2 — 라벨 축 경로 안전화·별도 충돌 검사; m3 — Tauri 미채택 근거; S0.1(b-3) UID 참조 문법 카탈로그 아티팩트화; AudioInput/AudioOutput 전송 비범위 명시; Open Questions 섹션 추가.
