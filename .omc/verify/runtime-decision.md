# 런타임 구조 결정 (Phase 0 게이트, US-007)

## 결정: **Option A′ — PySide6 + QWebEngineView(React Flow 호스팅) + pedalboard 인프로세스**

## 실측 근거 (2026-07-11)

| 항목 | A′ (PySide6+QWebChannel) | A (Electron+Python 사이드카) |
|---|---|---|
| 브리지 실험 | **성공** — spikes/qwebchannel_poc.py: naiite_14 파싱 결과(채널 33, 엣지 31)가 JS↔Python 왕복 **8ms**, 앱 부팅 0.49s (offscreen) | 미실험 (아래 사유로 불필요 판정) |
| 엔진 결합 | pedalboard/songcore가 **같은 프로세스** — IPC 없음 | stdio JSON-RPC 계층 + 프로세스 수명 관리 필요 |
| 설치 실측 | `pip install PySide6` 1회로 완료 (Python 3.14 wheel 정상) | Node 24는 있으나 electron 바이너리(~100MB) + 듀얼 런타임 배포 |
| 배포 | 단일 PyInstaller 아티팩트 | Electron 패키징 + Python 임베드 이중화 |
| 프론트 | React Flow 번들을 QWebEngineView가 로드 (계획서 전제 유지) | 동일 |

## 판정 논리
계획서 ADR대로 상위 2개 결정 동인(라운드트립·호스팅)은 두 안에서 동일한 Python 코드다.
차별 요소는 통합 표면뿐인데, QWebChannel 브리지가 실데이터로 즉시 동작했고 지연(8ms)이
UI 요구(그래프 렌더/드래그앤드롭)에 충분하므로, 프로세스 경계를 추가할 이유가 소멸했다.
pedalboard(해석 서비스)가 GUI 프로세스 안에서 직접 호출 가능한 것도 A′의 결정적 이점.

## 리스크 메모
- 플러그인 로드(pedalboard)는 크래시/행업 가능 → GUI 프로세스 보호를 위해
  Phase 4 해석 서비스는 **서브프로세스 프로브**(S0.2에서 검증한 host_probe 패턴)로 실행한다.
  (인프로세스 결정과 모순 아님 — 브리지·파서는 인프로세스, 위험한 플러그인 로드만 격리)
- QtWebEngine 임베드 용량은 Electron과 대동소이 (양안 공통 비용).
