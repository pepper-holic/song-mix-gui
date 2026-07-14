# 플러그인 해석 등급표 (S0.2)

| 플러그인 | 등급 | 상세 |
|---|---|---|
| Waves CLA-76 | **해석 가능** | 파라미터 142개(가독 142), 주입 후 5개 변경 |
| Soundtoys Decapitator | **해석 가능** | 파라미터 12개(가독 12), 주입 후 3개 변경 |
| Waves SSLComp | **해석 가능** | 파라미터 142개(가독 141), 주입 후 5개 변경 |
| Waves Maag EQ2 | **해석 가능** | 파라미터 10개(가독 10), 주입 후 5개 변경 |
| FabFilter Pro-Q 3 | **해석 가능** | 파라미터 387개(가독 387), 주입 후 7개 변경 |
| JST Clip | **복사만 가능** | ImportError: Failed to load plugin as VST3Plugin. Errors were:
	VST3Plugin: Unable to scan plugin C:\Program Files\Common Files\VST3\JST Clip.vst3: unsupported plugin format or scan failure. |
| SPL Transient Designer Plus | **해석 가능** | 파라미터 13개(가독 13), 주입 후 4개 변경 |
| JST Gain Reduction Deluxe | **복사만 가능** | ImportError: Failed to load plugin as VST3Plugin. Errors were:
	VST3Plugin: Unable to scan plugin C:\Program Files\Common Files\VST3\Gain Reduction Deluxe.vst3: unsupported plugin format or scan failure. |
| mvMeter2 | **부분 해석** | 로드/이름 OK(29/29), 프리셋 주입이 파라미터에 미반영 |
| Waves L4 Ultramaximizer | **해석 가능** | 파라미터 137개(가독 137), 주입 후 4개 변경 |
| SPL Attacker Plus | **해석 가능** | 파라미터 7개(가독 7), 주입 후 2개 변경 |
| Soundtoys Little Plate | **해석 가능** | 파라미터 5개(가독 5), 주입 후 3개 변경 |
| Soundtoys Little MicroShift | **해석 가능** | 파라미터 4개(가독 4), 주입 후 2개 변경 |
| Waves Scheps Omni Channel 2 | **해석 가능** | 파라미터 1946개(가독 1942), 주입 후 18개 변경 |
| IK AmpliTube 5 | **복사만 가능** | ImportError: Failed to load plugin as VST3Plugin. Errors were:
	VST3Plugin: Unable to scan plugin C:\Program Files\Common Files\VST3\AmpliTube 5.vst3: unsupported plugin format or scan failure. |
| Waves EQP-1A | **복사만 가능** | 바이너리 미발견(스캔 실패 shell 소속 가능) |
| Slate Trigger 2 | **해석 가능** | 파라미터 126개(가독 126), 주입 후 8개 변경 |
| Soundtoys Devil-Loc | **해석 가능** | 파라미터 3개(가독 3), 주입 후 2개 변경 |
| FabFilter Pro-Q (Pro-Q(v1) 미설치 — Pro-Q 3 바이너리로 주입 시도) | **해석 가능** | 파라미터 387개(가독 387), 주입 후 10개 변경 |
| Magma StressBox | **해석 가능** | 파라미터 135개(가독 135), 주입 후 3개 변경 |
| Waves De Esser | **복사만 가능** | 바이너리 미발견(스캔 실패 shell 소속 가능) |
| FabFilter Pro-R | **해석 가능** | 파라미터 141개(가독 141), 주입 후 35개 변경 |

- 합계: {'해석 가능': 16, '복사만 가능': 5, '부분 해석': 1}
- 엔진: pedalboard 0.9.23 (Python 3.14) — WaveShell 로드 지원 실측됨
- 주입 레시피: load_preset → raw_state 캡처 → 새 인스턴스 raw_state 재주입 → 컨트롤러 동기화
- 상세 값 샘플: spikes/out/host_poc_results.json

## 각주 (폴백 시도 기록)
- **Waves EQP-1A / De Esser**: WaveShell1-VST3 16.6 소속으로 추정되나 해당 셸이 pedalboard 스캔 실패
  (셸 자체 스캔 + `--name` 직접 로드 2회 모두 실패). → **복사만 가능** 확정.
  참고: 17.1 셸은 정상 동작하므로 Waves Central에서 해당 플러그인을 v17로 업데이트하면 해석 가능해질 여지 있음.
- **JST Clip / JST Gain Reduction Deluxe / IK AmpliTube 5**: 단독 VST3이 pedalboard 스캔 실패(보호/포맷 문제 추정).
  → 복사만 가능. 바이너리 전송에는 영향 없음(vstpreset 원본 복사 경로는 플러그인 로드 불필요).
- **mvMeter2**: 미터링 플러그인 — 프리셋 주입이 파라미터를 바꾸지 않는 것은 정상 동작에 가까움(표시용 상태 위주). 부분 해석 유지.
- **FabFilter Pro-Q(v1)/Pro-R(v1)**: v1 프리셋을 Pro-Q 3/Pro-R 2 바이너리에 주입 성공(각 10/35개 파라미터 변경) — v1 미설치 환경에서 후속 버전 해석으로 대체.
