"""zip 원시 바이트 수술 유틸 — 무수정 entry는 로컬 헤더+데이터 블록 원본 보존,
수정/추가 entry만 새로 직렬화한다. (S0.1 스파이크 공용, 이후 container.py의 원형)"""
import struct
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

LOCAL_HEADER_SIG = b"PK\x03\x04"
CENTRAL_SIG = b"PK\x01\x02"
EOCD_SIG = b"PK\x05\x06"
UTF8_FLAG = 0x800


@dataclass
class Entry:
    name: str
    local_block: bytes | None = None      # 원시 보존 블록 (무수정 entry)
    central_header: bytes | None = None   # 원시 central 항목 (offset은 쓰기 시 갱신)
    new_data: bytes | None = None         # 교체/신규 데이터 (비압축 원문)
    compress_type: int = zipfile.ZIP_DEFLATED
    template: "Entry | None" = None       # 신규 entry의 헤더 필드 참조용


@dataclass
class SongZip:
    entries: list[Entry] = field(default_factory=list)
    comment: bytes = b""

    @classmethod
    def read(cls, path: Path) -> "SongZip":
        data = path.read_bytes()
        sz = cls()
        with zipfile.ZipFile(path) as zf:
            sz.comment = zf.comment
            for info in zf.infolist():
                off = info.header_offset
                if data[off:off + 4] != LOCAL_HEADER_SIG:
                    raise ValueError(f"bad local header: {info.filename}")
                flags = struct.unpack("<H", data[off + 6:off + 8])[0]
                if flags & 0x08:
                    raise NotImplementedError(f"data descriptor: {info.filename}")
                fnlen, extralen = struct.unpack("<HH", data[off + 26:off + 30])
                block = data[off:off + 30 + fnlen + extralen + info.compress_size]
                sz.entries.append(Entry(info.filename, local_block=block))
        eocd = data.rfind(EOCD_SIG)
        cd_size, cd_off = struct.unpack("<II", data[eocd + 12:eocd + 20])
        pos, idx = cd_off, 0
        while pos < cd_off + cd_size:
            fnlen, extralen, commlen = struct.unpack("<HHH", data[pos + 28:pos + 34])
            end = pos + 46 + fnlen + extralen + commlen
            sz.entries[idx].central_header = data[pos:end]
            idx += 1
            pos = end
        if idx != len(sz.entries):
            raise ValueError("central dir count mismatch")
        return sz

    def get(self, name: str) -> Entry:
        for e in self.entries:
            if e.name == name:
                return e
        raise KeyError(name)

    def read_text(self, path: Path, name: str) -> bytes:
        with zipfile.ZipFile(path) as zf:
            return zf.read(name)

    def replace(self, name: str, data: bytes) -> None:
        e = self.get(name)
        e.new_data = data

    def add(self, name: str, data: bytes, template_name: str,
            compress_type: int = zipfile.ZIP_STORED, after: str | None = None) -> None:
        tmpl = self.get(template_name)
        new = Entry(name, new_data=data, compress_type=compress_type, template=tmpl)
        if after is None:
            self.entries.append(new)
        else:
            idx = next(i for i, e in enumerate(self.entries) if e.name == after)
            self.entries.insert(idx + 1, new)

    def write(self, out_path: Path) -> None:
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
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(bytes(out))


def _build_headers(e: Entry) -> tuple[bytes, bytes]:
    """수정/신규 entry의 로컬+중앙 헤더를 (기존/템플릿 헤더 필드 기반으로) 생성."""
    base = e.central_header if e.central_header is not None else e.template.central_header
    # central 헤더 필드 파싱 (46바이트 고정부)
    (ver_made, ver_need, _flags, _method, mtime, mdate, _crc, _csize, _usize,
     _fnlen, _extralen, _commlen, disk, iattr, eattr, _off) = struct.unpack(
        "<HHHHHHIIIHHHHHII", base[4:46])
    name_bytes = e.name.encode("utf-8")
    try:
        name_bytes.decode("ascii")
        flags = 0x0
    except UnicodeDecodeError:
        flags = UTF8_FLAG
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
