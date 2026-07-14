"""songcore 단위/통합 테스트 (naiite_14 + 116곡 코퍼스)."""
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore import MIXER_ENTRY, SongContainer, SongLockedError, load_model
from engine.songcore.topology import build_graph

NAIITE = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song")
SONGS_DIR = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")
ALL_SONGS = sorted(SONGS_DIR.rglob("*.song"))


@pytest.fixture(scope="module")
def container() -> SongContainer:
    return SongContainer.read(NAIITE)


@pytest.fixture(scope="module")
def model(container):
    return load_model(container)


@pytest.fixture(scope="module")
def graph(model):
    return build_graph(model)


# ---- US-009 mixer_parser ----

def test_channel_group_counts(model):
    assert len(model.group("AudioTrack")) == 19
    assert len(model.group("AudioGroup")) == 9
    assert len(model.group("AudioEffect")) == 1
    assert len(model.group("AudioInput")) == 3
    assert len(model.group("AudioOutput")) == 1


def test_raw_connection_count(container):
    assert container.read_text(MIXER_ENTRY).count("<Connection") == 50


def test_all_channels_have_unique_uids(model):
    uids = [c.uid for c in model.channels]
    assert all(uids)
    assert len(uids) == len(set(uids)) == 33


def test_kbus_insert_chain_order(model):
    kbus = model.by_label("K.BUS")
    names = [i.plugin_name for i in kbus.inserts]
    assert names == ["Pro-Q 3", "SPL Transient Designer Plus", "CLA-76 Stereo",
                     "JST Clip"]
    # 체인 순서 == presetPath 선두 순번
    for ins in kbus.inserts:
        assert ins.preset_path is not None
        leading = int(ins.preset_path.rsplit("/", 1)[-1].split(" - ")[0])
        assert leading == ins.chain_index + 1


def test_insert_preset_paths_exist_in_zip(container, model):
    names = set(container.names())
    for ch in model.channels:
        for ins in ch.inserts:
            if ins.preset_path:
                assert ins.preset_path in names, f"{ch.label}: {ins.preset_path}"


def test_mixout_chain(model):
    mixout = model.by_label("MIXOUT")
    assert [i.plugin_name for i in mixout.inserts] == \
        ["SSLComp Stereo", "Pro-Q 3", "L4 Ultramaximizer Stereo"]


# ---- US-010 topology ----

def test_kick_routing_path(model, graph):
    kick = model.by_label("kick")
    path = graph.path_to_terminal(kick.uid)
    assert path[:4] == ["kick", "K.BUS", "DR.B", "MIXOUT"]
    assert path[-1] == "메인"


def test_output_edge_count(graph):
    outputs = [e for e in graph.edges if e.kind == "output"]
    sends = [e for e in graph.edges if e.kind == "send"]
    assert len(outputs) == 29  # 33채널 - 입력3 - 종단(메인)1
    assert len(sends) == 2     # kick→FX 1, DR.B→DR Parallel


def test_drum_bus_subtree(model, graph):
    drb = model.by_label("DR.B")
    labels = {model.by_uid()[u].label for u in graph.subtree_uids(drb.uid)}
    assert {"DR.B", "K.BUS", "S.BUS", "T.BUS", "CYM.BUS", "kick", "SN T"} <= labels


# ---- US-008 container ----

def test_roundtrip_byte_identical(container):
    assert container.to_bytes() == NAIITE.read_bytes()


def test_replace_only_touches_target(tmp_path, container):
    c = SongContainer.read(NAIITE)
    text = c.read_text("notepad.xml")
    c.replace_text("notepad.xml", text)  # 동일 내용이라도 재직렬화 경로 통과
    out = tmp_path / "x.song"
    c.write_to(out)
    with zipfile.ZipFile(NAIITE) as za, zipfile.ZipFile(out) as zb:
        for n in za.namelist():
            assert za.read(n) == zb.read(n)
        assert zb.testzip() is None


def test_save_over_creates_bak(tmp_path):
    target = tmp_path / "copy.song"
    target.write_bytes(NAIITE.read_bytes())
    c = SongContainer.read(target)
    bak = c.save_over()
    assert bak.exists()
    assert bak.read_bytes() == NAIITE.read_bytes()
    assert target.read_bytes() == NAIITE.read_bytes()


def test_save_over_refuses_locked_file(tmp_path):
    target = tmp_path / "locked.song"
    target.write_bytes(NAIITE.read_bytes())
    c = SongContainer.read(target)
    with open(target, "rb"):
        with pytest.raises(SongLockedError):
            c.save_over()


# ---- US-011 116곡 코퍼스 ----

def test_corpus_present():
    assert len(ALL_SONGS) >= 100, f"코퍼스 {len(ALL_SONGS)}개 — 경로 확인 필요"


@pytest.mark.parametrize("song", ALL_SONGS, ids=lambda p: p.stem[:40])
def test_corpus_roundtrip(song):
    c = SongContainer.read(song)
    rewritten = c.to_bytes()
    original = song.read_bytes()
    if rewritten != original:
        # 바이트 불일치 시 entry 수준 동일성으로 원인 판별
        import io
        with zipfile.ZipFile(song) as za, zipfile.ZipFile(io.BytesIO(rewritten)) as zb:
            assert za.namelist() == zb.namelist(), f"{song.name}: entry 목록 상이"
            for n in za.namelist():
                assert za.read(n) == zb.read(n), f"{song.name}: {n} 내용 상이"
        pytest.fail(f"{song.name}: entry 동일하나 바이트 불일치(컨테이너 구조 차이)")


@pytest.mark.parametrize("song", ALL_SONGS, ids=lambda p: p.stem[:40])
def test_corpus_parses(song):
    c = SongContainer.read(song)
    if not c.has(MIXER_ENTRY):
        pytest.skip("audiomixer.xml 없음")
    model = load_model(c)
    assert model.channels, f"{song.name}: 채널 0개"
    graph = build_graph(model)
    assert graph.nodes
