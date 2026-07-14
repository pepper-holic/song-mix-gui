"""세션 내 다단계 Undo — 파일 바이트 스냅샷 스택 (US-V2-004).

원칙(v2 계획 U1 참조):
  - 연산 역산이 아니라 저장 직전 대상 파일 전체의 바이트 스냅샷을 세션 임시폴더에 push.
  - push는 브리지가 save_pipeline을 호출하기 직전에 수행(모듈 자체는 저장을 감싸지 않는다).
  - 신규 경로 저장(write_to, 기존 파일 없음)은 push 대상에서 제외.
  - 복원 전, 디스크가 push 시점 이후 외부에서 변경됐는지(mtime/해시) 확인 — 변경됐다면
    해당 파일의 스택 전체를 무효화하고 복원을 거부한다(자동 검증 불가 = fail-closed).
  - undo_last: pop → 잠금 검사 → 바이트 복원 → 재파싱 + uid_refs.validate() → 실패 시
    스냅샷을 스택에 되돌리고 오류 반환.
"""
import hashlib
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .container import check_write_allowed

MAX_STEPS = 20
_SESSION_ROOT_NAME = "songmix_undo_sessions"


def _session_root() -> Path:
    return Path(tempfile.gettempdir()) / _SESSION_ROOT_NAME


def cleanup_stale_sessions() -> None:
    """앱 시작 시 1회 호출 — 이전 세션(비정상 종료로 남은 크래시 잔존물)을 전부 정리한다."""
    root = _session_root()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


def _new_session_dir() -> Path:
    return _session_root() / uuid.uuid4().hex


def _hash_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


@dataclass
class _Snapshot:
    """복원 대상 바이트(push 시점 디스크 내용) + 저장 후 기대 상태(confirm_saved로 기록)."""

    seq: int
    snap_file: Path
    confirmed_mtime: float | None = field(default=None)
    confirmed_hash: str | None = field(default=None)


class UndoStack:
    """파일 경로별 독립 스택(세션 임시폴더, 최대 MAX_STEPS 단계)."""

    def __init__(self, session_dir: Path | None = None):
        self.session_dir = Path(session_dir) if session_dir else _new_session_dir()
        self._stacks: dict[str, list[_Snapshot]] = {}
        self._invalidated: set[str] = set()
        self._seq = 0

    @staticmethod
    def _key(path: Path) -> str:
        return str(Path(path).resolve())

    def depth(self, path: Path) -> int:
        return len(self._stacks.get(self._key(path), []))

    def push(self, path: Path) -> bool:
        """저장 직전 대상 파일의 현재 바이트를 스냅샷으로 push.

        대상 경로에 기존 파일이 없으면(신규 write_to) undo 대상이 아니므로 False 반환.
        """
        path = Path(path)
        if not path.exists():
            return False
        key = self._key(path)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._seq += 1
        snap_file = self.session_dir / f"{self._seq:06d}.snap"
        shutil.copy2(path, snap_file)
        stack = self._stacks.setdefault(key, [])
        stack.append(_Snapshot(seq=self._seq, snap_file=snap_file))
        if len(stack) > MAX_STEPS:
            evicted = stack.pop(0)
            evicted.snap_file.unlink(missing_ok=True)
        self._invalidated.discard(key)
        return True

    def confirm_saved(self, path: Path) -> None:
        """save_pipeline 성공 직후 호출 — 저장 후 디스크 상태를 top 스냅샷의 기대값으로 기록."""
        path = Path(path)
        stack = self._stacks.get(self._key(path))
        if not stack or not path.exists():
            return
        top = stack[-1]
        top.confirmed_mtime = path.stat().st_mtime
        top.confirmed_hash = _hash_file(path)

    def discard_last(self, path: Path) -> None:
        """push 이후 저장이 실패해 되돌릴 때 사용 — 최상단 스냅샷을 버린다."""
        path = Path(path)
        key = self._key(path)
        stack = self._stacks.get(key)
        if not stack:
            return
        snap = stack.pop()
        snap.snap_file.unlink(missing_ok=True)
        if not stack:
            del self._stacks[key]

    def _invalidate(self, key: str) -> None:
        for snap in self._stacks.get(key, []):
            snap.snap_file.unlink(missing_ok=True)
        self._stacks.pop(key, None)
        self._invalidated.add(key)

    def undo_last(self, path: Path) -> dict:
        """top 스냅샷을 복원. 반환: {"status": "ok"} 또는 {"status": "error", "message": str}."""
        # 지연 import — songcore 패키지 순환 import 회피(container/uid_refs가 이 모듈을 참조하지 않음)
        from . import load_model
        from .container import SongContainer
        from .uid_refs import errors_of, validate

        path = Path(path)
        key = self._key(path)
        if key in self._invalidated:
            return {"status": "error",
                    "message": "파일이 외부에서 수정되어 undo 스택이 무효화되었습니다"}
        stack = self._stacks.get(key)
        if not stack:
            return {"status": "error", "message": "복원할 이전 상태가 없습니다"}

        top = stack[-1]
        if top.confirmed_hash is not None:
            if not path.exists():
                self._invalidate(key)
                return {"status": "error",
                        "message": "대상 파일이 사라져 undo 스택을 무효화했습니다"}
            current_mtime = path.stat().st_mtime
            # 내용 해시가 유일한 권위 있는 무효화 신호다. mtime 불일치만으로 무효화하면
            # 파일시스템 타임스탬프 오차만으로도 undo가 거부되는 플레이키 실패가 실측됨
            # (전체 스위트 실행에서 1회 재현 — 격리 실행 시엔 통과, 즉 타이밍 의존).
            # mtime은 해시 계산을 건너뛰는 빠른 통과 경로로만 쓰고, mtime이 달라도
            # 내용이 그대로면(해시 일치) 무효화하지 않는다. 내용이 실제로 바뀐 경우는
            # 반드시 mtime도 함께 바뀌므로(동일 타임스탬프로 되돌리는 외부 도구가 없는 한)
            # fail-closed 보장은 유지된다.
            if current_mtime != top.confirmed_mtime and _hash_file(path) != top.confirmed_hash:
                self._invalidate(key)
                return {"status": "error",
                        "message": "파일이 외부에서 수정되어(Studio One 등) undo 스택을 무효화했습니다"}

        allowed, reason = check_write_allowed(path)
        if not allowed:
            return {"status": "error", "message": f"차단: {reason}"}

        prior_bytes = path.read_bytes() if path.exists() else None
        path.write_bytes(top.snap_file.read_bytes())

        try:
            reread = SongContainer.read(path)
            model = load_model(reread)
            errs = errors_of(validate(reread, model))
        except Exception as exc:  # noqa: BLE001 — 재파싱 실패도 검증 실패로 취급
            errs = [exc]

        if errs:
            if prior_bytes is not None:
                path.write_bytes(prior_bytes)  # 복원 실패 → 원상태로 되돌리고 스냅샷 보존
            return {"status": "error",
                    "message": "복원 후 재검증 실패 — 스냅샷을 스택에 보존함"}

        stack.pop()
        top.snap_file.unlink(missing_ok=True)
        if not stack:
            del self._stacks[key]
        elif stack[-1].confirmed_hash is not None:
            # 새 top의 기대 상태는 방금 복원한 바이트와 내용상 동일하지만,
            # 이 write가 mtime을 갱신했으므로 그 기준으로 갱신(내용 해시는 불변).
            stack[-1].confirmed_mtime = path.stat().st_mtime
        return {"status": "ok"}
