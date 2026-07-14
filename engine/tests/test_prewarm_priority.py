"""P3 프리웜 우선순위(그룹 입도) 테스트 — US-V2-011.

배치 프로브는 플러그인 바이너리 단위이므로 우선순위 재정렬도 화이트박스로
큐 상태(self._queue/_pending)를 직접 조작해 검증한다(실제 서브프로세스 프로브는
test_introspect.py가 이미 배치 정확성을 커버).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.introspect import InterpretService, Inventory


def _keys_for(inv: Inventory, *plugin_names: str) -> list[tuple[str, str | None]]:
    return [(r.path, r.subname) for name in plugin_names
            for r in [inv.resolve(name)] if r is not None]


def test_hint_visible_promotes_matching_group_to_front():
    inv = Inventory()
    inv.load()
    svc = InterpretService(inv)
    proq3, cla76, sslcomp = _keys_for(svc.inventory, "Pro-Q 3", "CLA-76 Stereo", "SSLComp Stereo")
    assert len({proq3, cla76, sslcomp}) == 3, "테스트 전제: 서로 다른 3개 그룹 키 필요"

    svc._queue = [proq3, cla76, sslcomp]  # noqa: SLF001 — 화이트박스 테스트
    svc._pending = {k: [] for k in svc._queue}  # noqa: SLF001
    svc._total_groups = 3  # noqa: SLF001

    svc.hint_visible(["SSLComp Stereo"])

    assert svc._queue[0] == sslcomp  # noqa: SLF001 — 승격된 그룹이 선두로
    assert set(svc._queue) == {proq3, cla76, sslcomp}  # noqa: SLF001 — 나머지는 그대로 보존


def test_hint_visible_preserves_relative_order_of_non_matching():
    inv = Inventory()
    inv.load()
    svc = InterpretService(inv)
    a, b, c = _keys_for(svc.inventory, "Pro-Q 3", "CLA-76 Stereo", "SSLComp Stereo")
    svc._queue = [a, b, c]  # noqa: SLF001
    svc._pending = {k: [] for k in svc._queue}  # noqa: SLF001

    svc.hint_visible(["존재하지않는플러그인"])  # 매치 없음 → 순서 불변

    assert svc._queue == [a, b, c]  # noqa: SLF001


def test_hint_visible_promotes_multiple_matches_together():
    inv = Inventory()
    inv.load()
    svc = InterpretService(inv)
    a, b, c = _keys_for(svc.inventory, "Pro-Q 3", "CLA-76 Stereo", "SSLComp Stereo")
    svc._queue = [a, b, c]  # noqa: SLF001
    svc._pending = {k: [] for k in svc._queue}  # noqa: SLF001

    svc.hint_visible(["SSLComp Stereo", "CLA-76 Stereo"])

    assert set(svc._queue[:2]) == {b, c}  # noqa: SLF001 — 매치된 둘이 앞으로
    assert svc._queue[2] == a  # noqa: SLF001


def test_prewarm_status_reflects_progress():
    svc = InterpretService()
    svc._total_groups = 5  # noqa: SLF001
    svc._done_groups = 2  # noqa: SLF001
    assert svc.prewarm_status() == {"done": 2, "total": 5}


def test_prewarm_status_default_zero():
    svc = InterpretService()
    assert svc.prewarm_status() == {"done": 0, "total": 0}
