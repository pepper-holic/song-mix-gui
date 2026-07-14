""".song zip 컨테이너 리더/라이터.

원칙:
  - 수정하지 않는 entry는 로컬 헤더+압축 데이터 원시 바이트 그대로 보존
    (전 entry 무수정 재작성 시 출력이 원본과 바이트 동일 — S0.1(a) 실증).
  - 저장 전 .bak 백업 생성, 잠금(Studio One 열림) 감지 시 쓰기 거부.
"""
import ctypes
import shutil
import struct
import subprocess
import zipfile
import zlib
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path

LOCAL_HEADER_SIG = b"PK\x03\x04"
CENTRAL_SIG = b"PK\x01\x02"
EOCD_SIG = b"PK\x05\x06"
UTF8_FLAG = 0x800

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
ERROR_SHARING_VIOLATION = 32
INVALID_HANDLE = ctypes.c_void_p(-1).value
STUDIO_ONE_PROCESS_NAMES = ("studio one.exe", "studioone.exe")


class SongLockedError(RuntimeError):
    """대상 파일이 잠겨 있거나 Studio One이 실행 중이어서 쓰기가 거부됨."""


def is_file_locked_exclusively(path: Path) -> tuple[bool, str]:
    """공유 완전 금지 모드 열기로 다른 열린 핸들 존재를 검사한다."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(str(path), GENERIC_READ | GENERIC_WRITE, 0,
                                  None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    err = ctypes.get_last_error()
    if handle == INVALID_HANDLE or handle is None:
        if err == ERROR_SHARING_VIOLATION:
            return True, "다른 프로세스가 파일 핸들 보유(sharing violation)"
        return True, f"열기 실패(winerror {err}) — 보수적으로 잠김 판정"
    kernel32.CloseHandle(handle)
    return False, "열린 핸들 없음"


def is_studio_one_running() -> bool:
    try:
        import psutil
        names = {(p.info.get("name") or "").lower()
                 for p in psutil.process_iter(["name"])}
    except ImportError:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True).stdout
        names = {line.split('","')[0].strip('"').lower()
                 for line in out.splitlines() if line}
    return any(n in names for n in STUDIO_ONE_PROCESS_NAMES)


def check_write_allowed(path: Path) -> tuple[bool, str]:
    if path.exists():
        locked, detail = is_file_locked_exclusively(path)
        if locked:
            return False, f"차단: {detail}"
    if is_studio_one_running():
        return False, "차단: Studio One 실행 중 (보수적 차단)"
    return True, "허용"


@dataclass
class Entry:
    name: str
    local_block: bytes | None = None
    central_header: bytes | None = None
    new_data: bytes | None = None
    compress_type: int = zipfile.ZIP_DEFLATED
    template: "Entry | None" = None


@dataclass
class SongContainer:
    """단일 .song 파일의 entry 컬렉션. 무수정 entry는 원시 블록 보존."""

    source_path: Path
    entries: list[Entry] = field(default_factory=list)
    comment: bytes = b""

    @classmethod
    def read(cls, path: Path) -> "SongContainer":
        path = Path(path)
        data = path.read_bytes()
        self = cls(source_path=path)
        with zipfile.ZipFile(path) as zf:
            self.comment = zf.comment
            for info in zf.infolist():
                off = info.header_offset
                if data[off:off + 4] != LOCAL_HEADER_SIG:
                    raise ValueError(f"bad local header: {info.filename}")
                flags = struct.unpack("<H", data[off + 6:off + 8])[0]
                if flags & 0x08:
                    raise NotImplementedError(f"data descriptor 미지원: {info.filename}")
                fnlen, extralen = struct.unpack("<HH", data[off + 26:off + 30])
                block = data[off:off + 30 + fnlen + extralen + info.compress_size]
                self.entries.append(Entry(info.filename, local_block=block))
        eocd = data.rfind(EOCD_SIG)
        if eocd < 0:
            raise ValueError("EOCD 없음")
        cd_size, cd_off = struct.unpack("<II", data[eocd + 12:eocd + 20])
        pos, idx = cd_off, 0
        while pos < cd_off + cd_size:
            if data[pos:pos + 4] != CENTRAL_SIG:
                raise ValueError("central dir 손상")
            fnlen, extralen, commlen = struct.unpack("<HHH", data[pos + 28:pos + 34])
            end = pos + 46 + fnlen + extralen + commlen
            self.entries[idx].central_header = data[pos:end]
            idx += 1
            pos = end
        if idx != len(self.entries):
            raise ValueError("central/local entry 수 불일치")
        return self

    # ---- entry 접근 ----
    def names(self) -> list[str]:
        return [e.name for e in self.entries]

    def has(self, name: str) -> bool:
        return any(e.name == name for e in self.entries)

    def get(self, name: str) -> Entry:
        for e in self.entries:
            if e.name == name:
                return e
        raise KeyError(name)

    def read_entry(self, name: str) -> bytes:
        e = self.get(name)
        if e.new_data is not None:
            return e.new_data
        with zipfile.ZipFile(self.source_path) as zf:
            return zf.read(name)

    def read_text(self, name: str) -> str:
        return self.read_entry(name).decode("utf-8")

    # ---- 변경 ----
    def replace(self, name: str, data: bytes) -> None:
        self.get(name).new_data = data

    def replace_text(self, name: str, text: str) -> None:
        self.replace(name, text.encode("utf-8"))

    def add(self, name: str, data: bytes, template_name: str,
            compress_type: int = zipfile.ZIP_STORED, after: str | None = None) -> None:
        if self.has(name):
            raise ValueError(f"entry 이미 존재: {name}")
        tmpl = self.get(template_name)
        new = Entry(name, new_data=data, compress_type=compress_type, template=tmpl)
        if after is None:
            self.entries.append(new)
        else:
            idx = next(i for i, e in enumerate(self.entries) if e.name == after)
            self.entries.insert(idx + 1, new)

    # ---- 쓰기 ----
    def to_bytes(self) -> bytes:
        out = bytearray()
        centrals: list[bytes] = []
        offsets: list[int] = []
        for e in self.entries:
            offsets.append(len(out))
            if e.new_data is None:
                out += e.local_block
                centrals.append(e.central_header)
            else:
                local, central = _build_headers(e)
                out += local
                centrals.append(central)
        cd_start = len(out)
        for ch, off in zip(centrals, offsets):
            buf = bytearray(ch)
            struct.pack_into("<I", buf, 42, off)
            out += buf
        cd_size = len(out) - cd_start
        out += struct.pack("<4sHHHHIIH", EOCD_SIG, 0, 0, len(self.entries),
                           len(self.entries), cd_size, cd_start, len(self.comment))
        out += self.comment
        return bytes(out)

    def write_to(self, out_path: Path) -> None:
        """새 경로에 저장 (백업/잠금 검사 없음 — 실험/사본용)."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(self.to_bytes())

    def save_over(self, target: Path | None = None) -> Path:
        """잠금 검사 → .bak 백업 → 덮어쓰기. 백업 경로 반환."""
        target = Path(target) if target else self.source_path
        allowed, reason = check_write_allowed(target)
        if not allowed:
            raise SongLockedError(f"{target}: {reason}")
        bak = target.with_suffix(target.suffix + ".bak")
        if target.exists():
            shutil.copy2(target, bak)
        target.write_bytes(self.to_bytes())
        return bak


def _build_headers(e: Entry) -> tuple[bytes, bytes]:
    base = e.central_header if e.central_header is not None else e.template.central_header
    (ver_made, ver_need, _flags, _method, mtime, mdate, _crc, _csize, _usize,
     _fnlen, _extralen, _commlen, disk, iattr, eattr, _off) = struct.unpack(
        "<HHHHHHIIIHHHHHII", base[4:46])
    name_bytes = e.name.encode("utf-8")
    flags = 0x0 if name_bytes.isascii() else UTF8_FLAG
    data = e.new_data
    crc = zlib.crc32(data) & 0xFFFFFFFF
    if e.compress_type == zipfile.ZIP_DEFLATED:
        comp = zlib.compressobj(6, zlib.DEFLATED, -15)
        payload = comp.compress(data) + comp.flush()
        method = 8
    else:
        payload = data
        method = 0
    local = struct.pack("<4sHHHHHIIIHH", LOCAL_HEADER_SIG, ver_need, flags, method,
                        mtime, mdate, crc, len(payload), len(data),
                        len(name_bytes), 0) + name_bytes + payload
    central = struct.pack("<4sHHHHHHIIIHHHHHII", CENTRAL_SIG, ver_made, ver_need,
                          flags, method, mtime, mdate, crc, len(payload), len(data),
                          len(name_bytes), 0, 0, disk, iattr, eattr, 0) + name_bytes
    return local, central
