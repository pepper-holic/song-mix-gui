"""헤드리스 E2E — GUI 전체 플로우 검증 (US-016~021, US-025).

시나리오:
  1. naiite_14 열기 → 그래프 30노드
  2. K.BUS 노드 클릭 → 상세 패널 + 인서트 4개
  3. 인서트(Pro-Q 3) 클릭 → 파라미터 테이블 (캐시 경유, 해석 가능)
  4. 두 번째 song(임시 사본)을 같은 leaf에 탭으로 연 뒤 컨텍스트 메뉴로 오른쪽 분할,
     드래그로 중앙 병합 → 가장자리 재분할(자유 분할 레이아웃 검증)
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
    # VSCode식 자유 분할 레이아웃: data-pane 값이 이제 "left"/"right" 리터럴이 아니라 생성된
    # leaf id라서 문서 제목(pane-title)으로 song-pane을 찾는 헬퍼를 전역에 등록해 재사용한다.
    ("define paneByTitle helper", """(() => {
        window.__paneByTitle = (substr) => [...document.querySelectorAll('.song-pane')]
          .find(p => p.querySelector('.pane-title')?.textContent.includes(substr));
        return 'helper-defined';
    })()"""),
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
    # ---- 그래프 키보드 내비게이션 (접근성, aria-activedescendant 패턴): K.BUS가 선택된
    # 상태에서 ArrowRight → 다음 열의 논리적 활성 노드로 이동 + 상세패널이 그 노드로 갱신되는지 확인.
    ("keyboard nav right", """(() => {
        const pane = window.__paneByTitle('naiite_14');
        const before = pane.getAttribute('aria-activedescendant');
        pane.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true, cancelable: true}));
        return JSON.stringify({before});
    })()"""),
    ("keyboard nav right result", """(() => JSON.stringify({
        activedescendant: window.__paneByTitle('naiite_14').getAttribute('aria-activedescendant'),
        detailTitle: document.querySelector('.detail-panel h2')?.textContent,
        kbdActive: window.__paneByTitle('naiite_14').querySelectorAll('.react-flow__node.kbd-active').length}))()"""),
    # ---- 검색/필터 (U2, AC-2): "CLA-76" 검색 → 실제 사용 채널 수만큼 하이라이트 ----
    ("search CLA-76", """(() => {
        const input = window.__paneByTitle('naiite_14').querySelector('.search-input');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, 'CLA-76');
        input.dispatchEvent(new Event('input', {bubbles: true}));
        return 'searched';
    })()"""),
    ("wait search tick", "'tick'"),
    ("search result", """(() => JSON.stringify({
        matches: window.__paneByTitle('naiite_14').querySelectorAll('.react-flow__node.search-match').length}))()"""),
    ("clear search", """(() => {
        const input = window.__paneByTitle('naiite_14').querySelector('.search-input');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, '');
        input.dispatchEvent(new Event('input', {bubbles: true}));
        return 'cleared';
    })()"""),
    # ---- 체인 비교 (U4, AC-4): K.BUS를 A로 지정(Shift+우클릭) 후 S.BUS와 비교(Alt+우클릭) ----
    # 둘 다 Pro-Q 3(FX01)를 쓰지만 프리셋이 다르므로 캐시 워밍 후 value-diff 행이 기대됨.
    ("shift-rightclick K.BUS (set baseline)", """(() => {
        const src = [...window.__paneByTitle('naiite_14').querySelectorAll('.channel-node')]
          .find(n => n.textContent.includes('K.BUS') && !n.textContent.includes('RT'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, shiftKey: true}));
        return 'baseline-set';
    })()"""),
    ("baseline status", "document.querySelector('.statusbar')?.textContent"),
    ("alt-rightclick S.BUS (compare)", """(() => {
        const src = [...window.__paneByTitle('naiite_14').querySelectorAll('.channel-node')]
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
    # ---- 자유 분할 레이아웃: dst song을 같은 leaf에 탭으로 연 뒤 탭 컨텍스트 메뉴로 오른쪽 분할.
    ("open dst", f"window.__openSong('{DST_JS}').then(() => 'ok')"),
    ("dst tab count check", """(() => JSON.stringify({
        tabCount: document.querySelectorAll('.tab').length,
        songPaneCount: document.querySelectorAll('.song-pane').length}))()"""),
    ("rightclick dst tab (open split menu)", """(() => {
        const tab = [...document.querySelectorAll('.tab')].find(t => t.textContent.includes('e2e_target'));
        tab.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: 200, clientY: 100}));
        return 'menu-opened';
    })()"""),
    ("split menu shown", """(() => JSON.stringify({
        menu: !!document.querySelector('.tab-context-menu')}))()"""),
    ("click split right", """(() => {
        const btn = [...document.querySelectorAll('.tab-context-menu li button')]
          .find(b => b.textContent.includes('오른쪽으로 분할'));
        btn.click();
        return 'split-clicked';
    })()"""),
    ("split result", """(() => JSON.stringify({
        splitRow: !!document.querySelector('.pane-split-row'),
        songPaneCount: document.querySelectorAll('.song-pane').length,
        hasNaiite: !!window.__paneByTitle('naiite_14'),
        hasTarget: !!window.__paneByTitle('e2e_target')}))()"""),
    # ---- 드래그 기반 분할(핵심 요청) 검증: e2e_target 탭을 naiite 패널 중앙으로 드래그해
    # 병합(leaf 1개로 평탄화) → 다시 그 패널 우측 가장자리로 드래그해 재분할.
    ("drag merge to center", """(() => {
        const dstTab = [...document.querySelectorAll('.tab')].find(t => t.textContent.includes('e2e_target'));
        const body = window.__paneByTitle('naiite_14').parentElement;
        const rect = body.getBoundingClientRect();
        const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
        const dt = new DataTransfer();
        dstTab.dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer: dt}));
        body.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt, clientX: cx, clientY: cy}));
        body.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt, clientX: cx, clientY: cy}));
        return 'merge-dropped';
    })()"""),
    ("merge result", """(() => JSON.stringify({
        splitRow: !!document.querySelector('.pane-split-row'),
        songPaneCount: document.querySelectorAll('.song-pane').length,
        tabCount: document.querySelectorAll('.tab').length}))()"""),
    ("drag resplit to right edge", """(() => {
        const dstTab = [...document.querySelectorAll('.tab')].find(t => t.textContent.includes('e2e_target'));
        const body = document.querySelector('.pane-leaf-body');
        const rect = body.getBoundingClientRect();
        const cx = rect.left + rect.width * 0.9, cy = rect.top + rect.height / 2;
        const dt = new DataTransfer();
        dstTab.dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer: dt}));
        body.dispatchEvent(new DragEvent('dragover', {bubbles: true, cancelable: true, dataTransfer: dt, clientX: cx, clientY: cy}));
        body.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt, clientX: cx, clientY: cy}));
        return 'resplit-dropped';
    })()"""),
    ("resplit result", """(() => JSON.stringify({
        splitRow: !!document.querySelector('.pane-split-row'),
        songPaneCount: document.querySelectorAll('.song-pane').length,
        hasNaiite: !!window.__paneByTitle('naiite_14'),
        hasTarget: !!window.__paneByTitle('e2e_target')}))()"""),
    # ---- 체인 이식 (S1, AC-7): 우측(dst 사본) 내 트랙 채널 "1 - guitar 1"(Decapitator+
    # Little MicroShift) → "1 - TOM M"(빈 체인)으로 체인 교체 — 트랙 포함 요구사항 검증.
    # dst 사본 내부에서 진행(전송 전이라 우측 모델이 원본 그대로) — 원본 naiite_14는 건드리지 않음.
    ("ctrl-rightclick guitar1 (chain copy)", """(() => {
        const nodes = [...window.__paneByTitle('e2e_target').querySelectorAll('.channel-node')];
        const src = nodes.find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('1 - guitar 1'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, ctrlKey: true}));
        return 'chain-copied';
    })()"""),
    ("chain copy status", "document.querySelector('.statusbar')?.textContent"),
    ("rightclick TOM M (chain paste target)", """(() => {
        const nodes = [...window.__paneByTitle('e2e_target').querySelectorAll('.channel-node')];
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
        const src = [...window.__paneByTitle('naiite_14').querySelectorAll('.channel-node')]
          .find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('S.BUS'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'copied';
    })()"""),
    ("clipboard guard copy status", "document.querySelector('.statusbar')?.textContent"),
    # ---- 트랙 채널 전송 (S4b, AC-6, US-V2-021): 좌측(naiite_14)의 "kick out" 트랙을
    # 우측(dst 사본)으로 드래그앤드롭 — 기본 모드(이벤트 미포함) 확인 후 전송.
    ("dnd track transfer", """(() => {
        const src = [...window.__paneByTitle('naiite_14').querySelectorAll('.channel-node')]
          .find(n => n.querySelector('.node-label')?.textContent.trim().startsWith('kick out'));
        const dstPane = window.__paneByTitle('e2e_target');
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
        const pane = window.__paneByTitle('e2e_target').querySelector('.react-flow__pane');
        pane.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'pasted';
    })()"""),
    ("clipboard guard paste status", "document.querySelector('.statusbar')?.textContent"),
    ("dnd transfer", """(() => {
        const src = [...window.__paneByTitle('naiite_14').querySelectorAll('.channel-node')]
          .find(n => n.textContent.includes('K.BUS'));
        const dstPane = window.__paneByTitle('e2e_target');
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
        const src = [...window.__paneByTitle('naiite_14').querySelectorAll('.channel-node')]
          .find(n => n.textContent.includes('K.BUS'));
        src.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}));
        return 'copied';
    })()"""),
    ("copy status", "document.querySelector('.statusbar')?.textContent"),
    ("ctx paste right (conflict)", """(() => {
        const pane = window.__paneByTitle('e2e_target').querySelector('.react-flow__pane');
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
        rightNodes: window.__paneByTitle('e2e_target').querySelectorAll('.react-flow__node').length}))()"""),
    # ---- Undo (US-V2-004): 우측 패널 포커스 → Ctrl+Z → 이전 전송 상태로 원복 ----
    ("focus right pane", """(() => {
        window.__paneByTitle('e2e_target').focus();
        return 'focused';
    })()"""),
    ("nodes before undo", """(() => JSON.stringify({
        rightNodes: window.__paneByTitle('e2e_target').querySelectorAll('.react-flow__node').length}))()"""),
    ("ctrl+z undo", """(() => {
        const pane = window.__paneByTitle('e2e_target');
        pane.dispatchEvent(new KeyboardEvent('keydown', {key: 'z', ctrlKey: true, bubbles: true, cancelable: true}));
        return 'undo-sent';
    })()"""),
    ("wait undo tick 1", "'tick'"),
    ("wait undo tick 2", "'tick'"),
    ("undo status", """(() => JSON.stringify({
        status: document.querySelector('.statusbar')?.textContent,
        rightNodes: window.__paneByTitle('e2e_target').querySelectorAll('.react-flow__node').length}))()"""),
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
    # 자유 분할 레이아웃에서는 "포커스된 leaf"가 Undo 등 이전 조작에 따라 바뀌므로(예: 방금
    # 우측 패널에 포커스를 줬던 Undo 스텝) 다이얼로그의 기본 소스가 naiite_14가 아닐 수 있다
    # — 소스 select를 명시적으로 naiite_14로 지정해 이후 미리보기 검증을 focus 이력과 분리한다.
    ("select bulk src naiite", """(() => {
        const select = document.querySelector('.modal-wide select');
        const opt = [...select.options].find(o => o.textContent.includes('naiite_14'));
        const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
        setter.call(select, opt.value);
        select.dispatchEvent(new Event('change', {bubbles: true}));
        return select.value;
    })()"""),
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
            # 그래프 키보드 내비게이션: ArrowRight로 activedescendant가 실제로 이동하고
            # 상세패널/시각 하이라이트가 그 노드를 따라가는지 확인
            kbd_before = json.loads(report["keyboard nav right"])["before"]
            kbd_after = json.loads(report["keyboard nav right result"])
            assert kbd_before, "초기 activedescendant 없음(K.BUS 선택 안 됨)"
            assert kbd_after["activedescendant"] and kbd_after["activedescendant"] != kbd_before, \
                f"방향키 이동 후 activedescendant 불변: {kbd_after}"
            assert kbd_after["detailTitle"] and kbd_after["detailTitle"] != "K.BUS", kbd_after
            assert kbd_after["kbdActive"] == 1, f"kbd-active 시각 하이라이트 없음: {kbd_after}"
            # 자유 분할 레이아웃: 컨텍스트 메뉴로 오른쪽 분할 생성 + 드래그로 병합/재분할이
            # 실제로 트리를 올바르게 변형하는지 확인(핵심 요청 검증).
            dtc = json.loads(report["dst tab count check"])
            assert dtc["tabCount"] == 2 and dtc["songPaneCount"] == 1, \
                f"dst 탭 추가 후 상태 불일치(같은 leaf에 탭으로 들어가야 함): {dtc}"
            sm = json.loads(report["split menu shown"])
            assert sm["menu"], "탭 우클릭 컨텍스트 메뉴 미표시"
            sr = json.loads(report["split result"])
            assert sr["splitRow"] and sr["songPaneCount"] == 2 and sr["hasNaiite"] and sr["hasTarget"], \
                f"컨텍스트 메뉴 오른쪽 분할 결과 불일치: {sr}"
            mr = json.loads(report["merge result"])
            assert not mr["splitRow"] and mr["songPaneCount"] == 1 and mr["tabCount"] == 2, \
                f"드래그 중앙 병합 결과 불일치: {mr}"
            rr = json.loads(report["resplit result"])
            assert rr["splitRow"] and rr["songPaneCount"] == 2 and rr["hasNaiite"] and rr["hasTarget"], \
                f"드래그 가장자리 재분할 결과 불일치: {rr}"
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
    QTimer.singleShot(190000, lambda: (print("E2E TIMEOUT"), app.exit(2)))
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
