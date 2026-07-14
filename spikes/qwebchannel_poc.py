"""US-007 런타임 결정 실험: PySide6 + QWebEngineView + QWebChannel 브리지.

검증 항목:
  1. QWebEngineView가 로컬 HTML을 렌더링하는가
  2. JS→Python 호출(파일 열기 요청)과 Python→JS 응답(파싱 JSON)이 왕복하는가
  3. 실제 songcore 파싱 결과(naiite_14, 채널 33개)가 브리지를 통과하는가

오프스크린 실행 (무인 환경): QT_QPA_PLATFORM=offscreen
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QTimer, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

from engine.songcore import SongContainer, load_model
from engine.songcore.topology import build_graph

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")

HTML = """<!DOCTYPE html><html><head>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
window.addEventListener('load', () => {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    const bridge = channel.objects.bridge;
    const t0 = performance.now();
    bridge.open_song('%PATH%', (resultJson) => {
      const data = JSON.parse(resultJson);
      const ms = performance.now() - t0;
      bridge.report(JSON.stringify({
        channels: data.channels.length,
        nodes: data.graph.nodes.length,
        edges: data.graph.edges.length,
        roundtrip_ms: ms
      }));
    });
  });
});
</script></head><body>bridge test</body></html>"""


class Bridge(QObject):
    def __init__(self):
        super().__init__()
        self.result = None

    @Slot(str, result=str)
    def open_song(self, path: str) -> str:
        c = SongContainer.read(Path(path))
        model = load_model(c)
        graph = build_graph(model)
        payload = model.to_dict()
        payload["graph"] = graph.to_dict()
        return json.dumps(payload)

    @Slot(str)
    def report(self, stats_json: str) -> None:
        self.result = json.loads(stats_json)


def main() -> int:
    t_start = time.time()
    app = QApplication(sys.argv)
    view = QWebEngineView()
    bridge = Bridge()
    channel = QWebChannel()
    channel.registerObject("bridge", bridge)
    view.page().setWebChannel(channel)
    html = HTML.replace("%PATH%", str(NAIITE).replace("\\", "/"))
    view.setHtml(html, QUrl("http://localhost/"))
    view.resize(640, 480)
    view.show()

    def poll():
        if bridge.result is not None:
            elapsed = time.time() - t_start
            print("BRIDGE OK:", json.dumps(bridge.result))
            print(f"total wall time: {elapsed:.2f}s")
            ok = (bridge.result["channels"] == 33
                  and bridge.result["nodes"] == 33
                  and bridge.result["edges"] == 31)
            print("ASSERTIONS:", "PASS" if ok else f"FAIL {bridge.result}")
            app.exit(0 if ok else 1)
        elif time.time() - t_start > 60:
            print("TIMEOUT: bridge 응답 없음")
            app.exit(2)

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(100)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
