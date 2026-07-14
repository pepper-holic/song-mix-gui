# Plan: song-mix-gui v2 — 사용성·성능·범위 확장

- Status: **pending approval (컨센서스 도달 — Architect APPROVE, Critic ACCEPT)**
- Source spec: `.omc/specs/deep-interview-song-mix-gui-v2.md` (딥 인터뷰 9라운드, 모호성 17%)
- Base: v1 완성 코드베이스 (pytest 262, E2E PASS — `CLAUDE.md`, `progress.txt` 참조)
- Date: 2026-07-12

## Requirements Summary

v1을 일상 도구 수준으로: **① 사용성**(세션 다단계 Undo, 그래프 검색/필터, 최근 파일, 나란히+차이강조 체인 비교) → **② 성능**(시작<3s, 열기<1s, 미캐시 해석 진행률+우선순위 프리웜) → **③ 범위 확장**(트랙 채널 전송[기본 빈 트랙+옵션 이벤트], 기존 트랙 체인 이식 UI, 버스 오토메이션 전송, 외부 send 보존 옵션) + UI/UX(그룹 구분·피드백·단축키·시각 폴리시). AC-1~AC-11은 스펙 승계.

## RALPLAN-DR Summary

### Principles
1. **v1 안전 원칙 불가침** — 원시 entry 보존, 텍스트 수술, fail-closed 스캐너, .bak, 수동 게이트 정직성. v2의 어떤 기능도 이를 우회하지 않는다.
2. **우선순위 = 배송 순서** — 사용성 → 성능 → 범위확장 순으로 Phase를 배치하고, 앞 Phase의 회귀 그린 없이 다음 Phase에 진입하지 않는다.
3. **쓰기 신규 축은 스파이크 게이트 후 본구현** — song.xml에 처음 쓰는 두 축(AutomationTrack, MediaTrack)은 v1의 S0.1 방식대로 최소 변형 파일 + 수동 체크리스트를 먼저 만든다.
4. **Undo는 전체 파일 스냅샷** — 연산 역산이 아니라 저장 직전 바이트 스냅샷 복원. 원시 보존 원칙과 정합하며 증명 가능하게 안전.
5. **성능은 측정 후 최적화** — 예산 4종(시작<3s, 열기<1s, 캐시 해석<0.3s, 전송+저장<3s)을 계측 스크립트로 고정하고, 병목 실측 없이 구조 변경 금지.

### Decision Drivers (Top 3)
1. 매일 쓰는 조작(전송 실수 복구, 채널 찾기, 세팅 비교)의 마찰 제거 — 사용자가 1순위로 지정
2. song.xml 신규 쓰기 축(AutomationTrack/MediaTrack)의 Studio One 수용성 — v2 최대 기술 리스크
3. 기존 262 테스트 + E2E 회귀 유지 — v1 신뢰를 담보로 한 증분 개발

### Viable Options

**Undo 설계**
- **A. 파일 바이트 스냅샷 스택 (채택)**: 저장 직전 대상 파일 전체를 세션 임시폴더에 push, Ctrl+Z는 top 복원(잠금검사+재파싱 검증 경유). Pros: 단순·증명가능·모든 쓰기 유형 공통. Cons: 파일당 ~200KB×스택 깊이 디스크 (한도 20단계로 무시 가능).
- B. 연산 역산(inverse transfer): Pros: 디스크 0. Cons: 쓰기 유형마다 역산 구현·검증 필요, fail-closed 증명 불가 — **invalidated** (원시 보존 원칙과 충돌).

**체인 비교의 파라미터 소스**
- **A. 해석 캐시 재사용 (채택)**: interpret 서비스의 md5 캐시 결과 2건을 나란히 diff. Pros: 추가 엔진 없음, 프리웜과 시너지. Cons: 미해석 플러그인은 값 비교 불가 → "체인 구조만 비교" 폴백 표시.
- B. 실시간 이중 로드: Cons: 클릭당 수 초×2 — invalidated (성능 예산 위반).

**트랙 채널 전송 전개**
- **A. 2단 스파이크 게이트 (채택)**: S-A(빈 트랙: MediaTrack+AudioTrackChannel+동반 entry) 수동 게이트 → 본구현 → S-B(이벤트 포함: +Events+mediapool) 수동 게이트 → 본구현. Pros: 리스크 최고 축을 v1 검증 패턴으로 분할. Cons: 수동 확인 2회 대기.
- B. 일괄 구현 후 일괄 검증: Cons: 실패 시 원인 축 분리 불가 — invalidated (v1 S0.1(b-2) 교훈).

## Implementation Steps

> **v1 게이트 결과 반영 (2026-07-12)**: 01~04 수동 확인 전부 통과 — 텍스트 수술 쓰기의 Studio One 수용성 확정, 동반 파일은 선택적 판정(엔진은 계속 기재). v2의 기저 리스크가 크게 해소됨. 교훈: **스파이크 검증 파일(05/06/07)은 대상 곡 폴더 안에 사본으로 배치**해야 미디어가 로딩됨(.omc/verify/에는 백업만).

### Phase 0-S — 스파이크 선발사 (t=0, Phase U와 병렬) **(Architect 합의 반영)**
본구현 순서는 U→P→S를 유지하되, **수동 게이트가 크리티컬 패스**이므로 스파이크 파일 3종을 프로젝트 착수와 동시에 생성·제출한다 (U 개발과 코드 충돌 없음 — 수동 이식 샘플):
- S3a 오토메이션 스파이크 → `.omc/verify/05-automation-transfer.song`
- S4a 빈 트랙 스파이크 → `.omc/verify/06-track-transfer-empty.song`
- S4c 이벤트 포함 스파이크 → `.omc/verify/07-track-transfer-events.song`
- 각각 MANUAL_CHECKLIST 항목 추가. **S4 체크리스트에는 LauncherCell/arranger 교차참조 확인 명시** (`LauncherCell trackId="{MediaTrack trackID}"`가 트랙별 존재 — 신규 트랙이 launcher cell 없이 정상 개봉되는지가 핵심 관찰 항목. 버스 AutomationTrack은 launcher 참조가 없어 이 위험이 낮은 비대칭도 기록).
- 게이트 결과가 U/P 완료 전에 도착하면 S 본구현은 무대기 진입. **사용자 가용성 의존 명시(Critic)**: 스파이크 제출 시 사용자에게 확인 요청을 즉시 전달하되, U/P 진행 중 미확인이어도 차단하지 않음 — S 본구현 착수 시점에 게이트 상태를 재확인하고, 미확인이면 v1 조건부 패턴(생성물 보존+체크리스트)으로 S3b/S4b를 진행하되 "수동 확인 대기" 표시 유지.

### Phase U — 사용성 (1순위) `app/` + `engine/`
- **U1 Undo 스택** (AC-1): `engine/songcore/undo.py` — 파일별 스택(세션 임시폴더, 최대 20단계). **스냅샷 소스 = 덮어쓰기 직전 대상 파일의 디스크 바이트** (.bak의 다단계판 — mediapool.xml 등 모든 entry가 단일 .song 안에 있으므로 파일 1개 스냅샷으로 완결). **push 시점 명문화(Critic Minor 2): 브리지 슬롯이 save_pipeline을 호출하기 직전에 디스크 바이트를 push** (save_pipeline 내부가 아님 — 첫 줄이 이미 save_over 쓰기이므로). 세션 임시폴더는 앱 시작 시 스테일 세션 잔존물 정리(크래시 대비). 브리지 슬롯 `undo_last(path)` = pop→잠금검사→바이트 복원→재파싱+validate(실패 시 스택 보존+오류 반환). **엣지: 신규 경로 저장(write_to, 기존 파일 없음)은 undo 비대상; 외부 수정 감지(mtime/해시 불일치) 시 해당 파일 스택 무효화+경고.** 프론트: Ctrl+Z(포커스 패널의 문서), 툴바 버튼, 상태바 "복원됨: {작업 설명}". pytest: push→2회 전송→2회 undo→원본 바이트 동일 + 무효화 케이스; E2E: 전송→Ctrl+Z→노드 수 원복.
- **U2 검색/필터** (AC-2): 툴바 검색 입력(패널별). 채널명/플러그인명 부분일치 → 매칭 노드 하이라이트(클래스 토글) + 첫 결과 `setCenter`. 플러그인 필터 모드: 미매칭 노드 dim. 데이터는 이미 로드된 model로 프론트 단독 처리(브리지 불필요). E2E: "CLA-76" 검색 → 하이라이트 노드 수 == 사용 채널 수.
- **U3 최근 파일** (AC-3): `QSettings("songmix","app")` 최근 10개. 브리지 `get_recent()/add`. 빈 패널과 툴바 드롭다운에 목록, 클릭 열기. E2E: 열기→목록 반영 확인(QSettings 목킹 or 임시 스코프).
- **U4 체인 비교 뷰** (AC-4, Critic MAJOR 2 반영): 노드 우클릭 메뉴 확장("비교 A로 지정"/"A와 비교") 또는 상세패널 "비교" 버튼. **diff 계산은 Python 서비스로 분리** — `engine/introspect/compare.py`: 두 채널의 (체인 구조, 캐시 interpret 결과)를 받아 행 목록(`match|value-diff|chain-mismatch` 타입) 반환 → **pytest로 직접 검증** (동일 플러그인·상이 값 → value-diff 행; 상이 플러그인 → chain-mismatch 행; 미해석 → 구조 비교 폴백). 프론트 `ComparePanel.tsx`는 렌더만(값 다른 행 색 강조, 불일치 행 표시, 미해석 배지). **E2E는 공유 플러그인을 가진 두 채널**(예: K.BUS vs S.BUS의 Pro-Q 3 — 실제 값 상이)로 **캐시 워밍 선행 후** "타입=value-diff인 행이 강조 색으로 렌더"를 단언 (구조 불일치 행만으로 통과 불가).
- **U5 UI/UX 폴리시** (AC-10): 그룹 범례(트랙/버스/FX/아웃 색), 전송·해석·프리웜 진행 인디케이터(상태바 스피너+프리웜 진행률 `prewarm_status()` 폴링), 단축키 도움말 다이얼로그(`?`), 파라미터 테이블 가독성(정렬·검색). 
- **게이트 U**: pytest+빌드+E2E(신규 시나리오 포함) 그린.

### Phase P — 성능 (2순위)
- **P1 계측 스크립트** `spikes/perf_budget.py`: 시작(프로세스 spawn→SELF-TEST 첫 프레임), 열기→그래프(브리지 타임스탬프), 캐시 해석, 전송+저장 — 예산표와 함께 출력. 이것이 AC-5의 판정기.
- **P2 시작 최적화**: 실측 후 — 인벤토리/introspect import 지연화, QtWebEngine 초기화와 번들 로드 병렬화, 필요 시 스플래시. 예산: <3s.
- **P3 프리웜 우선순위 (Critic MAJOR 1 반영 — 입도 재정의)**: 현행 prewarm은 **플러그인 바이너리 단위 배치**(service.py:72, 플러그인당 1회 로드가 존재 이유)이므로 항목 단위 큐는 배치 효율을 파괴한다. 따라서 우선순위는 **바이너리 그룹 레벨**에 적용: ⑴ `hint_visible(uids)` → 가시/선택 채널이 사용하는 **플러그인 그룹**을 그룹 큐 선두로 정렬 ⑵ 미캐시 클릭 시 해당 **플러그인 그룹** 승격 ⑶ `prewarm_status()` 브리지 슬롯 신설 — 진행률 입도는 **그룹 단위**(N/M 플러그인 완료)이며 이 입도가 U5·AC-5 판정 기준 ⑷ 그룹 큐는 락 보호(브리지↔워커 레이스 차단, Architect #3) ⑸ 배치→증분 워커 전환 같은 구조 변경은 원칙 5(측정 후) 게이트 뒤로 — P1 계측에서 그룹 입도가 체감 미달로 판정될 때만 스코프 승격.
- **P4 열기/저장 실측 확인**: 이미 예산 내로 추정 — 계측으로 확정만. 초과 시에만 최적화.
- **게이트 P**: perf_budget.py 전 항목 예산 통과 (미캐시 해석은 "진행률 표시 즉시성"으로 판정).

### Phase S — 범위 확장 (3순위) `engine/songcore/`
- **S1 체인 이식 UI** (AC-7): 엔진 `replace_insert_chain` 기존 완성 — UI만: 노드 우클릭 "체인 복사" 후 대상 채널(트랙 포함) 우클릭 "체인 붙여넣기(교체)" → 확인 다이얼로그 → 저장 파이프라인+Undo push. E2E 추가.
- **S2 외부 send 보존 옵션** (AC-9): `transfer.py` clean_sends에서 제거 전 대상 모델 라벨 매칭 — 동명 채널 존재 시 objectID를 그 UID로 재배선(옵션 on 시). 전송 확인 다이얼로그에 체크박스. pytest: 동명 있음→연결/없음→제거 기록.
- **S3 버스 오토메이션 전송** (AC-8): 실측 구조 확정됨(`AutomationTrack trackID={자체} name={라벨}` + `AutomationRegion identity=param:///AudioMixer/{채널UID}/…` + `media:///Envelopes/{라벨}/…`).
  - S3a 스파이크: naiite_14 S.BUS 오토메이션을 사본에 수동 이식한 최소 변형 파일 → `.omc/verify/05-automation-transfer.song` + MANUAL_CHECKLIST 추가.
  - S3b 본구현: transfer_subtree에서 전송 채널 UID의 AutomationTrack 블록을 소스 song.xml에서 추출→trackID 재생성→채널 UID를 uid_map으로 재매핑→dst song.xml `<List x:id="tracks">` 말미 삽입. Envelopes는 이미 복사됨 (라벨 키 URL 유효 — transfer.py:257 실측). **uid_refs.validate() fail-closed 확장 3종 (Architect #2, 필수)**: ⑴ song.xml AutomationRegion `param:///AudioMixer/{UID}` dangling 검사 ⑵ MediaTrack `channelID` ↔ audiomixer 채널 실재 검사 ⑶ trackID 전역 유일성 검사 (+ trackNumber 중복). **⑵⑶은 song.xml `<List x:id="tracks">` 트랙 파서 신설을 요구 — `engine/songcore/song_parser.py` (MediaTrack/AutomationTrack의 trackID·channelID·trackNumber 추출, 읽기 전용) 스코프에 포함(Critic Minor 1)**. 각 검사에 대응 pytest 필수. 기존 원본 코퍼스 29곡으로 보정(v1 방식) 후 배치. 참고(Critic Minor 4): 실측상 AutomationTrack에는 trackNumber 속성이 없음 → S3b는 부여 불필요, S3a에서 확인. pytest: 전송 후 identity dangling 0 + AutomationTrack 수 일치.
- **S4 트랙 채널 전송** (AC-6): 2단 게이트.
  - S4a 스파이크(빈 트랙): MediaTrack(trackID 신규, channelID=신규 채널 UID, Events 비움, trackNumber=말번+1) + AudioTrackChannel + 콘솔/notepad + Presets 복사 최소 변형 파일 → `.omc/verify/06-track-transfer-empty.song` + 체크리스트.
  - S4b 본구현(기본 모드): transfer_subtree 확장 or `transfer_track()` 신설 — 전송 다이얼로그에서 트랙 채널 지원(기본: 빈 트랙+체인+라우팅).
  - S4c 스파이크(이벤트 포함): +`List x:id="Events"` AudioEvent + mediapool.xml AudioClip/Url 이식 → `.omc/verify/07-track-transfer-events.song` + 체크리스트. **미디어 파일 경로 검증: url이 절대경로/타 폴더면 전송 전 경고 다이얼로그**(파일 복사는 비범위).
  - S4d 본구현(옵션 모드): 다이얼로그 "이벤트 포함" 체크박스.
- **게이트 S**: pytest(신규 전송 축별) + 검증 파일 3종 보존 + MANUAL_CHECKLIST 갱신 + E2E.

### Phase V — 최종 검증
- 전체 회귀(262+신규), E2E 확장 스위트, perf_budget 통과, AC-1~AC-11 체크리스트 실행, `RUN_REPORT-v2.md` + MANUAL_CHECKLIST 최종화(수동 게이트: 05/06/07 + v1 잔여 4건).

## Risks and Mitigations
| Risk | Mitigation |
|------|------------|
| AutomationTrack/MediaTrack 신규 쓰기를 Studio One이 거부 | S3a/S4a/S4c 스파이크 파일 + 수동 게이트 선행, 본구현은 게이트 후 (원칙 3) |
| 이벤트 포함 전송의 mediapool/미디어 경로 깨짐 | clipID↔mediapool 정합 스캐너 검사 추가, 경로 미존재 시 전송 전 경고, 파일 복사는 명시적 비범위 |
| Undo 복원이 잠금/외부 수정과 충돌 | 복원도 save_over와 동일 파이프라인(잠금검사+.bak+재파싱 검증), 파일 mtime 변화 감지 시 스택 무효화+경고 |
| QtWebEngine 콜드 스타트가 3s 예산 초과 | P1 실측 우선, 초과 시 지연 import+스플래시, 그래도 초과면 예산 재협상(수치 근거 제시) |
| 비교 뷰가 미해석 플러그인에서 빈 화면 | 구조 비교 폴백 + "해석 불가(복사 가능)" 배지 재사용 (해석 실패는 저하, 차단 아님) |
| trackNumber/트랙 순서 충돌 | 대상 song 말번+1 부여, 스캐너에 trackNumber 중복 검사 추가 |

## Verification Steps
- **Unit**: undo push/pop/한도/무효화; send 보존 라벨 매칭 2경로; AutomationTrack 추출·재매핑·삽입; MediaTrack 생성(빈/이벤트); mediapool 정합 검사; **validate() 확장 3종(param:/// dangling, channelID 실재, trackID 유일) 각각의 합성 결함 검출 + 29곡 원본 무오탐 보정**.
- **Integration**: 전송+오토메이션 후 uid_refs 확장 검사 dangling 0; 트랙 전송 후 116곡 회귀 무변(비대상); Undo 2단 왕복 바이트 동일.
- **E2E (헤드리스)**: 검색 하이라이트, 비교 뷰(공유 플러그인 채널·캐시 워밍 선행·value-diff 행 강조 렌더 단언 — U4 상세 기준), Undo 원복, 체인 붙여넣기, 트랙 전송 다이얼로그.
- **Perf**: `spikes/perf_budget.py` 예산표 전 항목.
- **수동 (Studio Pro 8.1)**: 05-automation, 06-track-empty, 07-track-events 개봉·재생 + AC-6/AC-8 확정.

## Acceptance Criteria
스펙 AC-1~AC-11 승계 (`.omc/specs/deep-interview-song-mix-gui-v2.md`).

## Open Questions
1. AutomationTrack이 tracks List 말미 삽입으로 순서 무관하게 수용되는가? → S3a에서 판정
2. 빈 MediaTrack(Events 없음)을 S1이 정상 표시하는가, Events 빈 List가 필요한가? → S4a에서 두 변형 비교
3. QtWebEngine 콜드 스타트 하한 실측치 → P1
4. 신규 MediaTrack이 LauncherCell 엔트리 없이 정상 개봉되는가? → S4a 수동 게이트 관찰 항목

## ADR

- **Decision**: v1 안전 아키텍처(원시 보존·텍스트 수술·fail-closed·수동 게이트)를 불변 기반으로 두고, v2를 U(사용성)→P(성능)→S(범위확장) 순서로 증분 배송한다. 단 최대 리스크 축(song.xml 신규 쓰기 3종)의 스파이크 파일+수동 게이트는 t=0에 병렬 발사한다. Undo는 파일 바이트 스냅샷 스택, 비교는 해석 캐시 재사용+Python diff 서비스, 프리웜 우선순위는 플러그인 그룹 입도로 구현한다.
- **Drivers**: ① 일상 조작 마찰 제거(사용자 1순위 지정) ② song.xml 신규 쓰기의 Studio One 수용성(최대 기술 리스크) ③ 기존 262 테스트+E2E 회귀 담보.
- **Alternatives considered**: 연산 역산 Undo(fail-closed 증명 불가로 기각), 실시간 이중 로드 비교(성능 예산 위반), 일괄 구현 후 검증(실패 축 분리 불가 — v1 교훈), 항목 단위 프리웜 큐(배치 효율 파괴 — Critic 지적으로 그룹 입도로 수정), 리스크 우선 배송(사용자 우선순위 지정과 충돌 — 스파이크만 선발사하는 synthesis 채택).
- **Why chosen**: 모든 신규 쓰기 축이 v1에서 검증된 패턴(최소 변형 스파이크→수동 게이트→본구현→fail-closed 확장)의 반복이라 리스크가 구조적으로 관리되고, 사용자 지정 우선순위와 리스크 조기 소각을 스파이크 병렬 발사로 동시에 만족하기 때문.
- **Consequences**: (+) U 배송 중 S의 최대 미지수가 백그라운드에서 소각, 실패 시 조기 재설계. (−) 수동 게이트 2회 대기(사용자 가용성 의존), song_parser.py 신설 스코프 추가, 프리웜 진행률 입도가 그룹 단위로 제한.
- **Follow-ups**: S3a/S4a/S4c 결과에 따라 Open Questions 1·2·4 판정 반영; P1 실측치로 시작<3s 예산 확정 또는 근거 있는 재협상; v1 잔여 수동 게이트 4건 확인 결과 수신.

## Changelog (컨센서스 반영 내역)
- **Architect 1차 (APPROVE 조건부, 5건 반영)**: ① 스파이크 3종(S3a/S4a/S4c) 생성·수동 게이트 제출을 t=0 병렬 발사로 이동(Phase 0-S 신설) — 사용자 가치 우선(U 먼저)과 리스크 조기 소각의 synthesis; ② uid_refs.validate() fail-closed 확장 3종 명시(param:/// dangling, channelID 실재, trackID 유일)+대응 pytest+29곡 보정; ③ 프리웜 큐 재정렬 스레드 안전성(락) 명시; ④ S4 수동 체크리스트에 LauncherCell/arranger 교차참조 항목+S3 비대칭 기록; ⑤ Undo 스냅샷 소스=덮어쓰기 직전 디스크 바이트로 확정, 신규 경로 저장 undo 비대상+외부 수정 시 스택 무효화 명시.
- Architect 실측 검증 통과 항목: AutomationTrack/MediaTrack 구조(song.xml 실파일 대조), uid_map 재매핑 성립(transfer.py:178-236), Envelopes 라벨 URL 유효성(transfer.py:257), song.xml이 신규 쓰기 축이라는 전제.
- **Critic 1차 (REVISE → 반영 완료)**: MAJOR① P3 프리웜 우선순위를 항목 단위 큐에서 **플러그인 그룹 입도**로 재정의(배치 효율 보존, prewarm_status() 신설, 진행률 입도=그룹 단위를 AC-5 판정 기준에 명시, 구조 전환은 측정 후 게이트 뒤로); MAJOR② AC-4 검증 강화 — diff 계산을 `engine/introspect/compare.py`(Python)로 분리해 pytest 직접 검증 + E2E는 공유 플러그인 채널·캐시 워밍 선행·value-diff 행 강조 단언으로 구체화; Minor① song.xml 트랙 파서(`song_parser.py`) 신설 스코프 명시; Minor② Undo push 시점 명문화(브리지가 save_pipeline 호출 직전) + 크래시 잔존물 정리; Minor③ 원칙 5에 전송+저장<3s 추가; Minor④ AutomationTrack trackNumber 속성 없음 실측 기록; Phase 0-S 사용자 가용성 의존 명시(미확인 시 조건부 패턴 유지).
