# Deep Interview Spec: song-mix-gui v2 — 사용성·성능·범위 확장

## Metadata
- Interview ID: di-songmix-v2-20260712
- Rounds: 9 (+ Round 0 토폴로지 게이트)
- Final Ambiguity Score: 17%
- Type: brownfield
- Generated: 2026-07-12
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.86 | 0.35 | 0.301 |
| Constraint Clarity | 0.78 | 0.25 | 0.195 |
| Success Criteria | 0.78 | 0.25 | 0.195 |
| Context Clarity | 0.90 | 0.15 | 0.135 |
| **Total Clarity** | | | **0.826** |
| **Ambiguity** | | | **0.174** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| 유저 친화 기능 (**1순위**) | active | Undo·검색/필터·최근 파일·체인 비교 | AC-1~AC-4에서 커버 |
| 성능 개선 (2순위) | active | 시작·열기·해석·저장 4지점 수치 예산 | AC-5에서 커버 |
| 범위 확장 (3순위) | active | 트랙 채널 전송·체인 이식·버스 오토메이션·send 보존 | AC-6~AC-9에서 커버 |
| UI/UX 개선 | active | 그래프 가독성·피드백·조작감·시각 완성도 (사용성과 함께 배송) | AC-10에서 커버 |

## Goal
v1(완성·검증됨)의 song-mix-gui를 **일상 사용 도구** 수준으로 끌어올린다.
우선순위: **① 사용성(편의 기능+UI/UX) → ② 성능 → ③ 범위 확장.**
사용성은 세션 내 다단계 Undo, 그래프 검색/필터, 최근 파일/빠른 열기, 나란히+차이 강조 체인 비교 뷰.
성능은 "현실적 개선" 예산(시작<3s, 열기<1s, 미캐시 해석은 진행률 UI+우선순위 프리웜).
범위 확장은 트랙 채널 전송(기본 빈 트랙+옵션 이벤트 포함), 기존 트랙에 체인만 이식,
버스 오토메이션(song.xml AutomationRegion) 전송, 외부 send 보존 옵션.

## Constraints
- v1의 안전 원칙 전부 승계: 원본 무수정, 무손실 라운드트립(원시 entry 보존), .bak 백업, 잠금 차단, fail-closed 스캐너, 텍스트 수술(재직렬화 금지).
- Undo: **세션 내 다단계** — 파일별 스택, 앱 종료 시 소멸. 전송/덮어쓰기/저장 작업 단위로 push, Ctrl+Z 역순 복원.
- 트랙 채널 전송 기본값은 **빈 트랙+믹서 세팅**(song.xml MediaTrack + 채널 + 체인 + 라우팅, 이벤트 제외). "이벤트 포함"은 명시적 옵션 — mediapool.xml 참조 및 오디오 파일 경로 유효성 처리는 계획 단계에서 설계(경로 깨짐 시 사용자 경고 필수).
- 버스 오토메이션 전송: song.xml AutomationRegion 생성 + Envelopes/ 복사 + param:///AudioMixer/{UID} identity의 신규 UID 재매핑.
- 외부 send 보존: 서브트리 밖 send 대상과 **동명 채널이 대상 song에 존재하면 연결**, 없으면 기존대로 제거+기록 (옵션).
- 성능 예산: 앱 시작 <3s, song 열기→그래프 <1s, 캐시 해석 <0.3s, 미캐시 해석은 진행률 표시+선택 채널 우선 프리웜, 전송+저장 <3s.
- 비교 뷰: 슬롯 순서대로 나란히, 동일 플러그인은 파라미터 값 차이를 색으로 강조, 체인 불일치(다른 플러그인/슬롯)도 표시.
- 검색/필터: 채널·플러그인 이름 검색 → 그래프 내 해당 노드 하이라이트/포커스, 특정 플러그인 사용 채널만 필터.
- 플랫폼/스택 변경 없음: PySide6+QWebEngineView+React Flow+pedalboard (A′ 유지).

## Non-Goals
- Studio One 실시간 연동 없음 (v1과 동일).
- 오디오 렌더링/재생 기능 없음.
- 이벤트 포함 전송 시 오디오 파일 자체의 복사/이동은 비범위 (참조만 전송, 경로 깨짐은 경고로 처리).
- macOS 지원 없음.
- 앱 재시작 후에도 유지되는 영구 Undo 히스토리 없음 (.bak은 기존대로 유지).

## Acceptance Criteria
- [ ] AC-1 (Undo): 전송→전송→Ctrl+Z→Ctrl+Z 하면 대상 song이 각 단계 역순으로 원상 복구되고, 복원 후 재파싱+무결성 검사가 통과한다. 스택은 파일별로 독립.
- [ ] AC-2 (검색): 검색창에 "CLA-76" 입력 시 CLA-76을 쓰는 채널 노드들이 하이라이트되고 첫 결과로 뷰포트가 이동한다. 채널명 검색도 동일.
- [ ] AC-3 (최근 파일): 앱 재시작 후에도 최근 연 song 목록이 보이고 클릭 한 번으로 열린다.
- [ ] AC-4 (비교 뷰): 두 채널을 선택해 비교하면 체인이 슬롯 순서대로 나란히 표시되고, 동일 플러그인의 파라미터 값 차이가 색으로 강조된다.
- [ ] AC-5 (성능): 앱 시작 <3초, song 열기→그래프 표시 <1초(naiite_14 기준), 미캐시 해석 클릭 시 진행률 인디케이터가 즉시 표시되며 프리웜은 현재 보이는/선택된 채널을 우선한다.
- [ ] AC-6 (트랙 전송): 트랙 채널을 다른 song에 전송하면 빈 트랙+채널+체인+라우팅이 생성되고 Studio Pro 8.1에서 정상 개봉된다(수동 게이트). "이벤트 포함" 옵션 시 클립까지 보이며, 미디어 경로가 깨지면 전송 전에 경고한다.
- [ ] AC-7 (체인 이식): 기존 트랙 채널에 소스 채널의 체인만 덮어쓰는 UI 경로가 있다 (엔진 replace_insert_chain 활용).
- [ ] AC-8 (오토메이션): 버스 서브트리 전송 시 볼륨/팬 오토메이션이 대상에서 실제로 동작한다 (song.xml 리전 + 재매핑 UID, Studio One 수동 확인 게이트).
- [ ] AC-9 (send 보존): 외부 send 대상과 동명 채널이 대상에 있으면 send가 연결된 채로 전송된다 (옵션 활성 시).
- [ ] AC-10 (UI/UX): 트랙/버스/FX 그룹이 시각적으로 구분되고, 모든 비동기 작업(전송·해석·프리웜)에 로딩/진행 피드백이 있으며, 단축키 목록이 앱 내에서 확인 가능하다.
- [ ] AC-11 (회귀): v1 자동 테스트 전체(261+) + E2E가 계속 통과하고, 새 기능도 동급의 pytest/E2E 커버리지를 가진다.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| 4개 워크스트림이 병렬 동급 | Contrarian: 하나만 지킬 수 있다면? | **사용성 1순위** → 성능 → 범위 확장 |
| Undo는 .bak 복원으로 충분 | Simplifier: 가장 단순한 버전? | 아니오 — **세션 내 다단계** 필요 |
| 트랙 전송 = 통짜 복사 | 이벤트/미디어 경계 질문 | 기본 빈 트랙, **이벤트 포함은 옵션** |
| "빠르게"면 충분 | 수치 예산 요구 | "현실적 개선" 예산 채택 (시작<3s 등) |
| 비교는 눈으로 하면 됨 | 합격 형태 질문 | **나란히 + 차이 색 강조** 필수 |

## Technical Context
- v1 코드베이스 (동일 세션 구현·검증): engine/songcore (컨테이너·파서·토폴로지·스캐너·전송), engine/introspect (인벤토리·해석+프리웜), app/main.py (브리지·저장 파이프라인), app/frontend (React Flow).
- Undo 구현 힌트: save_pipeline이 이미 .bak을 만들므로, 다단계는 저장 전 전체 파일 바이트 스냅샷을 세션 임시 폴더에 push하는 방식이 원시 보존 원칙과 정합.
- 오토메이션 전송은 v1에서 유일하게 남은 "송장 없는 참조 축"(param:///AudioMixer/{UID}) — S0.1(b-3) 카탈로그와 uid_refs 스캐너가 이미 이 형태를 알고 있음.
- 외부 send 보존은 transfer.py의 clean_sends 지점에서 대상 모델의 라벨 매칭으로 분기.
- 성능: 시작 지연의 주원인은 QtWebEngine 초기화 — 지연 로딩/스플래시 검토. 프리웜 우선순위는 브리지에 "현재 보이는 채널" 힌트 전달로 구현 가능.
- **미해결 수동 게이트 (v1 승계)**: .omc/MANUAL_CHECKLIST.md의 Studio Pro 8.1 개봉 확인 4건 — v2의 트랙/오토메이션 전송도 동일한 수동 게이트 필요.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| SongFile | core domain | path, channels, undo stack | has many Channel, UndoStep |
| TrackChannel | core domain | track def(song.xml), channel, chain, events? | routes to Bus; has MediaEvent(옵션) |
| InsertChain | core domain | ordered inserts, presets | belongs to Channel; comparable |
| AutomationRegion | core domain | identity(param:///…/{UID}), envelope ref | belongs to Channel; transferred with subtree |
| Send | core domain | source, destination | preserved if 동명 대상 존재(옵션) |
| TransferOperation | core domain | scope(bus/track/chain), options(events, sends) | produces UndoStep |
| UndoStack | supporting | per-file steps, session-scoped | restores SongFile bytes |
| SearchQuery | supporting | text, type(channel/plugin) | highlights GraphView nodes |
| ChainComparison | supporting | left/right channel, param diffs | renders side-by-side view |
| MediaEvent | supporting | clip refs, mediapool entry | optional transfer payload |
| PerfBudget | supporting | startup<3s, open<1s, cached<0.3s | gates AC-5 |
| GraphView | supporting | nodes, groups, highlight state | visualizes SongFile |
| RecentFiles | supporting | persisted list | opens SongFile |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 6 | 6 | - | - | N/A |
| 2 | 9 | 3 | 0 | 6 | 100% |
| 3 | 10 | 1 | 0 | 9 | 100% |
| 4 | 11 | 1 | 0 | 10 | 100% |
| 5 | 11 | 0 | 0 | 11 | 100% |
| 6 | 12 | 1 | 0 | 11 | 100% |
| 7 | 13 | 1 | 0 | 12 | 100% |
| 8 | 13 | 0 | 0 | 13 | 100% |
| 9 | 13 | 0 | 0 | 13 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (Round 0 + 9 rounds)</summary>

### Round 0 (토폴로지 게이트)
**Q:** 4개 컴포넌트(범위 확장/성능/UI-UX/유저 친화 기능)로 읽었는데 맞나요?
**A:** 맞음 — 4개 그대로.

### Round 1
**Q:** 2차 범위 확장으로 반드시 들어가야 할 기능은? (v1 비범위 목록 제시)
**A:** 트랙 채널 전송, 기존 트랙에 체인만 이식, 버스 오토메이션 전송, 외부 send 보존 옵션 — 전부.
**Ambiguity:** 62%

### Round 2
**Q:** 편의 기능은 구체적으로?
**A:** Undo, 검색/필터, 최근 파일/빠른 열기, 프리셋/체인 비교 — 전부.
**Ambiguity:** 55%

### Round 3
**Q:** 어디가 느린가? (체감 기준)
**A:** 파라미터 첫 해석, song 열기/그래프, 전송/저장, 앱 시작 — 전부.
**Ambiguity:** 50%

### Round 4
**Q:** UI/UX 불편 지점은?
**A:** 그래프 가독성, 상호작용 피드백, 키보드/조작감, 시각 완성도 — 전부.
**Ambiguity:** 45%

### Round 5 (Contrarian)
**Q:** 하나만 지킬 수 있다면? 정말 버릴 게 없나?
**A:** **사용성이 1순위.**
**Ambiguity:** 38%

### Round 6 (Simplifier)
**Q:** Undo의 가장 단순하면서 충분한 버전은?
**A:** 세션 내 다단계 Undo (마지막 1회 복원으로는 부족).
**Ambiguity:** 34%

### Round 7
**Q:** 트랙 채널 전송은 무엇까지 함께 가나?
**A:** 둘 다 옵션으로 — 기본 빈 트랙+믹서 세팅, 옵션으로 이벤트 포함.
**Ambiguity:** 30%

### Round 8
**Q:** 성능 합격선은? (현재 수치 제시)
**A:** 현실적 개선 — 시작<3s, 열기<1s, 미캐시는 진행률 UI+우선순위 프리웜.
**Ambiguity:** 23%

### Round 9
**Q:** 체인 비교 뷰의 합격 형태는?
**A:** 나란히 + 차이 색 강조.
**Ambiguity:** 17% — PASSED

</details>
