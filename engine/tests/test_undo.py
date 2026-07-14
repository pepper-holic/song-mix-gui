"""Undo 스택 테스트 (US-V2-004) — push/pop/한도/무효화."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engine.songcore.undo import MAX_STEPS, UndoStack

SONGS_DIR = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")
SONG_A = SONGS_DIR / "NAIITE_EP/naiite_13/naiite_13.song"
SONG_B = SONGS_DIR / "NAIITE_EP/naiite_14/naiite_14.song"
SONG_C = SONGS_DIR / "NAIITE_EP/naiite_16/naiite_16.song"


@pytest.fixture()
def stack(tmp_path):
    return UndoStack(session_dir=tmp_path / "undo_sess")


def test_push_two_saves_two_undos_restores_original_bytes(tmp_path, stack):
    target = tmp_path / "t.song"
    target.write_bytes(SONG_A.read_bytes())
    original_bytes = target.read_bytes()

    # 연산 1: push(S0) → 저장 → S1
    assert stack.push(target) is True
    target.write_bytes(SONG_B.read_bytes())
    stack.confirm_saved(target)

    # 연산 2: push(S1) → 저장 → S2
    assert stack.push(target) is True
    target.write_bytes(SONG_C.read_bytes())
    stack.confirm_saved(target)

    assert stack.depth(target) == 2

    # undo 1회 → S1로 복원
    r1 = stack.undo_last(target)
    assert r1["status"] == "ok", r1
    assert target.read_bytes() == SONG_B.read_bytes()
    assert stack.depth(target) == 1

    # undo 2회 → 최초(S0) 바이트로 복원
    r2 = stack.undo_last(target)
    assert r2["status"] == "ok", r2
    assert target.read_bytes() == original_bytes
    assert stack.depth(target) == 0

    # 스택 소진 후 undo → 오류
    r3 = stack.undo_last(target)
    assert r3["status"] == "error"


def test_external_modification_invalidates_stack(tmp_path, stack):
    target = tmp_path / "t.song"
    target.write_bytes(SONG_A.read_bytes())

    assert stack.push(target) is True
    target.write_bytes(SONG_B.read_bytes())  # 정상 저장 시뮬레이션
    stack.confirm_saved(target)

    # 외부(Studio One 등)에서 파일을 직접 변경 — mtime과 내용 모두 변경
    time.sleep(0.01)
    target.write_bytes(SONG_C.read_bytes())

    result = stack.undo_last(target)
    assert result["status"] == "error"
    assert "외부" in result["message"]
    # 스택이 무효화되어 완전히 비워짐 (조용히 복원되지 않았음을 확인)
    assert stack.depth(target) == 0
    # 무효화 후 파일 내용은 그대로(외부 수정본) 남아있어야 함 — 덮어쓰지 않음
    assert target.read_bytes() == SONG_C.read_bytes()


def test_max_steps_eviction(tmp_path, stack):
    target = tmp_path / "t.song"
    target.write_bytes(b"dummy-content-not-a-real-song")

    snap_files_seen = []
    for i in range(MAX_STEPS + 5):
        target.write_bytes(f"dummy-content-{i}".encode())
        assert stack.push(target) is True
        key = stack._key(target)  # noqa: SLF001 — 테스트 내부 상태 직접 확인
        snap_files_seen.append(stack._stacks[key][-1].snap_file)

    assert stack.depth(target) == MAX_STEPS
    # 가장 오래된(초과분) 스냅샷 파일들은 디스크에서 제거되어야 함
    for f in snap_files_seen[:5]:
        assert not f.exists()
    # 최근 MAX_STEPS개는 남아있어야 함
    for f in snap_files_seen[5:]:
        assert f.exists()


def test_new_file_not_pushed(tmp_path, stack):
    fresh = tmp_path / "brand_new.song"
    assert not fresh.exists()
    assert stack.push(fresh) is False
    assert stack.depth(fresh) == 0


def test_cleanup_stale_sessions_removes_prior_session_dir(tmp_path, monkeypatch):
    import tempfile

    fake_tmp = tmp_path / "systemp"
    fake_tmp.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_tmp))

    from engine.songcore import undo as undo_mod

    stale_session = undo_mod._session_root() / "stale-session-id"  # noqa: SLF001
    stale_session.mkdir(parents=True)
    (stale_session / "leftover.snap").write_bytes(b"crash-leftover")

    undo_mod.cleanup_stale_sessions()

    assert not undo_mod._session_root().exists()  # noqa: SLF001
