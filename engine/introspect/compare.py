"""체인 비교(diff) 서비스 — U4 체인 비교 뷰(AC-4)의 Python 계산부.

프론트(ComparePanel.tsx)는 렌더만 담당하고, 두 채널 체인의 실제 비교 로직은
여기서 계산해 pytest로 직접 검증한다(Critic MAJOR② 반영).

행 타입:
  - match: 동일 슬롯에 동일 플러그인, 해석 가능하며 파라미터 값도 전부 동일
  - value-diff: 동일 슬롯에 동일 플러그인이지만 파라미터 값이 하나 이상 다름
  - chain-mismatch: 슬롯에 서로 다른 플러그인이 있거나 한쪽에만 인서트가 존재

미해석(interpret 결과가 없거나 status != "ok")인 경우 값 비교는 할 수 없으므로
interpretable=False로 표시하고(구조 비교 폴백), 플러그인 이름 일치 여부만으로
match/chain-mismatch를 판정한다.
"""
from dataclasses import dataclass
from typing import Callable

from ..songcore.mixer_parser import Insert

InterpretLookup = Callable[[Insert], dict | None]


@dataclass(frozen=True)
class ParamDiff:
    name: str
    left_value: str | None
    right_value: str | None


@dataclass(frozen=True)
class CompareRow:
    slot: int
    row_type: str  # "match" | "value-diff" | "chain-mismatch"
    left_plugin: str | None
    right_plugin: str | None
    interpretable: bool
    diffs: tuple[ParamDiff, ...] = ()


def _interpret_params(lookup: InterpretLookup, insert: Insert | None) -> dict[str, str] | None:
    """insert가 없거나 미해석이면 None. 해석 성공 시 {파라미터명: 값} 딕셔너리."""
    if insert is None:
        return None
    result = lookup(insert)
    if result is None or result.get("status") != "ok":
        return None
    return {p["name"]: p["value"] for p in result.get("params", [])}


def compare_chains(left_inserts: list[Insert], right_inserts: list[Insert],
                   lookup: InterpretLookup) -> list[CompareRow]:
    """슬롯(체인 순서) 순으로 나란히 비교한 행 목록을 반환."""
    max_len = max(len(left_inserts), len(right_inserts))
    rows: list[CompareRow] = []
    for slot in range(max_len):
        left = left_inserts[slot] if slot < len(left_inserts) else None
        right = right_inserts[slot] if slot < len(right_inserts) else None
        left_plugin = left.plugin_name if left else None
        right_plugin = right.plugin_name if right else None

        if left is None or right is None or left_plugin != right_plugin:
            rows.append(CompareRow(
                slot=slot, row_type="chain-mismatch",
                left_plugin=left_plugin, right_plugin=right_plugin,
                interpretable=False))
            continue

        left_params = _interpret_params(lookup, left)
        right_params = _interpret_params(lookup, right)
        if left_params is None or right_params is None:
            rows.append(CompareRow(
                slot=slot, row_type="match",
                left_plugin=left_plugin, right_plugin=right_plugin,
                interpretable=False))
            continue

        diffs = tuple(
            ParamDiff(name, left_params.get(name), right_params.get(name))
            for name in sorted(set(left_params) | set(right_params))
            if left_params.get(name) != right_params.get(name)
        )
        rows.append(CompareRow(
            slot=slot, row_type="value-diff" if diffs else "match",
            left_plugin=left_plugin, right_plugin=right_plugin,
            interpretable=True, diffs=diffs))
    return rows
