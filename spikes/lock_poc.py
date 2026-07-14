"""S0.3 잠금 감지 스파이크.

AC-5 "Studio One이 열고 있으면 쓰기 차단"의 감지 메커니즘 검증.

메커니즘 2단:
  1) 배타 핸들 검사 — 파일을 쓰기+공유금지 모드로 열어봐서 실패하면 잠김.
     (Windows: CreateFile dwShareMode=0 시도. 다른 프로세스가 어떤 공유든
      허용하지 않는 핸들을 잡고 있으면 ERROR_SHARING_VIOLATION)
  2) 프로세스 휴리스틱 — Studio One(Studio One.exe) 프로세스 존재 여부.
     핸들을 안 잡는 경우(임시 폴더 추출 편집) 대비한 보수적 폴백.

사용:
  python spikes/lock_poc.py <파일>          # 1회 검사
  python spikes/lock_poc.py <파일> --self-test  # 자체 잠금으로 검사 로직 검증
"""
import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
ERROR_SHARING_VIOLATION = 32
INVALID_HANDLE = ctypes.c_void_p(-1).value

STUDIO_ONE_PROCESS_NAMES = ("Studio One.exe", "StudioOne.exe")


def is_file_locked_exclusively(path: Path) -> tuple[bool, str]:
    """공유 완전 금지 모드로 열어 다른 핸들 존재를 검사한다.

    True = 다른 프로세스가 핸들을 잡고 있음 (쓰기 금지해야 함).
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(
        str(path), GENERIC_READ | GENERIC_WRITE,
        0,  # dwShareMode=0: 다른 열린 핸들이 하나라도 있으면 실패
        None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    err = ctypes.get_last_error()
    if handle == INVALID_HANDLE or handle is None:
        if err == ERROR_SHARING_VIOLATION:
            return True, "sharing violation — 다른 프로세스가 핸들 보유"
        return True, f"open failed (winerror {err}) — 보수적으로 잠김 판정"
    kernel32.CloseHandle(handle)
    return False, "배타 열기 성공 — 열린 핸들 없음"


def is_studio_one_running() -> bool:
    try:
        import psutil
        names = {p.name().lower() for p in psutil.process_iter(["name"])}
    except ImportError:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True).stdout
        names = {line.split('","')[0].strip('"').lower()
                 for line in out.splitlines() if line}
    return any(n.lower() in names for n in STUDIO_ONE_PROCESS_NAMES)


def check_write_allowed(path: Path) -> tuple[bool, str]:
    """쓰기 허용 여부 종합 판정. (허용, 사유)"""
    locked, detail = is_file_locked_exclusively(path)
    if locked:
        return False, f"차단: {detail}"
    if is_studio_one_running():
        return False, "차단: Studio One 프로세스 실행 중 (핸들 미보유라도 보수적 차단)"
    return True, "허용: 핸들 없음 + Studio One 미실행"


def self_test(path: Path) -> int:
    """검사 로직 자체 검증: 파일을 열어둔 상태에서 잠김으로 판정되는지."""
    ok = True
    locked, detail = is_file_locked_exclusively(path)
    print(f"[1] 미잠금 상태 검사: locked={locked} ({detail})")
    ok &= not locked

    with open(path, "rb"):
        # 읽기 핸들(공유 허용)만으로는 dwShareMode=0 열기가 실패해야 함
        locked, detail = is_file_locked_exclusively(path)
        print(f"[2] 읽기 핸들 보유 중 검사: locked={locked} ({detail})")
        ok &= locked

    locked, detail = is_file_locked_exclusively(path)
    print(f"[3] 핸들 해제 후 검사: locked={locked} ({detail})")
    ok &= not locked

    running = is_studio_one_running()
    print(f"[4] Studio One 실행 여부: {running}")
    allowed, reason = check_write_allowed(path)
    print(f"[5] 종합 판정: allowed={allowed} ({reason})")
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    path = Path(sys.argv[1])
    if "--self-test" in sys.argv:
        return self_test(path)
    allowed, reason = check_write_allowed(path)
    print(f"{path}: write {'ALLOWED' if allowed else 'BLOCKED'} — {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
