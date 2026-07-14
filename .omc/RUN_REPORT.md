# RUN REPORT — song-mix-gui 무인 실행 (2026-07-11)

Phase 0~5 전부 실행 완료. **26 스토리 중 26 통과 (완전 통과 20 + 조건부 6)**, BLOCKED 0.
자동 테스트: **엔진 261개 + GUI 헤드리스 self-test/E2E 전부 통과.**

## 실행 방법

```bash
# GUI 앱 (PySide6 + React Flow)
python app/main.py

# 엔진 테스트 전체 (261개, ~1.4s)
python -m pytest engine/tests -q

# GUI 헤드리스 E2E
QT_QPA_PLATFORM=offscreen python app/e2e_test.py

# 프론트 재빌드 (src 수정 시)
cd app/frontend && npm run build
```

## 돌아와서 해야 할 일 → [MANUAL_CHECKLIST.md](MANUAL_CHECKLIST.md)

Studio Pro 8.1로 `.omc/verify/`의 검증 파일 4개를 열어 확인 (열람만, 저장 금지):

| # | 파일 | 확인 내용 |
|---|---|---|
| 1 | 01-rename-bus.song | 버스 리네임 수용 (S0.1(b)) |
| 2 | 02-duplicate-channel-full.song | 채널 복제+동반 기재 수용 |
| 3 | 03-duplicate-channel-mixeronly.song | 동반 파일 필수성 판정 (b-2) |
| 4 | 04-engine-drum-transfer.song | 드럼 버스 서브트리 전송 결과 (Phase 1 게이트 + 3.4) |
| 5 | (잠금 실측) | Studio One 실행 중 `python spikes/lock_poc.py <파일>` |

## AC-1 ~ AC-7 판정

| AC | 내용 | 판정 | 근거 |
|---|---|---|---|
| AC-1 | naiite_14 채널·버스 구조 + 인서트 체인 순서 추출 | **통과** | 19/9/1/3/1 채널, 체인 순서=프리셋 순번 (pytest) |
| AC-2 | 라우팅 → 계층 그래프 (kick→K.BUS→DR.B→MIXOUT) | **통과** | topology 경로 테스트 + output 29/send 2 엣지 |
| AC-3 | GUI 계층 시각화 + 체인 순서 표시 | **통과** | 헤드리스 렌더 30노드/31엣지, 뱃지 확인 (스크린샷 spikes/out/) |
| AC-4 | 탭/스플릿 + 서브트리 DnD/복붙 전송 | **통과** | E2E: 스플릿→드래그 드롭→전송 완료 |
| AC-5 | .bak 백업 + 잠금 차단 + Studio One 정상 재생 | **조건부** | .bak/잠금/재검증 자동 통과. Studio One 개봉·재생은 수동 확인 대기 |
| AC-6 | 이름 충돌 확인 팝업 후 덮어쓰기 | **통과** | E2E: 충돌 모달→덮어쓰기→교체(채널 수 불변) |
| AC-7 | 파라미터 이름/값 표시 (Pro-Q 3, CLA-76 포함) + 해석불가 배지 | **통과** | 등급표: 해석가능 16/22 (Pro-Q 3·CLA-76 포함). E2E: 파라미터 테이블 11행 + JST Clip 배지 |

## 스토리 현황

- **완전 통과 (20)**: US-001, 004, 005, 007~013, 015~021, 023~025, 026
- **조건부 통과 — 수동 확인 대기 (6)**: US-002, 003, 006, 014, 022 (+ AC-5 축)
- **BLOCKED (0)**

## 주요 결정 (근거 문서)

- **런타임 A′ 확정**: PySide6+QWebEngineView+QWebChannel, pedalboard 인프로세스
  (플러그인 로드만 서브프로세스 격리) — 브리지 8ms 실측. → [verify/runtime-decision.md](verify/runtime-decision.md)
- **라운드트립 전략**: 무수정 entry 원시 블록 보존 → 116곡 전체 바이트 동일 재작성 검증.
- **파라미터 주입 레시피**: load_preset → raw_state 캡처 → 새 인스턴스 재주입 (FabFilter 컨트롤러 미동기화 우회).
- **플러그인 등급** → [verify/plugin-grade-table.md](verify/plugin-grade-table.md):
  해석가능 16 / 부분해석 1(mvMeter2) / 복사만 5 (JST Clip, JST GRD, AmpliTube 5, EQP-1A, De Esser).

## 알려진 이슈 / 한계

1. **WaveShell 16.6 스캔 실패** — EQP-1A·De Esser 해석 불가(복사는 가능). Waves Central에서
   v17로 업데이트하면 해석 가능해질 여지 (17.1 셸은 정상).
2. **전송 시 외부 send 제거** — 서브트리 밖을 가리키는 send(예: DR.B→DR Parallel)는 제거되고
   상태바에 기록됨. 필요하면 DR Parallel까지 서브트리에 포함해 드래그.
3. **버스 오토메이션(song.xml AutomationRegion)은 전송 안 됨** — Envelopes/ 폴더는 복사되지만
   song.xml 리전 생성은 2차 범위. 전송 후 버스 볼륨/팬 오토메이션은 대상에서 비활성.
4. **새 오디오 트랙 채널 생성 비범위** (계획 1.6 대로) — 버스/FX 채널 + 기존 채널 체인 교체만.
5. mvMeter2는 미터링 특성상 "부분 해석" (프리셋이 파라미터를 바꾸지 않음).
6. GUI의 Ctrl+C/V는 DnD와 동일 엔진 경로지만 E2E는 DnD 경로만 자동 검증함.

## 산출물 지도

```
engine/songcore/     파서·컨테이너·스캐너·전송 (tests 261 passed)
engine/introspect/   인벤토리·해석 서비스 (프로브 캐시 spikes/out/param_cache/)
app/main.py          PySide6 셸 (브리지+저장 파이프라인)
app/frontend/        React+React Flow (dist/ 빌드 완료)
spikes/              Phase 0 스파이크 7종 + 코퍼스 스캔
.omc/verify/         검증 파일 4종 + 분석 문서 5종
```

---

## 📌 갱신 (2026-07-12): 수동 게이트 정식 통과

사용자가 Studio Pro 8.1로 검증 파일 4종(01~04)을 확인 — **전부 통과**.
조건부(conditional)였던 스토리들(US-002/003/014/022 및 AC-5의 수용성 부분)은 **정식 통과**로 승격.
핵심 판정: mixerconsole/notepad 동반 기재는 선택적(미기재도 콘솔 재생성). 상세: MANUAL_CHECKLIST.md 상단 표.
잔여: S0.3 잠금 실측만 (문서화 목적).
