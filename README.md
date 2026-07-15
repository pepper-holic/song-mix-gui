# song-mix-gui

Studio One `.song` 믹스 분석 · 시각화 · 병렬 전개 GUI.

한 곡에서 완성한 채널별 플러그인 체인과 버스/병렬 라우팅 구조를, 라벨이 일치하는
다른 `.song` 파일들에 안전하게 옮겨 붙일 수 있게 해주는 데스크톱 도구입니다.
Studio One 프로젝트 파일(zip 컨테이너 + XML)을 직접 읽고 텍스트 수술로만 써서,
원본 파일 포맷을 훼손하지 않습니다.

v1 완성. v2 계획은 `.omc/plans/song-mix-gui-v2-consensus-plan.md` 참고.

## 주요 기능

- **믹스 그래프 시각화**: 채널 라우팅(트랙 → 버스 → 아웃풋)을 React Flow 그래프로 표시
- **인서트 체인 인스펙션**: 채널별 플러그인 체인 + vstpreset 파라미터 해석(서브프로세스 프로브 + 캐시)
- **버스/체인/트랙 전송**: 드래그앤드롭 또는 우클릭 메뉴로 버스 서브트리, 인서트 체인, 단일 트랙을 다른 곡으로 전송
- **채널 비교**: 두 채널의 인서트 체인 값 차이를 나란히 비교
- **일괄 레시피 적용**: 한 곡의 믹스 레시피(트랙 체인 + 버스 구조)를 폴더 하위 여러 곡에 라벨 매칭 기준으로 한 번에 적용
  - 폴더 스캔으로 대상 곡 후보를 찾고, 파일별 트랙/버스 현황을 미리 확인 후 선택
  - Studio One의 `History/` 자동저장·스냅샷 폴더는 자동 제외(원본만 노출)
  - 버스 트리를 depth와 함께 보여주고, 상위 버스를 선택하면 하위는 자동으로 "포함됨" 처리(서브트리 통째 전송이므로 개별 제외 불가)
  - fail-closed: 위험한 상황(라벨 중복, 조상/자손 동시 지정, 제외 라벨이 서브트리 내부에 중첩)은 조용히 넘어가지 않고 명시적으로 거부
- **Undo**: 전송/적용 작업을 되돌릴 수 있는 자체 Undo 스택

## 철칙 (변경 금지)

- 원본 `.song` 파일은 절대 직접 수정하지 않습니다 — 쓰기는 항상 `.bak` 백업 생성 + 잠금 검사를 거치는 `save_over` 경유로만 이뤄집니다.
- 손대지 않는 zip entry는 원시 바이트를 그대로 보존합니다. XML을 쓸 때도 DOM을 다시 직렬화하지 않고 **텍스트 수술만** 합니다(Studio One XML의 미선언 `x:` 네임스페이스 접두사, CRLF, 속성 줄바꿈 정렬을 그대로 보존하기 위함).
- 전송 후 UID 참조 무결성 검증(`uid_refs.validate`)에 실패하면 fail-closed로 쓰기를 거부합니다.
- 이 도구가 "Studio One이 결과 파일을 정상적으로 인식한다"는 것을 자동으로 검증할 수는 없습니다. 실제 애플리케이션 검증은 항상 수동으로 확인하세요.

## 구조

```
engine/songcore/    .song(zip) 컨테이너 · 파서 · 라우팅 그래프 · UID 스캐너 · 전송 엔진
engine/introspect/  플러그인 인벤토리 + vstpreset 파라미터 해석(프로브 + 캐시 + 프리웜)
app/main.py          PySide6 셸 + QWebChannel 브리지 + 저장 파이프라인
app/frontend/         React Flow 기반 UI (Vite + TypeScript)
spikes/               Phase 0 검증 스파이크 스크립트
```

## 실행

### 요구 사항

- Python 3.11+, PySide6 (`pip install PySide6`)
- Node.js 18+ (프론트엔드 빌드용)

### 프론트엔드 빌드

```bash
cd app/frontend
npm install
npm run build
```

### GUI 실행

```bash
python app/main.py
```

## 테스트

```bash
# 엔진 유닛/통합 테스트 (pytest)
python -m pytest engine/tests -q

# GUI 헤드리스 셀프테스트
QT_QPA_PLATFORM=offscreen python app/main.py --self-test

# 헤드리스 E2E 시나리오
QT_QPA_PLATFORM=offscreen python app/e2e_test.py
```

콘솔에 한글/이모지를 출력할 때는 `PYTHONIOENCODING=utf-8`을 함께 지정하세요(Windows `cp949` 인코딩 크래시 방지).

## 배포용 실행파일 빌드 (PyInstaller)

```bash
pip install pyinstaller
cd app/frontend && npm run build && cd ../..
python -m PyInstaller packaging/song-mix-gui.spec --distpath dist --workpath build --noconfirm
```

결과물: `dist/song-mix-gui/`(onedir — `song-mix-gui.exe` + 동봉 DLL/리소스 폴더 전체를 그대로 배포).
onefile이 아니라 onedir을 쓰는 이유와 얼린 빌드 전용 처리(호스트 프로브 서브프로세스 재호출,
파라미터 캐시 영속 위치)는 `packaging/song-mix-gui.spec` 및 `engine/introspect/runtime.py` 주석 참고.
첫 실행은 Windows Defender 등이 새 실행파일을 스캔하느라 수십 초 걸릴 수 있음(이후 실행은 빠름).

## 핵심 도메인 지식

- `.song` 파일은 zip 컨테이너입니다: `Devices/audiomixer.xml`(채널·라우팅·인서트), `Presets/Channels/<라벨>/N - <플러그인>.vstpreset`(파일명 순번이 체인 순서), `Envelopes/<라벨>/`. 채널 라벨이 폴더 키로 쓰이며 UID가 아니므로 라벨 충돌은 별도로 검사합니다.
- UID 참조는 `{G}` 형태의 중괄호 + 대시 제거 32자리 HEX로 등장합니다.
- 서로 다른 곡 간 라벨 표기가 다를 수 있어(예: `"kick"` vs `"1 - kick"`) 일괄 적용은 자동 유사매칭을 하지 않고 정확한 라벨 일치만 인정하며, 불일치는 "매칭 안 됨"으로 사용자에게 명시적으로 보고합니다.

## 라이선스

미정(개인 프로젝트).
