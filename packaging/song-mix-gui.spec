# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 빌드 스펙 — song-mix-gui 배포용 실행파일.

onedir(폴더형)를 쓰는 이유: onefile은 매 실행마다 임시 폴더에 재압축 해제하므로
(1) QtWebEngine 위성 파일(QtWebEngineProcess.exe/resources.pak/locales/icudtl.dat) 상대경로
탐색이 불안정해지고 (2) engine/introspect의 파라미터 해석 캐시(param_cache/)를 실행파일
옆에 영속시키는 전제(engine/introspect/runtime.py의 data_dir())가 깨진다.

빌드: pyinstaller packaging/song-mix-gui.spec --distpath dist --workpath build --noconfirm
결과: dist/song-mix-gui/song-mix-gui.exe (+ 동봉 DLL/리소스 폴더)
"""
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # packaging/ 의 부모 = 리포 루트

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "app" / "frontend" / "dist"), "app/frontend/dist"),
    ],
    # host_probe.py는 --probe-mode로 지연 임포트(app/main.py)돼 정적 분석이 놓칠 수 있어
    # pedalboard를 명시 — 나머지(engine.*)는 main.py의 최상위 import로 자동 발견됨.
    hiddenimports=["pedalboard"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="song-mix-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="song-mix-gui",
)
