# song-mix-gui

Studio One .song 믹스 분석·시각화·병렬 전개 GUI. v1 완성(2026-07-12).
v2 계획: `.omc/plans/song-mix-gui-v2-consensus-plan.md` (컨센서스 완료, 실행 승인 대기).

## 새 세션 부트스트랩 (이 순서로 읽기 — 재탐색 금지)
1. `progress.txt` — 세션별 결정·학습 누적 (가장 중요)
2. `.omc/RUN_REPORT.md` — v1 완료 상태, 알려진 이슈
3. `.omc/specs/deep-interview-song-mix-gui-v2.md` — v2 요구사항 (있다면 `.omc/plans/`의 v2 계획도)
4. `.omc/MANUAL_CHECKLIST.md` — 사용자 수동 확인 대기 항목

## 구조
- `engine/songcore/` — .song(zip) 컨테이너·파서·라우팅 그래프·UID 스캐너·전송 엔진
- `engine/introspect/` — 플러그인 인벤토리 + vstpreset 파라미터 해석(서브프로세스 프로브+캐시+프리웜)
- `app/main.py` — PySide6 셸 + QWebChannel 브리지 + 저장 파이프라인 (실행: `python app/main.py`)
- `app/frontend/` — React Flow UI (빌드: `cd app/frontend && npm run build`)
- `spikes/` — Phase 0 검증 스파이크 (host_probe.py는 introspect가 런타임 재사용)

## 철칙 (변경 금지)
- 원본 .song 절대 수정 금지 — 실험은 사본. 쓰기는 .bak+잠금검사 경유(save_over)만.
- 무수정 zip entry는 원시 바이트 보존. XML 쓰기는 **텍스트 수술만** (DOM 재직렬화 금지 — `x:` 접두사 미선언, CRLF, 속성 줄바꿈 정렬 보존 필요).
- 전송 후 uid_refs.validate error = fail-closed (쓰기 거부).
- "Studio One이 파일을 수용한다"는 자동 검증 불가 — 수동 게이트를 통과한 척 금지, MANUAL_CHECKLIST에 기록.

## 검증 명령
- 엔진: `python -m pytest engine/tests -q` (262개, ~7s)
- GUI 셀프테스트: `QT_QPA_PLATFORM=offscreen python app/main.py --self-test`
- E2E: `QT_QPA_PLATFORM=offscreen python app/e2e_test.py`
- 콘솔 인코딩: 한글/이모지 출력 시 `PYTHONIOENCODING=utf-8` (cp949 크래시 방지)

## 핵심 도메인 지식 (재발견 비용 큼)
- .song = zip: `Devices/audiomixer.xml`(채널·라우팅·인서트), `Presets/Channels/<라벨>/N - <플러그인>.vstpreset`(체인 순서=파일명 순번), `Envelopes/<라벨>/`, 라벨이 폴더 키(UID 아님 — 라벨 충돌 별도 검사).
- UID 참조 형태: `{G}` braced + 대시 제거 HEX32(mixerconsole Section path). 카탈로그: `.omc/verify/uid-syntax-catalog.md`
- 파라미터 주입 레시피: `load_preset → raw_state 캡처 → 새 인스턴스에 raw_state 재주입` (FabFilter 컨트롤러 미동기화 우회)
- WaveShell 16.6 셸은 pedalboard 스캔 불가(EQP-1A·De Esser 복사만 가능). 15.5/16.7/17.1 정상.
- 테스트 코퍼스: `C:\Users\yhkze\Documents\Studio Pro\Songs` 116곡(고유 29+History 87). 샘플: naiite_14.song
