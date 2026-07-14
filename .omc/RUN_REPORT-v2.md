# RUN REPORT v2 — song-mix-gui 사용성/성능/범위확장 (2026-07-13)

Phase 0-S → U → P → S → V → V-followup → V-followup2 전부 실행 완료. **26 스토리 중 26 통과**
(엔진/브리지/프론트/pytest/E2E 레벨).
자동 테스트: **엔진 262(v1) + 272(v2 신규) = 534개 + GUI 헤드리스 self-test/E2E 전부 통과.**

**Studio One 8.1 수동 게이트 05/06/07 전부 통과 (2026-07-13, 사용자 확인)** — v2 최대 기술
리스크(song.xml 신규 쓰기 축: AutomationTrack/MediaTrack)의 Studio One 수용성이 실측으로
확정됐다. 상세: [MANUAL_CHECKLIST.md](MANUAL_CHECKLIST.md). Open Question 1(오토메이션
삽입 순서 무관), 2(빈 MediaTrack에 Events 리스트 자체가 없어도 정상), 4(LauncherCell
미기재 허용) 전부 해소 — **더 이상 조건부 항목 없음, v2 전체 정식 통과.**

**V-followup(같은 세션, 사용자 "계속 진행" 지시로 이어서 완료)**: 1차 완료 시점에 note로만
남겨뒀던 프론트 배선 3건(P3 hint_visible 자동 호출/프리웜 진행률 폴링 UI, S4b 트랙 전송
다이얼로그 — engine transfer_track() 함수는 있었지만 브리지 슬롯 자체가 전혀 없었던 실제 갭)을
마저 구현. 이로써 AC-5가 조건부→통과로, AC-6은 "Studio One 게이트만 남음"으로 승격.

**V-followup2(사용자 "계속 진행" 재요청)**: 완료 상태를 다시 검토하다 안전 공백을 발견 —
다수 pytest가 src로 실제 코퍼스 경로(NAIITE 등)를 직접 읽어 쓰는데, v1의 "원본 절대 수정 금지"
원칙을 스위트 차원에서 자동 강제하는 안전망이 없었음. `engine/tests/conftest.py` 신설
(세션 스코프 autouse fixture, 116곡 md5를 스위트 실행 전/후 비교)으로 보강.

**아키텍트(Opus) 최종 검증 통과**: CRITICAL/HIGH 0건. v1 불가침 원칙(원본 무수정·텍스트 수술·fail-closed·
.bak+잠금검사), fail-closed 확장 3종의 severity 비대칭 로직, 보안(경로 조작/인젝션) 전부 확인 완료.
지적된 LOW 2건(trackNumber 결측 센티널 오탐 가능성, Events 제거의 비-깊이인식 정규식)은 즉시 수정 반영.
디슬롭 패스로 transfer_subtree/transfer_track의 중복 파일 복사 로직을 `_copy_channel_files()`로 통합,
미사용 죽은 변수 2개 제거.

## 실행 방법

```bash
# GUI 앱
python app/main.py

# 엔진 테스트 전체 (534개, ~8.4s)
python -m pytest engine/tests -q

# GUI 헤드리스 E2E (Undo/검색/최근파일/비교/체인이식/전송 전 시나리오 포함)
QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python app/e2e_test.py

# 성능 계측 (P1)
PYTHONIOENCODING=utf-8 python spikes/perf_budget.py

# 프론트 재빌드
cd app/frontend && npm run build
```

## 돌아와서 해야 할 일 → [MANUAL_CHECKLIST.md](MANUAL_CHECKLIST.md)

Studio Pro 8.1로 `.omc/verify/`의 v2 검증 파일 3개를 **대상 곡 폴더 안에 사본으로 배치 후** 열어 확인:

| # | 파일 | 확인 내용 |
|---|---|---|
| 05 | 05-automation-transfer.song | 버스 오토메이션(AutomationTrack) 수용 여부 |
| 06 | 06-track-transfer-empty.song | 빈 트랙 전송 + LauncherCell 없이 정상 개봉 여부 |
| 07 | 07-track-transfer-events.song | 이벤트 포함 트랙 전송 + 미디어 재링크 여부 |

v1 잔여: S0.3 잠금 실측 (문서화 목적, 기능 영향 없음) — 아직 미확인이면 이월.

## AC-1 ~ AC-11 판정

| AC | 내용 | 판정 | 근거 |
|---|---|---|---|
| AC-1 | Undo: 전송→전송→Ctrl+Z→Ctrl+Z 역순 복원 + 재검증 | **통과** | pytest 5종(무효화 케이스 포함) + E2E(전송→Undo→노드 원복, `복원됨` 메시지) |
| AC-2 | 검색: "CLA-76" 하이라이트 == 실제 사용 채널 수 | **통과** | E2E: `matches=6` == 모델에서 계산한 실제 사용 수 |
| AC-3 | 최근 파일: 재시작 후에도 목록 노출 + 클릭 열기 | **통과** | QSettings 영속 저장, E2E: `naiite_recorded=True` |
| AC-4 | 비교 뷰: 나란히 표시 + 값 차이 색 강조 | **통과** | compare.py pytest 6종 + E2E: `valueDiffRows=3`(K.BUS/S.BUS Pro-Q 3) |
| AC-5 | 성능: 시작<3s, 열기<1s, 미캐시 진행률 즉시 표시 + 가시 채널 우선 프리웜 | **통과** | perf_budget.py 4항목 전부 예산 대비 큰 여유로 PASS(시작 0.43s, 열기 0.51s, 캐시해석 0.001s, 전송저장 0.07s). hint_visible()/prewarm_status() 엔진+브리지+프론트(문서 로드 시 자동 hint 호출, 800ms 폴링 진행률 UI) 전부 완성. E2E: `prewarm_status={'done':0,'total':12}`로 실제 미캐시 그룹 반영 확인 |
| AC-6 | 트랙 전송: 빈 트랙 기본 + 이벤트 옵션 + Studio One 정상 개봉 | **통과** | `transfer_track()` 엔진(RecordUnit 미전송, 덮어쓰기 미지원=YAGNI) + 브리지 슬롯 + 다이얼로그 UI(이벤트 포함 체크박스) 전부 완성. pytest 8종 + E2E(kick out 트랙 DnD 전송→다이얼로그→재파싱에서 실제 채널 생성 확인) 통과. **Studio One 수동 게이트 06/07 통과(2026-07-13) — 빈 트랙 정상 개봉+LauncherCell 미기재로 충분, 이벤트 포함 트랙 재생 정상** |
| AC-7 | 체인 이식: 기존 채널(트랙 포함)에 체인만 교체 UI | **통과** | Ctrl+우클릭 복사 → 대상 우클릭 교체 확인 다이얼로그. E2E: 빈 체인(TOM M)이 guitar1과 동일 체인으로 교체 확인. **실제 버그 발견·수정**: 체인 클립보드가 소모되지 않아 이후 평범한 우클릭이 계속 붙여넣기로 오인식되던 회귀 |
| AC-8 | 오토메이션: 버스 전송 시 볼륨/팬 오토메이션이 실제 동작 | **통과** | `transfer_subtree`가 AutomationTrack 자동 동반 전송, validate() fail-closed 확장 3종(116곡 무오탐), pytest 4종 통과. **Studio One 수동 게이트 05 통과(2026-07-13) — DR BUS vol 레인 정상 표시+바인딩, 기존 재생 무영향** |
| AC-9 | send 보존: 동명 채널 있으면 연결 유지(옵션) | **통과** | 엔진(`preserve_external_sends`) + 브리지 + 툴바 상시 토글 UI. E2E로 전체 흐름 회귀 확인 |
| AC-10 | UI/UX: 그룹 범례 + 진행 피드백 + 단축키 도움말 | **통과** | 범례(4색), 상태바 스피너, `?` 단축키 모달, 파라미터 테이블 정렬/필터 |
| AC-11 | 회귀: v1 전체 + 신규 기능 pytest/E2E 유지 | **통과** | pytest 534 passed(0 실패), E2E PASS(신규 시나리오 전부 포함) |

## 스토리 현황 (prd.json 기준)

- **완전 통과 (26/26)**: 전체 스토리(스파이크 3종 + US-V2-001~022 + 게이트 4종) 전부 `passes: true`
- **조건부 요소 없음**: AC-1~AC-11 전부 정식 통과 (Studio One 수동 게이트 05/06/07 전부 통과, 2026-07-13)
- **BLOCKED (0)**
- 잔여(기능 영향 없음, 문서화 목적): v1 S0.3 잠금 실측 미확인

## 이번 세션 핵심 발견 (실측 기반, 재발견 비용 큼)

1. **song.xml Tracks 리스트는 대문자** `<List x:id="Tracks">` — 계획 문서 표기(소문자)는 오타였음.
2. **AutomationTrack에는 trackNumber 속성 없음** (실측 확인, 계획의 예측 적중).
3. **MediaTrack mediaType 구분이 필수**: `mediaType="Audio"`만 audiomixer 채널을 참조. `mediaType="Music"`(악기/MIDI 트랙, 실측: song3/song1.song "MODO DRUM")은 `Devices/musictrackdevice.xml`의 별도 채널을 참조 — v2 범위 밖. 이 구분 없이 dangling 검사를 걸면 코퍼스 전체에서 19건 오탐.
4. **원본 코퍼스에 스테일 오토메이션 dangling이 실존** (naiite_20의 삭제된 구 S.BUS UID 참조, notepad.xml 스테일 UID와 동일 현상) — fail-closed 신규 검사는 `require_console_for` 기반 error/warning 비대칭을 반드시 적용해야 함(안 그러면 정상 파일 저장이 항상 실패하는 회귀 발생).
5. **List 태그는 중첩됨** (Tracks 안에 MediaTrack의 Events 등) — song.xml 삽입 위치를 찾을 때 첫 `</List>` 단순 검색은 위험, 태그 깊이 카운팅 필요.
6. **RecordUnit(트랙 입력 라우팅)은 전송하지 않음** — 소스 전용 하드웨어 참조, v1 채널 COPY의 "입력 없음" 설계 원칙과 동일하게 적용.
7. **체인 클립보드 소모 버그**: Ctrl+우클릭 체인 복사 후 클립보드를 리셋하지 않으면 이후 모든 평범한 우클릭이 "체인 붙여넣기"로 오인식되어 서브트리 복사가 막힘 — E2E로 실제 발견·수정.
8. **엔진 완성 ≠ 브리지 연결**: `transfer_track()` 엔진 함수와 pytest 8종이 이미 있었음에도
   main.py에는 이를 호출하는 브리지 슬롯이 전혀 없었음(grep으로 실측 확인) — "pytest 통과"만으로
   기능이 실제로 GUI에서 쓸 수 있다고 판단하면 안 되고, 브리지/프론트 배선까지 확인해야 함.
9. **드래그 가능 여부 변경의 파급 효과**: 트랙 노드를 draggable로 바꾸자 `drag-hint`(⠿) span이
   라벨에 붙어 기존 E2E의 정확 텍스트 매칭(`=== '1 - guitar 1'`)이 깨질 뻔함 — `startsWith` 매칭으로
   전환. UI 변경이 다른 기능의 셀렉터에 미치는 영향은 회귀 실행으로만 발견 가능.
10. **공유 clipboard.current를 여러 진입점이 다루는 다이얼로그는 소모(clear) 조건을 명시해야 함**:
    트랙 전송 확인 다이얼로그는 붙여넣기(clipboard 기반)와 드래그드롭(clipboard 무관) 두 경로 모두에서
    열릴 수 있는데, "확정 시 clipboard 리셋" 로직을 무조건 적용하면 드롭 경로가 사용자의 무관한 복사를
    조용히 지워버림 — 참조 동일성(`clipboard.current === payload`) 체크로 실제 소유자일 때만 소모하도록
    수정. 아키텍트 리뷰가 코드 읽기만으로 재현 시나리오까지 제시해 실제 E2E로 재현·수정한 사례.

## 산출물 지도

```
engine/songcore/song_parser.py   신규 — song.xml 트랙 파서(읽기 전용)
engine/songcore/undo.py          신규 — 세션 내 다단계 Undo(바이트 스냅샷 스택)
engine/songcore/transfer.py      확장 — 오토메이션 동반 전송, transfer_track(), send 보존 옵션
engine/songcore/uid_refs.py      확장 — fail-closed 검사 3종(오토메이션/트랙 채널/trackID 유일성)
engine/introspect/compare.py     신규 — 체인 비교 diff 서비스
engine/introspect/service.py     확장 — 프리웜 그룹 큐(우선순위 재정렬, 진행률)
app/main.py                      확장 — undo/recent/compare/hint_visible/prewarm_status 브리지 슬롯
app/frontend/src/ComparePanel.tsx 신규 — 체인 비교 렌더
spikes/perf_budget.py            신규 — P1 성능 계측
spikes/spike_v2_tracks.py        신규 — Phase 0-S 스파이크 빌드 도구
.omc/verify/05~07*.song          신규 — 수동 게이트 대상 3종
engine/tests/                    신규 6개 파일(song_parser/compare/uid_refs_v2/transfer_automation/
                                  transfer_track/prewarm_priority) + test_undo.py, 총 272개 신규 pytest
engine/tests/conftest.py         신규 — 코퍼스 원본 불변성 안전망(세션 스코프 autouse fixture)
```
