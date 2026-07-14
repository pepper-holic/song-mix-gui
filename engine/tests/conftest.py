"""engine/tests 전역 fixture — 원본 코퍼스 불변성 안전망.

v1 핵심 불가침 원칙("원본 .song 절대 수정 금지")을 개별 테스트 작성자의 재량에
맡기지 않고 스위트 차원에서 자동 강제한다. transfer_subtree/transfer_track/
replace_insert_chain 등 다수 테스트가 src로 실제 코퍼스 경로(NAIITE 등)를 그대로
읽어 쓰는데, 실수로 그 경로에 쓰기가 발생해도 개별 테스트만 봐서는 발견하기 어렵다.
스위트 실행 전/후로 전체 코퍼스의 md5를 비교해 하나라도 바뀌면 즉시 실패시킨다.
"""
import hashlib
from pathlib import Path

import pytest

SONGS_DIR = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")


def _hash_all(paths: list[Path]) -> dict[Path, str]:
    return {p: hashlib.md5(p.read_bytes()).hexdigest() for p in paths}


@pytest.fixture(scope="session", autouse=True)
def corpus_immutability_guard():
    songs = sorted(SONGS_DIR.rglob("*.song"))
    before = _hash_all(songs)
    yield
    after = _hash_all(songs)
    changed = [str(p) for p in before if before[p] != after.get(p)]
    assert not changed, f"원본 코퍼스가 테스트 중 수정됨(불가침 원칙 위반): {changed}"
