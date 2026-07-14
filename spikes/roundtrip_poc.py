"""S0.1(a) 무수정 라운드트립 스파이크.

전략: 수정하지 않는 entry는 로컬 파일 헤더 + 압축 데이터 블록을 원본에서
바이트 그대로 복사하고, 중앙 디렉토리를 재구성한다. 전 entry 무수정이면
출력 파일이 원본과 바이트 동일해야 한다.

사용: python spikes/roundtrip_poc.py <원본.song> <출력.song>
원본은 절대 수정하지 않는다 (읽기 전용 접근 + 사전/사후 해시 검증).
"""
import hashlib
import struct
import sys
import zipfile
from pathlib import Path

LOCAL_HEADER_SIG = b"PK\x03\x04"
CENTRAL_SIG = b"PK\x01\x02"
EOCD_SIG = b"PK\x05\x06"


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class RawEntry:
    """원본 zip에서 로컬 헤더+데이터 블록을 원시 바이트로 보존한 entry."""

    def __init__(self, name: str, local_block: bytes, central_header: bytes):
        self.name = name
        self.local_block = local_block      # local header + filename + extra + data
        self.central_header = central_header  # central dir entry (offset 필드는 쓰기 시 갱신)


def read_raw_entries(song_path: Path) -> tuple[list[RawEntry], bytes]:
    """zip을 파싱해 entry별 원시 블록과 EOCD 코멘트를 추출한다."""
    data = song_path.read_bytes()
    entries: list[RawEntry] = []
    with zipfile.ZipFile(song_path) as zf:
        comment = zf.comment
        for info in zf.infolist():
            off = info.header_offset
            if data[off:off + 4] != LOCAL_HEADER_SIG:
                raise ValueError(f"local header signature mismatch at {off} for {info.filename}")
            fnlen, extralen = struct.unpack("<HH", data[off + 26:off + 30])
            flags = struct.unpack("<H", data[off + 6:off + 8])[0]
            if flags & 0x08:
                raise NotImplementedError(f"data descriptor entry not supported: {info.filename}")
            block_len = 30 + fnlen + extralen + info.compress_size
            local_block = data[off:off + block_len]
            entries.append(RawEntry(info.filename, local_block, b""))

    # 중앙 디렉토리 원시 항목 추출 (EOCD에서 시작 오프셋 획득)
    eocd_pos = data.rfind(EOCD_SIG)
    if eocd_pos < 0:
        raise ValueError("EOCD not found")
    cd_size, cd_offset = struct.unpack("<II", data[eocd_pos + 12:eocd_pos + 20])
    pos = cd_offset
    idx = 0
    while pos < cd_offset + cd_size:
        if data[pos:pos + 4] != CENTRAL_SIG:
            raise ValueError(f"central dir signature mismatch at {pos}")
        fnlen, extralen, commlen = struct.unpack("<HHH", data[pos + 28:pos + 34])
        entry_len = 46 + fnlen + extralen + commlen
        entries[idx].central_header = data[pos:pos + entry_len]
        idx += 1
        pos += entry_len
    if idx != len(entries):
        raise ValueError(f"central dir count {idx} != local count {len(entries)}")
    return entries, comment


def write_raw_zip(entries: list[RawEntry], comment: bytes, out_path: Path) -> None:
    """원시 블록들을 이어 붙이고 중앙 디렉토리/EOCD를 재구성해 zip을 쓴다."""
    out = bytearray()
    offsets: list[int] = []
    for e in entries:
        offsets.append(len(out))
        out += e.local_block
    cd_start = len(out)
    for e, off in zip(entries, offsets):
        ch = bytearray(e.central_header)
        struct.pack_into("<I", ch, 42, off)  # relative offset of local header
        out += ch
    cd_size = len(out) - cd_start
    eocd = struct.pack(
        "<4sHHHHIIH",
        EOCD_SIG, 0, 0, len(entries), len(entries), cd_size, cd_start, len(comment),
    )
    out += eocd + comment
    out_path.write_bytes(bytes(out))


def verify(original: Path, rewritten: Path) -> list[str]:
    """entry 목록/바이트/메타데이터 동일성 검증. 문제 목록 반환."""
    problems: list[str] = []
    with zipfile.ZipFile(original) as za, zipfile.ZipFile(rewritten) as zb:
        names_a = za.namelist()
        names_b = zb.namelist()
        if names_a != names_b:
            problems.append(f"entry list mismatch: {set(names_a) ^ set(names_b)}")
            return problems
        for name in names_a:
            ia, ib = za.getinfo(name), zb.getinfo(name)
            if za.read(name) != zb.read(name):
                problems.append(f"content mismatch: {name}")
            for attr in ("compress_type", "date_time", "CRC", "compress_size",
                         "file_size", "flag_bits", "external_attr", "extra",
                         "create_system", "create_version", "extract_version"):
                if getattr(ia, attr) != getattr(ib, attr):
                    problems.append(f"meta mismatch {name}.{attr}: {getattr(ia, attr)} != {getattr(ib, attr)}")
    return problems


def main() -> int:
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    dst.parent.mkdir(parents=True, exist_ok=True)

    hash_before = md5(src)
    entries, comment = read_raw_entries(src)
    write_raw_zip(entries, comment, dst)
    hash_after = md5(src)

    print(f"entries: {len(entries)}")
    print(f"original md5 before/after read: {hash_before} / {hash_after} "
          f"({'UNTOUCHED' if hash_before == hash_after else 'MODIFIED!!'})")
    out_hash = md5(dst)
    print(f"rewritten md5: {out_hash} ({'BYTE-IDENTICAL' if out_hash == hash_before else 'differs'})")

    problems = verify(src, dst)
    if problems:
        print("VERIFY FAIL:")
        for p in problems:
            print(" -", p)
        return 1
    print("VERIFY PASS: entry list / content bytes / metadata all identical")
    if hash_before != hash_after:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
