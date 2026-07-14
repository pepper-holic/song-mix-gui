"""헤드리스 E2E — GUI 전체 플로우 검증 (US-016~021, US-025).

시나리오:
  1. naiite_14 열기 → 그래프 30노드
  2. K.BUS 노드 클릭 → 상세 패널 + 인서트 4개
  3. 인서트(Pro-Q 3) 클릭 → 파라미터 테이블 (캐시 경유, 해석 가능)
  4. 좌우 스플릿 + 두 번째 song(임시 사본) 열기
  5. K.BUS 드래그앤드롭 시뮬레이션 → 전송 → 상태바 완료 + .bak 생성
  6. 같은 전송 재시도 → 충돌 다이얼로그 → 덮어쓰기 → 완료
  7. 대상 재파싱: K.BUS 존재 + 그래프 갱신

실행: QT_QPA_PLATFORM=offscreen python app/e2e_test.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Windows 기본 콘솔(cp949)에서 상태 문자열(—, 한글) print 크래시 방지
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

from app.main import DIST_INDEX, Bridge

NAIITE = "C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song"
DST_SRC = Path("C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_HWA_SPLIT/sp_hwa_14/sp_hwa_14 (fixed).song")

tmpdir = Path(tempfile.mkdtemp(prefix="e2e_song_"))
DST = tmpdir / "e2e_target.song"
shutil.copy2(DST_SRC, DST)
DST_JS = str(DST).replace("\\", "/")

STEPS: list[tuple[str, str]] = [
    ("open naiite", f"window.__openSong('{NAIITE}').then(() => 'ok')"),
    ("graph nodes", """(() => JSON.stringify({
        nodes: document.querySelectorAll('.react-flow__node').length}))()"""),
    ("click K.BUS node", """(() => {
        const nodes = [...document.querySelectorAll('.channel-node')];
        const kbus = nodes.find(n => n.textContent.includes('K.BUS') && !n.textContent.includes('RT'));
        kbus.dispatchEvent(new MouseEvent('click', {bubbles: true}));
        return 'clicked';
    })()"""),
    ("detail panel", """(() => JSON.stringify({
        panel: !!document.querySelector('.detail-panel'),
        inserts: document.querySelectorAll('.insert-item').length,
        title: document.querySelector('.detail-panel h2')?.textContent}))()"""),
    ("click insert 1 (Pro-Q 3)", """(() => {
        document.querySelectorAll('.insert-item')[0].click();
        return 'clicked';
    })()"""),
    ("wait params", """(() => JSON.stringify({
        rows: document.querySelectorAll('.param-table tbody tr').length,
        badge: !!document.querySelector('.badge-uninterpretable'),
        loading: !!document.querySelector('.param-loading')}))()"""),
    ("click insert 4 (JST Clip)", """(() => {
        document.querySelectorAll('.insert-item')[3].click();
        return 'clicked';
    })()"""),
    ("wait tick 1", "'tick'"),
    ("wait tick 2", "'tick'"),
    ("wait tick 3", "'tick'"),
    ("wait badge", """(() => JSON.stringify({
        badge: !!document.querySelector('.badge-uninterpretable'),
        loading: !!document.querySelector('.param-loading')}))()"""),
    # ---- 검색/필터 (U2, AC-2): "CLA-76" 검색 → 실제 사용 채널 수만큼 하이라이트 ----
    ("search CLA-76", """(() => {
        const input = document.querySelector('[data-pane="left"] .search-input');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, 'CLA-76');
        input.dispatchEvent(new Event('input', {bubbles: true}));
        return 'searched';
    })()"""),
    ("wait search tick", "'tick'"),
    ("search result", """(() => JSON.stringify({
        matches: document.querySelectorAll('[data-pane="left"] .react-flow__node.search-match').length}))()"""),
    ("clear search", """(() => {
        const input = document.querySelector('[data-pane="left"] .search-input');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, '');
        input.dispatchEvent(new Event('input', {bubbles: true}));
        return 'cleared';
    })()"""),
    # ---- 체인 비교 (U4, AC-4): K.BUS를 A로 지정(Shift+우클릭) 후 S.BUS와 비교(Alt+우클릭) ----
    # 둘 다 Pro-Q 3(FX01)를 쓰지만 프리셋이 다르므로 캐시 워밍 후 value-diff 행이 기대됨.
    ("shift-rightclick K.BUS (set baseline)", """(() => {
        const src = [...document.querySelectorAll('[data-pane="left"] .channel-node')]
          .find(n => n.textContent.includes('K.BUS') && !n.textContent.includes('RT'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, shiftKey: true}));
        return 'baseline-set';
    })()"""),
    ("baseline status", "document.querySelector('.statusbar')?.textContent"),
    ("alt-rightclick S.BUS (compare)", """(() => {
        const src = [...document.querySelectorAll('[data-pane="left"] .channel-node')]
          .find(n => n.textContent.includes('S.BUS'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, altKey: true}));
        return 'compare-triggered';
    })()"""),
    ("wait compare tick 1", "'tick'"),
    ("wait compare tick 2", "'tick'"),
    ("wait compare tick 3", "'tick'"),
    ("compare panel", """(() => JSON.stringify({
        panel: !!document.querySelector('.compare-panel'),
        valueDiffRows: document.querySelectorAll('.compare-row.row-value-diff').length}))()"""),
    ("close compare panel", """(() => {
        document.querySelector('.compare-panel .close-btn')?.click();
        return 'closed';
    })()"""),
    ("split view", """(() => {
        [...document.querySelectorAll('.toolbar button')]
          .find(b => b.textContent.includes('스플릿')).click();
        return 'split';
    })()"""),
    ("open dst", f"window.__openSong('{DST_JS}').then(() => 'ok')"),
    ("assign right pane", """(() => {
        const tabs = [...document.querySelectorAll('.tab')];
        const t = tabs.find(t => t.textContent.includes('e2e_target'));
        t.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true}));
        return 'right-assigned';
    })()"""),
    # ---- 체인 이식 (S1, AC-7): 우측(dst 사본) 내 트랙 채널 "1 - guitar 1"(Decapitator+
    # Little MicroShift) → "1 - TOM M"(빈 체인)으로 체인 교체 — 트랙 포함 요구사항 검증.
    # dst 사본 내부에서 진행(전송 전이라 우측 모델이 원본 그대로) — 원본 naiite_14는 건드리지 않음.
    ("ctrl-rightclick guitar1 (chain copy)", """(() => {
        const nodes = [...document.querySelectorAll('[data-pane="right"] .channel-node')];
        const src = nodes.find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('1 - guitar 1'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, ctrlKey: true}));
        return 'chain-copied';
    })()"""),
    ("chain copy status", "document.querySelector('.statusbar')?.textContent"),
    ("rightclick TOM M (chain paste target)", """(() => {
        const nodes = [...document.querySelectorAll('[data-pane="right"] .channel-node')];
        const dst = nodes.find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('1 - TOM M'));
        dst.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'target-clicked';
    })()"""),
    ("chain paste modal", """(() => JSON.stringify({
        modal: !!document.querySelector('.modal h3'),
        text: document.querySelector('.modal h3')?.textContent}))()"""),
    ("confirm chain replace", """(() => {
        [...document.querySelectorAll('.modal-actions button')]
          .find(b => b.textContent.includes('교체')).click();
        return 'confirmed';
    })()"""),
    ("wait chain tick 1", "'tick'"),
    ("wait chain tick 2", "'tick'"),
    ("chain replace status", "document.querySelector('.statusbar')?.textContent"),
    # 클립보드 보존 회귀 검증(아키텍트 리뷰 지적): 트랙 드래그드롭 전송은 clipboard.current와
    # 무관해야 한다 — 먼저 S.BUS를 복사해 clipboard를 채워둔 뒤, 아래 트랙 DnD 전송이
    # 이 복사를 조용히 지우지 않는지 확인한다.
    ("ctx copy S.BUS (clipboard guard setup)", """(() => {
        const src = [...document.querySelectorAll('[data-pane="left"] .channel-node')]
          .find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('S.BUS'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'copied';
    })()"""),
    ("clipboard guard copy status", "document.querySelector('.statusbar')?.textContent"),
    # ---- 트랙 채널 전송 (S4b, AC-6, US-V2-021): 좌측(naiite_14)의 "kick out" 트랙을
    # 우측(dst 사본)으로 드래그앤드롭 — 기본 모드(이벤트 미포함) 확인 후 전송.
    ("dnd track transfer", """(() => {
        const src = [...document.querySelectorAll('[data-pane="left"] .channel-node')]
          .find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('kick out'));
        const dstPane = document.querySelector('[data-pane="right"]');
        const dt = new DataTransfer();
        src.dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer: dt}));
        dstPane.dispatchEvent(new DragEvent('dragover', {bubbles: true, dataTransfer: dt, cancelable: true}));
        dstPane.dispatchEvent(new DragEvent('drop', {bubbles: true, dataTransfer: dt}));
        return 'dropped';
    })()"""),
    ("track transfer modal", """(() => JSON.stringify({
        modal: !!document.querySelector('.modal h3'),
        text: document.querySelector('.modal h3')?.textContent}))()"""),
    ("confirm track transfer", """(() => {
        [...document.querySelectorAll('.modal-actions button')]
          .find(b => b.textContent.includes('전송')).click();
        return 'confirmed';
    })()"""),
    ("wait track tick 1", "'tick'"),
    ("wait track tick 2", "'tick'"),
    ("track transfer status", "document.querySelector('.statusbar')?.textContent"),
    # 클립보드 보존 확인: 트랙 DnD 전송이 확정된 뒤에도 S.BUS 복사가 살아있어야
    # 붙여넣기가 "붙여넣을 항목 없음"이 아니라 실제 전송 흐름으로 이어진다.
    ("paste S.BUS after track transfer (clipboard guard check)", """(() => {
        const pane = document.querySelector('[data-pane="right"] .react-flow__pane');
        pane.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'pasted';
    })()"""),
    ("clipboard guard paste status", "document.querySelector('.statusbar')?.textContent"),
    ("dnd transfer", """(() => {
        const src = [...document.querySelectorAll('[data-pane="left"] .channel-node')]
          .find(n => n.textContent.includes('K.BUS'));
        const dstPane = document.querySelector('[data-pane="right"]');
        const dt = new DataTransfer();
        src.dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer: dt}));
        dstPane.dispatchEvent(new DragEvent('dragover', {bubbles: true, dataTransfer: dt, cancelable: true}));
        dstPane.dispatchEvent(new DragEvent('drop', {bubbles: true, dataTransfer: dt}));
        return 'dropped';
    })()"""),
    ("transfer status", """(() => JSON.stringify({
        status: document.querySelector('.statusbar')?.textContent,
        modal: !!document.querySelector('.modal')}))()"""),
    ("ctx copy K.BUS", """(() => {
        const src = [...document.querySelectorAll('[data-pane="left"] .channel-node')]
          .find(n => n.textContent.includes('K.BUS'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'copied';
    })()"""),
    ("copy status", "document.querySelector('.statusbar')?.textContent"),
    ("ctx paste right (conflict)", """(() => {
        const pane = document.querySelector('[data-pane="right"] .react-flow__pane');
        pane.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'pasted';
    })()"""),
    ("conflict modal", """(() => JSON.stringify({
        modal: !!document.querySelector('.modal'),
        text: document.querySelector('.modal p strong')?.textContent}))()"""),
    ("confirm overwrite", """(() => {
        [...document.querySelectorAll('.modal-actions button')]
          .find(b => b.textContent.includes('덮어쓰기')).click();
        return 'confirmed';
    })()"""),
    ("final status", """(() => JSON.stringify({
        status: document.querySelector('.statusbar')?.textContent,
        rightNodes: document.querySelectorAll('[data-pane="right"] .react-flow__node').length}))()"""),
    # ---- Undo (US-V2-004): 우측 패널 포커스 → Ctrl+Z → 이전 전송 상태로 원복 ----
    ("focus right pane", """(() => {
        document.querySelector('[data-pane="right"]').focus();
        return 'focused';
    })()"""),
    ("nodes before undo", """(() => JSON.stringify({
        rightNodes: document.querySelectorAll('[data-pane="right"] .react-flow__node').length}))()"""),
    ("ctrl+z undo", """(() => {
        const pane = document.querySelector('[data-pane="right"]');
        pane.dispatchEvent(new KeyboardEvent('keydown', {key: 'z', ctrlKey: true, bubbles: true, cancelable: true}));
        return 'undo-sent';
    })()"""),
    ("wait undo tick 1", "'tick'"),
    ("wait undo tick 2", "'tick'"),
    ("undo status", """(() => JSON.stringify({
        status: document.querySelector('.statusbar')?.textContent,
        rightNodes: document.querySelectorAll('[data-pane="right"] .react-flow__node').length}))()"""),
    # ---- US-V3-001 GUI: 여러 곡 일괄 레시피 적용 다이얼로그 (미리보기까지, 읽기 전용) ----
    ("open bulk apply dialog", """(() => {
        const btn = [...document.querySelectorAll('button')]
          .find(b => b.textContent.includes('레시피 일괄 적용'));
        btn.click();
        return 'opened';
    })()"""),
    ("bulk dialog shown", """(() => JSON.stringify({
        modal: !!document.querySelector('.modal-wide'),
        title: document.querySelector('.modal-wide h3')?.textContent}))()"""),
    ("inject dst path", f"""(() => {{
        window.__bulkApplyAddDst('{DST_JS}');
        return 'injected';
    }})()"""),
    ("click preview", """(() => {
        const btn = [...document.querySelectorAll('.modal-wide .modal-actions button')]
          .find(b => b.textContent.includes('미리보기'));
        btn.click();
        return 'preview-clicked';
    })()"""),
    ("wait bulk tick 1", "'tick'"),
    ("wait bulk tick 2", "'tick'"),
    ("bulk preview result", """(() => JSON.stringify({
        blocks: document.querySelectorAll('.bulk-result-block').length,
        planRows: document.querySelectorAll('.bulk-plan-list li').length,
        busSubtree: [...document.querySelectorAll('.bulk-action-bus-subtree')]
          .some(li => li.textContent.includes('MIXOUT'))}))()"""),
    ("close bulk dialog", """(() => {
        const btn = [...document.querySelectorAll('.modal-wide .modal-actions button')]
          .find(b => b.textContent.includes('닫기'));
        btn.click();
        return 'closed';
    })()"""),
]

results: list[tuple[str, str]] = []


def main() -> int:
    app = QApplication(sys.argv)
    window = QMainWindow()
    view = QWebEngineView()
    s = view.settings()
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    bridge = Bridge(window)
    channel = QWebChannel()
    channel.registerObject("bridge", bridge)
    view.page().setWebChannel(channel)
    window.setCentralWidget(view)
    window.resize(1500, 950)
    view.load(QUrl.fromLocalFile(str(DIST_INDEX)))
    window.show()

    state = {"i": -1, "waiting": False}

    def advance():
        if state["waiting"]:
            return
        state["i"] += 1
        if state["i"] >= len(STEPS):
            finish()
            return
        name, js = STEPS[state["i"]]
        state["waiting"] = True

        def handle(result):
            results.append((name, str(result)))
            state["waiting"] = False

        view.page().runJavaScript(js, handle)

    def finish():
        from engine.songcore import SongContainer, load_model
        from engine.songcore.uid_refs import errors_of, validate

        shot = ROOT / "spikes/out/gui_e2e.png"
        view.grab().save(str(shot))
        ok = True
        report = {}
        for name, r in results:
            report[name] = r
        try:
            assert json.loads(report["graph nodes"])["nodes"] == 30
            d = json.loads(report["detail panel"])
            assert d["panel"] and d["inserts"] == 4 and d["title"] == "K.BUS"
            p = json.loads(report["wait params"])
            assert p["rows"] > 0, f"파라미터 행 없음: {p}"
            b = json.loads(report["wait badge"])
            assert b["badge"] and not b["loading"], f"해석불가 배지 미표시: {b}"
            # U2 검색/필터: "CLA-76"을 실제로 쓰는 채널 수와 하이라이트 노드 수가 일치해야 함
            naiite_model = load_model(SongContainer.read(Path(NAIITE)))
            expected_cla76 = sum(
                1 for ch in naiite_model.channels
                if ch.group != "AudioInput"
                and any("CLA-76" in i.plugin_name for i in ch.inserts))
            s = json.loads(report["search result"])
            assert s["matches"] == expected_cla76, \
                f"검색 하이라이트 수 불일치: {s['matches']} != {expected_cla76}"
            # U4 체인 비교: K.BUS를 A로 지정 → S.BUS와 비교 시 value-diff 행 렌더
            assert "비교 기준" in (report["baseline status"] or ""), report["baseline status"]
            cmp_ = json.loads(report["compare panel"])
            assert cmp_["panel"], "비교 패널 미표시"
            assert cmp_["valueDiffRows"] >= 1, f"value-diff 행 없음: {cmp_}"
            # S1 체인 이식: K(트랙) 체인 복사 → SN(트랙) 붙여넣기(교체) 확인
            cp = json.loads(report["chain paste modal"])
            assert cp["modal"] and "체인 붙여넣기" in (cp["text"] or ""), cp
            assert "체인 이식 완료" in (report["chain replace status"] or ""), \
                report["chain replace status"]
            # S4b 트랙 채널 전송: kick out 트랙 DnD → 다이얼로그 → 전송 완료
            assert "복사됨" in report["clipboard guard copy status"], \
                report["clipboard guard copy status"]
            tm = json.loads(report["track transfer modal"])
            assert tm["modal"] and "트랙 채널 전송" in (tm["text"] or ""), tm
            assert "트랙 전송 완료" in (report["track transfer status"] or ""), \
                report["track transfer status"]
            # 클립보드 보존 회귀 검증(아키텍트 리뷰 지적): 트랙 DnD 전송 확정이 이전에 복사해둔
            # S.BUS 클립보드를 조용히 지우지 않아야 함 — "붙여넣을 항목 없음"이면 회귀.
            guard_status = report["clipboard guard paste status"] or ""
            assert "붙여넣을 항목 없음" not in guard_status, \
                f"트랙 전송이 무관한 클립보드를 지웠음(회귀): {guard_status}"
            t = json.loads(report["transfer status"])
            assert "전송 완료" in (t["status"] or ""), t
            assert "복사됨" in report["copy status"], report["copy status"]
            c = json.loads(report["conflict modal"])
            assert c["modal"], "충돌 다이얼로그 미표시(우클릭 붙여넣기 경로)"
            f = json.loads(report["final status"])
            assert "전송 완료" in (f["status"] or ""), f
            assert f["rightNodes"] > 0
            assert DST.with_suffix(".song.bak").exists(), ".bak 없음"
            u = json.loads(report["undo status"])
            assert "복원됨" in (u["status"] or ""), f"undo 상태 메시지 미표시: {u}"
            assert u["rightNodes"] > 0, "undo 후 그래프가 비어있음(재로드 실패)"
            # US-V3-001: 일괄 적용 다이얼로그 — 미리보기까지만(읽기 전용, DST 미변경 확인은 별도)
            bd = json.loads(report["bulk dialog shown"])
            assert bd["modal"] and "일괄 적용" in (bd["title"] or ""), bd
            bp = json.loads(report["bulk preview result"])
            assert bp["blocks"] == 1, f"미리보기 결과 블록 수 불일치: {bp}"
            assert bp["planRows"] > 0, f"미리보기 계획 행 없음: {bp}"
            assert bp["busSubtree"], f"MIXOUT 버스 서브트리 계획 미표시: {bp}"
        except AssertionError as exc:
            ok = False
            print("ASSERT FAIL:", exc)
        for name, r in results:
            print(f"  [{name}] {r[:150]}")
        # 대상 재파싱 검증
        cont = SongContainer.read(DST)
        model = load_model(cont)
        # S4b 트랙 전송 검증: dst에 "kick out" 트랙 채널이 실제로 생성됐는지 확인
        kick_out_ch = model.by_label("kick out")
        track_transfer_ok = kick_out_ch is not None and kick_out_ch.tag == "AudioTrackChannel"
        print(f"  [track-transfer] kick out 채널 생성: {track_transfer_ok}")
        ok = ok and track_transfer_ok
        has_kbus = model.by_label("K.BUS") is not None
        errs = errors_of(validate(cont, model))
        print(f"  [reparse] K.BUS={has_kbus}, errors={len(errs)}")
        ok = ok and has_kbus and not errs
        # S1 체인 이식 검증: TOM M(원래 빈 체인)이 guitar 1과 동일한 체인으로 교체됐는지 확인
        src_ch = model.by_label("1 - guitar 1")
        dst_ch = model.by_label("1 - TOM M")
        expected_chain = ["Decapitator", "Little MicroShift"]
        chain_ok = (src_ch is not None and dst_ch is not None
                   and [i.plugin_name for i in src_ch.inserts] == expected_chain
                   and [i.plugin_name for i in dst_ch.inserts] == expected_chain)
        print(f"  [chain-replace] TOM M 체인 == guitar 1 체인: {chain_ok}")
        ok = ok and chain_ok
        # U3 최근 파일: QSettings에 이번 세션에 연 song 경로가 기록됐는지 직접 확인
        recent = json.loads(bridge.get_recent())
        naiite_recorded = str(Path(NAIITE)) in recent
        print(f"  [recent] naiite_recorded={naiite_recorded}, count={len(recent)}")
        ok = ok and naiite_recorded
        # P3 프리웜 힌트/진행률(US-V2-020): 프론트가 song 로드 시 자동 호출하는 브리지 슬롯이
        # 정상 동작하는지 직접 확인 (프론트 호출 자체는 SongPane의 useEffect로 코드 보증)
        naiite_model = load_model(SongContainer.read(Path(NAIITE)))
        kbus_uid = naiite_model.by_label("K.BUS").uid
        hint_res = json.loads(bridge.hint_visible(NAIITE, json.dumps([kbus_uid])))
        status_res = json.loads(bridge.prewarm_status())
        prewarm_ok = (hint_res.get("status") == "ok"
                     and isinstance(status_res.get("done"), int)
                     and isinstance(status_res.get("total"), int))
        print(f"  [prewarm-bridge] hint_visible={hint_res}, prewarm_status={status_res}")
        ok = ok and prewarm_ok
        print(f"E2E {'PASS' if ok else 'FAIL'} → {shot}")
        app.exit(0 if ok else 1)

    # 스텝 사이 간격: 렌더/비동기 브리지 대기
    ticker = QTimer(window)
    ticker.timeout.connect(advance)
    ticker.start(1800)
    QTimer.singleShot(160000, lambda: (print("E2E TIMEOUT"), app.exit(2)))
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
