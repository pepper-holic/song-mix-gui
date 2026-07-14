# Studio Pro 8.1 수동 확인 체크리스트

## ✅ 판정 완료 (2026-07-12, 사용자 확인)

| 파일 | 판정 | 비고 |
|---|---|---|
| 01-rename-bus | **통과** | 정상 개봉·표시·재생 |
| 02-duplicate-channel-full | **통과** | COPY 표시됨. 입력 없음은 설계대로(재배선 안 함) |
| 03-duplicate-channel-mixeronly | **통과 + 판정 획득** | 동반 파일 없이도 COPY 표시 → **mixerconsole/notepad는 선택적**(콘솔 재생성됨). 엔진은 안전 기본값으로 계속 기재 |
| 04-engine-drum-transfer | **통과** | 버스 5개+세팅 이식 확인. 미디어 미로딩은 검증 파일이 원곡 폴더 밖이라 상대경로 끊김(전송 결함 아님). 이식 버스에 입력 없음은 설계(트랙 전송은 v2 범위) |

→ **S0.1(b) / S0.1(b-2) / Phase 1 게이트 / Phase 3.4 전부 정식 통과. 쓰기 경로의 Studio One 수용성 확정.**
→ 남은 항목: S0.3 잠금 실측(아래, 문서화 목적 — 기능 영향 없음)
→ 교훈: 전송 검증 파일은 **대상 곡 폴더 안에 사본으로 두고 열어야** 미디어가 로딩됨 (v2 스파이크부터 적용)

---

# (이하 원 절차 기록 — 보관용)


무인 실행 중 자동화 불가능한 "Studio One 수용" 게이트들입니다.
각 파일을 Studio Pro 8.1로 열어 아래 절차대로 확인해 주세요.
**주의: 확인 시 원본 프로젝트가 아닌 아래 검증 파일을 여세요. 저장하지 말고 열람만.**

## S0.1(b) 최소 변형 쓰기 — 게이트: 쓰기 기능 전체의 전제

### 1. `.omc/verify/01-rename-bus.song`
- 변경 내용: 버스 `K.BUS`의 라벨만 `K.BUS RT`로 변경 (그 외 바이트 동일)
- 확인 절차:
  1. Studio Pro 8.1에서 파일 열기 — 오류/복구 대화상자 없이 열리는가?
  2. 믹서 콘솔에서 해당 버스가 `K.BUS RT`로 표시되는가?
  3. kick, kick out 채널의 출력이 여전히 이 버스로 라우팅되어 있는가?
  4. 재생 시 사운드가 원본과 동일한가? (K.BUS 인서트 체인: Pro-Q 3 → SPL Transient Designer → CLA-76 → JST Clip 동작 확인)
- 판정: [ ] 통과 / [ ] 실패 (실패 시 증상 메모: ____________)

### 2. `.omc/verify/02-duplicate-channel-full.song`
- 변경 내용: `CYM.BUS` 버스를 복제해 `CYM.BUS COPY` 생성 (새 UID, DR.B로 라우팅,
  Pro-Q 3 인서트+프리셋 복사, mixerconsole.xml/notepad.xml 동반 기재 포함)
- 확인 절차:
  1. 파일이 정상으로 열리는가?
  2. 믹서에 `CYM.BUS COPY` 채널이 보이는가? (콘솔 마지막 순서)
  3. `CYM.BUS COPY`의 출력이 DR.B인가? 인서트에 Pro-Q 3가 있고 설정값이 CYM.BUS와 동일한가?
  4. 재생 정상? (COPY 버스에 입력이 없으므로 소리 변화는 없어야 함)
- 판정: [ ] 통과 / [ ] 실패 (증상: ____________)

### 3. `.omc/verify/03-duplicate-channel-mixeronly.song` — S0.1(b-2) 동반 파일 필수성 실험
- 변경 내용: 2와 동일한 복제이지만 **audiomixer.xml에만 기록** (mixerconsole/notepad 미기재)
- 목적: Studio One이 동반 entry 없이도 채널을 수용하는지(콘솔 레이아웃 재생성 여부) 판정
- 확인 절차:
  1. 파일이 정상으로 열리는가?
  2. `CYM.BUS COPY`가 믹서에 표시되는가? (표시된다면 동반 파일은 선택적)
  3. 표시 이상(채널 숨김, 순서 꼬임, 오류 메시지)이 있는가?
- 판정: [ ] 2번과 동일하게 정상 (동반 파일 선택적) / [ ] 이상 있음 (동반 파일 필수 — 증상: ____________)

> 판정 결과는 다음 세션에서 알려주세요. 3번 결과에 따라 transfer 엔진의 동반 파일 정책(필수/선택)을 확정합니다.
> 자동화된 사전 검증(이미 통과): 무수정 entry 바이트 보존, XML 파싱 유효성, UID 전역 유일성, zip CRC 무결성, 원본 불변.

## Phase 1 게이트 + Phase 3.4 전송 결과물 (US-014, US-022)

### 4. `.omc/verify/04-engine-drum-transfer.song`
- 변경 내용: naiite_14의 드럼 버스 서브트리(K.BUS+S.BUS+T.BUS+CYM.BUS→DR.B, 인서트 체인
  및 vstpreset 15개 파일 포함)를 `sp_hwa_14 (fixed).song` 사본에 **transfer 엔진으로** 전송.
  DR.B의 출력은 대상에 MIXOUT이 없어 "메인"으로 접합. DR.B의 DR Parallel 센드는 제거됨(기록 있음).
- 자동 검증(통과): 재파싱 그래프 동등성(DR.B 자식 4버스), dangling 참조 0, UID 전역 유일,
  zip CRC, 콘솔/notepad 동반 기재.
- 확인 절차:
  1. 파일이 정상으로 열리는가?
  2. 믹서에 K.BUS/S.BUS/T.BUS/CYM.BUS/DR.B가 추가되어 있고 DR.B 출력이 "메인"인가?
  3. K.BUS 인서트가 Pro-Q 3 → SPL Transient Designer → CLA-76 → JST Clip 순서로 로드되고
     설정값이 naiite_14와 동일한가? (Pro-Q 3를 열어 EQ 커브 비교)
  4. 기존 채널들(K, SN, TOM 등)의 라우팅과 사운드가 그대로인가? 재생 정상?
- 판정: [ ] 통과 / [ ] 실패 (증상: ____________)

## S0.3 잠금 감지 실측 — Studio One 실행 중 상태 (US-006)

자동 자체검증은 통과했습니다(파일 핸들 보유 시 sharing violation 검출 확인).
Studio One이 .song을 열었을 때 실제로 OS 핸들을 유지하는지만 실측이 필요합니다.

- 절차:
  1. Studio Pro 8.1로 아무 .song 하나(사본 권장)를 연다.
  2. 터미널에서 실행: `python spikes/lock_poc.py "<그 파일 경로>"`
  3. 출력이 `write BLOCKED — sharing violation`이면: Studio One이 핸들 유지 → 핸들 검사만으로 충분.
  4. `BLOCKED — Studio One 프로세스 실행 중`(핸들은 없음)이면: 프로세스 휴리스틱이 실제 방어선 → 현 구현이 이미 보수적으로 차단하므로 그대로 유효.
- 판정: [ ] 핸들 유지함 / [ ] 핸들 없음(프로세스 휴리스틱 의존)
> 어느 쪽이든 현 구현(핸들 검사 + Studio One 프로세스 실행 시 무조건 차단)은 안전 측이며 코드 변경 불필요. 실측은 문서화 목적.

---

# Phase 0-S 스파이크 게이트 (v2 — song.xml 신규 쓰기 축) ✅ 판정 완료 (2026-07-13, 사용자 확인)

## ✅ 판정 완료 (2026-07-13, 사용자 확인)

| 파일 | 판정 | 비고 |
|---|---|---|
| 05-automation-transfer | **통과** | `DR BUS vol` 레인 정상 표시, 기존 트랙 재생/사운드 문제없음 |
| 06-track-transfer-empty | **통과 + 핵심 판정 획득** | `NEW TRK` 정상 표시(빈 트랙, 설계대로). **Show/런처 화면에서 트랙 열 정상 표시(셀 누락·오류 없음)** → **LauncherCell 미기재로 충분함이 확정** (Open Question 4 해소) |
| 07-track-transfer-events | **통과** | `NEW TRK EV`에 킥 클립 이벤트 표시 + 파형 재생 정상(곡 폴더 안에서 재개봉 후 재링크 성공) |

→ **v2 최대 기술 리스크(song.xml 신규 쓰기 축 2종: AutomationTrack/MediaTrack) Studio One 수용성 전부 확정.**
→ Open Question 1(오토메이션 삽입 순서 무관), 2(빈 MediaTrack은 Events 리스트 자체가 없어도 정상), 4(LauncherCell 미기재 허용) 전부 해소.
→ 교훈 재확인: `.omc/verify/`에서 직접 열면(인접 Media 폴더 없음) 미디어 재링크 실패 — 반드시 대상 곡 폴더 안 사본으로 열어야 함.

---


v2 최대 기술 리스크: song.xml에 **처음 쓰는 두 축**(AutomationTrack, MediaTrack)을 Studio One이
수용하는지. v1 01~04와 동일하게 **최소 변형 수동 이식 파일**을 먼저 만들어 게이트한다.
빌드/자동검증 스크립트: `spikes/spike_v2_tracks.py` (원본 불변, 무수정 entry 바이트 보존,
zip CRC, song.xml/audiomixer/mediapool XML 재파싱 유효성 전부 자동 PASS).

- 소스: `NAIITE_EP/naiite_14/naiite_14.song` (오토메이션 원본)
- 대상: `NAIITE_HWA_SPLIT/sp_hwa_14/sp_hwa_14 (fixed).song` 사본 (v1 04-spike와 동일 대상)
- 백업본은 `.omc/verify/05~07`에 보관.

> **⚠ 개봉 위치 (v1 교훈 필수 적용)**: 05~07은 반드시 **대상 곡 폴더
> `...\Songs\NAIITE_HWA_SPLIT\sp_hwa_14\` 안에 사본으로 복사한 뒤** 그 위치에서 여세요.
> `.omc/verify/`에서 직접 열면 인접 `Media/` 폴더가 없어 07의 오디오가 재링크되지 않습니다.
> (원본 코퍼스는 건드리지 말 것 — 사본만 배치. 확인 후 저장하지 말고 열람만.)

### 5. `.omc/verify/05-automation-transfer.song` — S3a 버스 오토메이션 전송
- 변경 내용: naiite_14의 `S.BUS` 볼륨 오토메이션 `AutomationTrack`(1개 `AutomationRegion`,
  identity=`param:///AudioMixer/{S.BUS UID}/volume`)을 대상의 `<List x:id="Tracks">` 말미에 삽입.
  identity의 채널 UID를 대상의 **`DR BUS`** 그룹 채널 UID로 재매핑(metaIdentity=`AudioGroupChannel/volume` 유지),
  trackID는 새 GUID로 재생성, 참조 엔벨로프 `Envelopes/S.BUS/볼륨.envelopex`를 대상 zip에 원시 복사.
  (AutomationTrack에는 trackNumber 속성이 없음 — 실측 확인, 부여 불필요. AutomationRegion `mute="1"`은
   원본 그대로 보존 — 오토메이션 레인은 존재하나 바이패스 상태. 청감 확인 시 수동 unmute.)
- 확인 절차:
  1. 파일이 오류/복구 대화상자 없이 열리는가?
  2. 오토메이션(편집) 화면에 `DR BUS vol (spike)` 레인이 보이고, 그 대상이 **DR BUS 채널의 볼륨**으로 바인딩되어 있는가?
  3. 기존 트랙/채널/라우팅과 사운드가 그대로인가? (오토메이션은 mute 상태이므로 재생음 변화 없어야 정상)
  4. (선택) 레인을 unmute 시 DR BUS 볼륨이 곡선대로 움직이는가?
- 판정: [x] 통과 / [ ] 실패 — `DR BUS vol` 레인 정상 표시, 기존 트랙 재생/사운드 문제없음
> 관찰: 버스 AutomationTrack은 LauncherCell 참조가 없어(트랙 launcher 비대상) 06/07 대비 위험이 낮음. 실측으로도 확인됨.

### 6. `.omc/verify/06-track-transfer-empty.song` — S4a 빈 트랙 전송
- 변경 내용: 대상에 **빈 MediaTrack 1개**(`name="NEW TRK"`, 새 trackID, trackNumber=17=말번+1,
  `channelID`=신규 `AudioTrackChannel` UID, **Events List 없음**) 추가. 신규 AudioTrackChannel은
  기존 `1 - TOM F` 채널(인서트 프리셋 없음)을 템플릿으로 uniqueID/Combinator/Panner UID 전부 재생성,
  라우팅은 `TOM` 그룹 유지. 기본 볼륨/팬 오토메이션 레인의 엔벨로프 파일을 `Envelopes/NEW TRK/`로 복사.
  동반 기재: `mixerconsole.xml` Section+ScreenBank, `notepad.xml` 항목 (v1 02-spike 방식).
- **핵심 관찰 항목 — LauncherCell 비대칭 (v2 계획 Open Question 4)**:
  이 파일은 신규 트랙에 대응하는 **`LauncherCell` 엔트리를 일부러 넣지 않았다**
  (기존 128개 cell = 16트랙×8씬 그대로, 신규 trackID 참조 cell 0개). 신규 MediaTrack이
  **launcher cell 없이도 정상 개봉/표시되는지**가 이 스파이크의 최대 판정 목표.
- 확인 절차:
  1. 파일이 오류/복구 대화상자 없이 열리는가?
  2. 어레인지먼트/믹서에 `NEW TRK` 트랙·채널이 보이는가? (트랙 순서 마지막, 콘솔 마지막)
  3. **[LauncherCell 확인]** 런치어(씬 런처) 뷰를 열었을 때 `NEW TRK` 트랙 열이 정상인가,
     아니면 셀 누락/오류/트랙 숨김/순서 꼬임이 발생하는가?
     → 정상이면 **엔진은 LauncherCell 미기재 가능**(빈 트랙 최소 기재). 이상이면 엔진이 씬별 cell 동반 기재 필요.
  4. 기존 트랙들의 라우팅·사운드·재생이 그대로인가?
- 판정: [x] 통과 (LauncherCell 없이 정상) / [ ] 통과하나 launcher 이상 (cell 동반 필요) / [ ] 실패 — `NEW TRK` 정상 표시(빈 트랙), Show/런처 화면에서 트랙 열 정상(셀 누락·오류 없음) → **엔진은 LauncherCell 미기재로 충분**(v2 계획 Open Question 4 확정)

### 7. `.omc/verify/07-track-transfer-events.song` — S4c 이벤트 포함 트랙 전송
- 변경 내용: 6과 동일 구조(`name="NEW TRK EV"`)에 **`<List x:id="Events">` 1개 `AudioEvent` 추가**.
  이벤트의 `clipID`는 **대상 곡에 이미 존재하는 클립**(`14 - kick`, mediaID `{A5FF94B4-…}`)을 재사용
  (새 미디어 경로 발명 없음). `mediapool.xml`의 해당 클립 `useCount` 1→2 갱신. LauncherCell은 6과 동일하게 미기재.
- **⚠ 미디어 경로 경고 (v2 계획 "url 절대경로/타 폴더 경고" 요건에 직결)**:
  재사용한 클립의 `Url`은 **절대경로**이며 **현재 곡 폴더와 불일치**한다 —
  `file:///C:/Users/yhkze/Documents/Studio Pro/Songs/sp_hwa_14/Media/14 - kick.wav`
  (실제 곡 위치는 `.../Songs/NAIITE_HWA_SPLIT/sp_hwa_14/`). 이 스테일 절대경로는 **대상 곡의 모든 기존
  트랙이 공유**하는 것으로, 이 파일 자체 결함이 아니라 곡이 이동된 흔적. Studio One은 개봉 시 인접
  `Media/` 폴더에서 재링크하는 것으로 추정 → **반드시 곡 폴더 안(인접 `Media/` 있음)에서 열 것**.
  (엔진 시사점: 이벤트 포함 전송 시 clip `Url`이 절대경로/타 폴더면 전송 전 경고 다이얼로그 필요 — 파일 복사는 비범위.)
- 확인 절차:
  1. 파일이 오류/복구 대화상자 없이 열리는가?
  2. `NEW TRK EV` 트랙에 오디오 이벤트(클립 `14 - kick`)가 어레인지에 **보이는가**?
  3. **[미디어 재생]** 해당 이벤트가 재링크되어 실제로 **재생/파형 표시**되는가?
     (재링크 실패 시 미싱 미디어 표시 → 절대경로 경고 요건의 근거로 기록)
  4. mediapool 정합(useCount 반영) 및 기존 트랙 재생이 그대로인가?
- 판정: [x] 통과(이벤트 보임+재생) / [ ] 트랙은 열리나 미디어 미링크 / [ ] 실패 — `NEW TRK EV`에 킥 클립 이벤트 표시, 파형 재생 정상(곡 폴더 안에서 재개봉 후 재링크 성공). 최초 `.omc/verify/`에서 직접 열었을 때는 "누락된 파일 탐색" 대화상자(14개 파일)가 떴으나, 이는 예상된 현상(인접 Media 폴더 없음)이었고 곡 폴더 안 사본으로 재개봉 후 정상 재링크됨 — 실측으로 재확인.

> 세 파일 모두 자동 사전검증 통과(원본 불변·무수정 entry 바이트 동일·zip CRC·XML 재파싱 유효·trackID/채널 UID 전역 유일·참조 무-dangling) + Studio One 수동 게이트 전부 통과.

## S3b/S4b/S4d 본구현 완료 + Studio One 수동 게이트 전부 통과 (2026-07-13)

엔진 본구현(스파이크 산출물 보존 + fail-closed 검증)과 Studio One 수동 게이트 05/06/07 전부 통과 완료.
v2 최대 기술 리스크(song.xml 신규 쓰기 축: AutomationTrack, MediaTrack)의 Studio One 수용성이 실측으로 확정됐다.

- **S3b(버스 오토메이션 전송)**: `transfer_subtree`가 전송된 채널의 `AutomationTrack`을 자동으로 song.xml에 동반 전송.
  `uid_refs.validate()` fail-closed 확장 3종(오토메이션 identity dangling / 트랙 channelID 실재 / trackID·trackNumber 유일성) 추가.
  116곡 코퍼스 회귀에서 실제 예외 2건 발견·반영(악기 트랙 mediaType 구분, naiite_20 스테일 오토메이션 비대칭 처리) — pytest 전부 통과.
- **S4b/S4d(트랙 채널 전송)**: `transfer_track()` 신설 — 기본은 빈 트랙(Events 제외), `include_events=True`로 이벤트+mediapool 클립 이식(경로가 대상 폴더 밖이면 경고 기록, 07 스파이크와 동일 현상 재현 확인). RecordUnit(입력 라우팅)은 소스 전용이라 전송 안 함(빈 채널, v1 COPY 설계 원칙과 동일). pytest 8종 통과.
- **다이얼로그 UI(트랙 채널 선택/이벤트 포함 체크박스)**: 이후 세션에서 완성(브리지 슬롯 신설 + 프론트 배선, E2E로 실제 채널 생성 확인).
- **05/06/07 전부 통과**로 최대 리스크 해소 — 위 엔진 구현 중 관련 축(자동화/트랙 전송)의 재검토는 불필요.

## S0.3 잠금 실측 (v1 잔여, 문서화 목적)

미확인 상태로 남음 — 기능에는 영향 없음(현 구현이 이미 보수적으로 안전측 차단).
