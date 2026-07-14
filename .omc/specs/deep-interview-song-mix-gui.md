# Deep Interview Spec: Studio One .song 믹스 분석·시각화·병렬 전개 GUI 툴

## Metadata
- Interview ID: di-naiite14-tool-20260711
- Rounds: 6 (+ Round 0 토폴로지 게이트)
- Final Ambiguity Score: 15.9%
- Type: greenfield
- Generated: 2026-07-11
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.88 | 0.40 | 0.352 |
| Constraint Clarity | 0.78 | 0.30 | 0.234 |
| Success Criteria | 0.85 | 0.30 | 0.255 |
| **Total Clarity** | | | **0.841** |
| **Ambiguity** | | | **0.159** |

## Topology
| Component | Status | Description | Coverage / Deferral Note |
|-----------|--------|-------------|--------------------------|
| Parser | active | .song(zip) 압축 해제 → audiomixer.xml + vstpreset 파싱 → 채널/체인/라우팅 추출 | AC-1, AC-2에서 커버 |
| Visualization GUI | active | 채널→버스→MIXOUT 계층 흐름 + 플러그인 체인을 GUI로 표시 | AC-3에서 커버 |
| Template Apply (병렬 전개) | active | 탭/좌우 스플릿으로 여러 song을 열고 드래그앤드롭·복붙으로 채널/버스 구조를 대상 song에 직접 기록 | AC-4, AC-5, AC-6에서 커버 |
| Plugin Inventory | active | 설치된 VST를 활용해 vstpreset의 파라미터를 사람이 읽을 수 있는 이름/값으로 해석 | AC-7에서 커버 |

## Goal
Studio One(현재 Studio Pro 8.1, 문서 포맷 버전 9) .song 파일을 zip으로 열어 채널별 플러그인 체인(순서 포함), 세팅값, 버스 라우팅(채널→버스→MIXOUT)을 계층적으로 시각화하고, 여러 .song 파일을 탭 또는 좌우 스플릿으로 나란히 열어 채널 세팅·버스 서브트리를 드래그앤드롭/복붙으로 다른 .song 파일에 직접 기록(적용)할 수 있는 데스크톱 GUI 툴을 만든다. 플러그인 세팅값은 원본 바이너리 그대로의 복사·전송뿐 아니라, 사용자의 song 라이브러리에 실제 사용된 플러그인에 한해 파라미터 이름/값 수준으로 해석해 표시한다.

## Constraints
- 대상 포맷: Studio Pro 8.1 / Document:FormatVersion 9 (사용자 라이브러리 전체가 이 계열). 다른 버전 호환은 발견 시 대응.
- 쓰기 안전: Studio One이 해당 .song을 열고 있는 동안 쓰기 금지(강제). 저장 시 원본 자동 백업(.bak) 후 원본 경로에 덮어쓰기.
- 파라미터 해석 범위: 사용자의 `C:\Users\yhkze\Documents\Studio Pro\Songs` (116개 .song)에서 실사용된 약 22종 플러그인 우선. 미해석 플러그인도 바이너리 그대로 복사/전송은 항상 가능해야 함.
- 실사용 플러그인 목록 (스캔 결과, 사용 빈도순): Waves CLA-76, Soundtoys Decapitator, Waves SSLComp, Waves Maag EQ2, FabFilter Pro-Q 3, JST Clip, SPL Transient Designer Plus, JST Gain Reduction Deluxe, mvMeter2, Waves L4 Ultramaximizer, SPL Attacker Plus, Soundtoys Little Plate, Soundtoys Little MicroShift, Waves Scheps Omni Channel 2, IK AmpliTube 5, Waves EQP-1A, Slate Trigger 2, Soundtoys Devil-Loc, FabFilter Pro-Q, Magma StressBox, Waves De Esser, FabFilter Pro-R.
- 플러그인 설치 위치: `C:\Program Files\FabFilter`, `C:\Program Files\VstPlugIns` 등 (VST2/VST3 혼재 가능, Waves는 shell 방식 유의).
- 전송 충돌 정책: 대상에 같은 이름의 채널/버스가 있으면 확인 팝업 후 덮어쓰기(인서트 체인/세팅 교체).
- 플랫폼: Windows 11 (사용자 환경 기준).
- .song 포맷은 비공식(문서화 안 됨) — 파싱/쓰기 로직은 라운드트립 검증(쓰고 다시 읽어 동일성 확인)을 갖춰야 함.

## Non-Goals
- Studio One 실행 중 실시간 연동(라이브 리모트 컨트롤) 없음 — 파일 기반 오프라인 편집 전용.
- 오디오 데이터(웨이브폼, 이벤트, 미디어풀) 편집 없음 — 믹서 토폴로지·인서트·세팅만 다룸.
- 전 세계 모든 플러그인의 파라미터 해석 — 사용자 라이브러리 실사용분 우선, 나머지는 필요 시 확장.
- macOS 지원.

## Acceptance Criteria
- [ ] AC-1: naiite_14.song을 열면 압축 해제 없이(내부 처리) 19트랙 채널·버스 구조와 각 채널의 인서트 체인이 순서대로 추출된다.
- [ ] AC-2: audiomixer.xml의 라우팅이 채널→버스→MIXOUT 계층 그래프 데이터로 변환된다 (예: kick, kick out → K.BUS → DR.B → MIXOUT).
- [ ] AC-3: GUI에서 이 계층이 순차적·계층적으로 시각화되고, 각 노드에서 플러그인 체인(예: K.BUS = Pro-Q 3 → SPL Transient Designer → CLA-76 → JST Clip)이 순서대로 보인다.
- [ ] AC-4: 두 번째 .song을 탭 또는 좌우 스플릿으로 열고, 소스의 채널 하나 또는 버스 서브트리(예: K.BUS+S.BUS+T.BUS+CYM.BUS→DR.B)를 드래그앤드롭/복붙으로 대상에 옮길 수 있다.
- [ ] AC-5: 저장 시 원본이 .bak으로 백업되고, Studio One이 파일을 열고 있으면 쓰기가 차단되며, 저장된 파일을 Studio Pro 8.1에서 열면 라우팅·플러그인·세팅이 그대로 살아 있고 정상 재생된다.
- [ ] AC-6: 이름 충돌 시 확인 팝업 후 덮어쓰기가 동작한다.
- [ ] AC-7: 실사용 플러그인(최소 Pro-Q 3, CLA-76 포함)의 vstpreset 세팅값이 파라미터 이름/값으로 사람이 읽을 수 있게 표시된다. 미해석 플러그인은 "해석 불가(복사 가능)"로 표시된다.

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| "병렬 전개"의 의미 | 직접 수정 vs 프리셋 생성 vs 가이드? | 탭/스플릿 멀티 song 뷰에서 드래그앤드롭·복붙으로 직접 기록 (A+B 하이브리드) |
| 플러그인 폴더 스캔의 목적 | 단순 설치 확인? | 파라미터 정의를 불러와 세팅값을 의미 있게 해석 + 세팅 복붙 지원 |
| 시각화만으로 충분한가 | 합격 기준은? | 시각화 + 서브트리 전송 + Studio One 정상 재생 + 파라미터 해석까지 필수 |
| 모든 플러그인 파라미터 해석 가능 (Contrarian) | vstpreset은 대부분 비공개 chunk | 사용자 Songs 폴더 실사용 22종 우선, 필요 시 확장. 호스팅 방식이 유일한 일반해 |
| 저장 방식 | 파일 손상 리스크 | 자동 백업(.bak) + 덮어쓰기, Studio One 열림 시 쓰기 금지 강제 |
| 충돌 처리 (Simplifier) | 가장 단순한 동작은? | 이름 같으면 확인 후 덮어쓰기 |

## Technical Context

### .song 파일 구조 (naiite_14 실측)
- .song = zip 컨테이너. 핵심 파일:
  - `Devices/audiomixer.xml` (144KB): 채널/버스/센드 라우팅 + 인서트 슬롯 정의
  - `Devices/mixerconsole.xml`: 믹서 콘솔 레이아웃
  - `Presets/Channels/<채널명>/<N> - <플러그인명>.vstpreset`: 채널별 플러그인 체인(파일명 순번 = 체인 순서), VST3 표준 vstpreset 컨테이너(내부는 벤더 chunk)
  - `Song/song.xml`, `metainfo.xml`(버전/템포/트랙수), `Envelopes/`(볼륨/팬 오토메이션)
- 확인된 버스 구조: kick/SN/TOM/OVER/HI HAT/RIDE → K.BUS/S.BUS/T.BUS/CYM.BUS → DR.B(+DR Parallel), guitar → GT.B, bass → BASS.B, FX 1(Little Plate 리버브 센드), 최종 MIXOUT(SSLComp → Pro-Q 3 → L4).

### 기술스택 권고 (계획 단계에서 확정)
- **파서/쓰기**: 어떤 언어든 가능(zip + XML). 라운드트립 무손실이 핵심 요건 — XML 원형 보존 파서 필요.
- **파라미터 해석**: 22종 벤더 chunk 역공학은 비현실적 → **설치된 VST를 실제 로드해 preset 주입 후 파라미터를 읽는 호스팅 방식**이 일반해.
  - 후보 1: Python + Spotify **pedalboard** (VST3 로드/파라미터 열거 지원, 헤드리스 가능) — 개발 속도 최고
  - 후보 2: **JUCE**(C++) 헬퍼 CLI — 가장 견고, VST2/VST3/Waves shell 대응력 높음
- **GUI**: 계층 그래프 + 듀얼 패널 + 드래그앤드롭 요건 →
  - 후보 1: **Tauri 또는 Electron + React + React Flow** (노드 그래프 시각화에 최적, 드래그앤드롭 성숙)
  - 후보 2: PySide6/Qt + NodeGraphQt (Python 단일 스택으로 통일 가능)
- 권고 조합: **Electron(또는 Tauri) + React Flow 프론트 + Python(pedalboard) 사이드카**로 파싱·해석 담당, 또는 전체 Python(PySide6) 단일 스택. 최종 선택은 플래닝 단계에서 pedalboard의 Waves shell 플러그인 지원 여부 검증 후 확정.

### 리스크
- Waves 플러그인은 shell(WaveShell) 구조라 개별 플러그인 로드가 까다로움 — 호스팅 PoC를 최우선 스파이크로.
- .song 쓰기 후 Studio One이 거부하는 케이스 대비: 라운드트립 테스트(수정 없이 읽고 쓴 파일이 원본과 기능적으로 동일한지)를 파서 1차 완성 기준으로 삼을 것.

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Song File | core domain | path, format version, channels, buses | has many Channel, Bus; belongs to Song Library |
| Channel | core domain | name, type(track/bus), inserts, output target | routes to Bus/Main Out; has Plugin Chain |
| Bus | core domain | name, children, inserts, output target | aggregates Channels; routes to Bus/Main Out |
| Main Out (MIXOUT) | core domain | master chain | terminal node of Routing |
| Routing | core domain | source→destination edges | connects Channel/Bus/Main Out |
| Plugin Chain | core domain | ordered inserts | belongs to Channel/Bus |
| Plugin Insert | core domain | plugin name, slot order, preset | references vstpreset, Installed Plugin |
| vstpreset | supporting | binary chunk, plugin id | decoded via Parameter Mapping |
| Plugin Parameter | supporting | name, value, range, unit | belongs to Installed Plugin |
| Installed Plugin | external system | vendor, format(VST2/3), install path | scanned from plugin folders |
| Parameter Mapping | supporting | preset→param values | links vstpreset to Plugin Parameter |
| Transfer Operation | core domain | source selection, target, conflict policy | copies Channel/Bus subtree between Song Files |
| Song Library | supporting | Songs folder path, 116 songs | contains Song Files; defines decode scope |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 9 | 9 | - | - | N/A |
| 2 | 12 | 3 | 0 | 9 | 75% |
| 3 | 12 | 0 | 0 | 12 | 100% |
| 4 | 13 | 1 | 0 | 12 | 92% |
| 5 | 13 | 0 | 0 | 13 | 100% |
| 6 | 13 | 0 | 0 | 13 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (Round 0 + 6 rounds)</summary>

### Round 0 (토폴로지 게이트)
**Q:** 4개 최상위 컴포넌트(파서/시각화/병렬 전개/플러그인 인벤토리)로 읽었는데 맞나요?
**A:** 네, 4개 모두 맞습니다.

### Round 1
**Q:** "다른 song 파일에 병렬 전개"가 정확히 무엇을 의미하나요? (직접 수정 / 프리셋 생성 / 가이드)
**A:** A+B — 여러 song 파일을 탭 혹은 좌우 스플릿으로 나눠서 드래그앤드롭·복붙으로 채널 설정이나 버스 구조를 그대로 옮겨 적용.
**Ambiguity:** 62.5% (Goal 0.60, Constraints 0.25, Criteria 0.20)

### Round 2
**Q:** 플러그인 폴더 스캔 기능의 실제 목적은?
**A:** 플러그인들의 세팅값·노브·값 범위를 불러와 무슨 의미인지 매칭하고 복붙 가능하게 하기 위함.
**Ambiguity:** 55.5% (Goal 0.70, Constraints 0.30, Criteria 0.25)

### Round 3
**Q:** 합격 시나리오 확인 — 시각화 + 버스 서브트리 전송 + Studio One 정상 재생이 핵심 기준인가?
**A:** 파라미터 해석까지 필수.
**Ambiguity:** 35.5% (Goal 0.75, Constraints 0.35, Criteria 0.80)

### Round 4 (Contrarian)
**Q:** "모든 플러그인 파라미터 해석 가능" 가정에 도전 — 호스팅 방식 vs 역공학 방식, 어느 범위면 합격?
**A:** 내 song 파일들(C:\Users\yhkze\Documents\Studio Pro\Songs)에 있는 것들 우선, 나머지는 필요 시 확장.
**Ambiguity:** 28.3% (Goal 0.78, Constraints 0.55, Criteria 0.80)

### Round 5
**Q:** 저장/백업 정책은? (Studio One 열림 시 쓰기 금지 강제 전제)
**A:** 자동 백업 + 덮어쓰기 (추천안 채택).
**Ambiguity:** 21.7% (Goal 0.78, Constraints 0.75, Criteria 0.82)

### Round 6 (Simplifier)
**Q:** 대상 song에 같은 이름의 채널/버스가 이미 있으면?
**A:** 이름 같으면 덮어쓰기(확인 후).
**Ambiguity:** 15.9% (Goal 0.88, Constraints 0.78, Criteria 0.85) — PASSED

</details>
