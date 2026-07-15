"""배포 빌드(PyInstaller onedir)와 소스 실행 양쪽에서 쓰는 경로/서브프로세스 헬퍼.

PyInstaller로 얼린 실행 파일에서는 sys.executable이 파이썬 인터프리터가 아니라
이 앱 자신의 exe이고, 소스 트리(spikes/ 등)도 함께 배포되지 않으므로 host_probe
서브프로세스 호출과 캐시 경로 둘 다 여기서 분기 처리한다.
"""
import sys
from pathlib import Path

PROBE = Path(__file__).resolve().parents[2] / "spikes/host_probe.py"


def data_dir() -> Path:
    """캐시처럼 세션 간 지속돼야 하는 데이터의 쓰기 가능한 위치.
    얼린 빌드(onedir)에서는 실행 파일 옆 폴더 — 소스 실행에서는 spikes/out/ 그대로."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2] / "spikes/out"


def probe_cmd(*args: str) -> list[str]:
    """host_probe 서브프로세스 호출 커맨드.
    얼린 빌드에서는 --probe-mode로 자기 자신(exe)을 재호출한다(app/main.py가 처리)."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--probe-mode", *args]
    return [sys.executable, str(PROBE), *args]
