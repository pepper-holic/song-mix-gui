"""CLI: 한 곡의 믹스 레시피(버스구조+병렬구조+트랙별 플러그인 체인)를 여러 곡에
라벨 매칭 기준으로 일괄 적용한다(engine/songcore/bulk_apply.py).

기본은 미리보기(dry-run)만 수행하고 실제 파일은 절대 건드리지 않는다.
라벨 매칭 결과(어떤 채널이 chain-replace/bus-subtree/excluded/no-match인지)를
반드시 먼저 확인한 뒤 --apply로 실제 적용할 것.

버스/병렬 구조는 기본적으로 "찾아낸 최상위 버스 루트 전부"를 통째로 옮긴다(보통
곡의 최종 서브믹스버스 하나 = 그 아래 전체 버스망). 특정 버스만 옮기고 싶으면
--bus를 반복 지정(그 라벨의 루트만 전송, 나머지는 손대지 않음). --bus를 아예
"" 하나만 주면(즉 --bus-none) 버스/병렬 구조는 전혀 건드리지 않고 트랙 플러그인
체인만 반영한다.

사용 예:
    python -m engine.apply_mix_recipe "src.song" "dst1.song" "dst2.song" --exclude "SN T"
    python -m engine.apply_mix_recipe "src.song" "dst1.song" --exclude "SN T" --bus "DR.B" --apply
    python -m engine.apply_mix_recipe "src.song" "dst1.song" --bus-none --apply  # 트랙 체인만
"""
import argparse
from pathlib import Path

from .songcore import SongContainer, load_model
from .songcore.bulk_apply import (apply_recipe_to_songs, nested_exclusion_warnings,
                                  plan_recipe)


def _print_plan_only(src_path: Path, dst_paths: list[Path], exclude_labels: set[str],
                     include_bus_labels: set[str] | None) -> int:
    """전송을 전혀 시도하지 않고 라벨 매칭 결과만 계산해 보여준다.

    apply_recipe_to_songs와 달리 버스 서브트리 전송이 구조적으로 실패할 상황
    (예: 대상에 필요한 ChannelGroup이 아예 없음)이어도 매칭표 자체는 항상 볼 수
    있다 — 실전송 전 라벨 표기 차이를 먼저 확인하려는 용도.
    """
    src = SongContainer.read(src_path)
    src_model = load_model(src)
    had_error = False
    for dst_path in dst_paths:
        print(f"\n=== {dst_path} (매칭 미리보기만 — 전송 시도 없음) ===")
        try:
            dst_model = load_model(SongContainer.read(dst_path))
            plans = plan_recipe(src_model, dst_model, exclude_labels, include_bus_labels)
        except ValueError as e:
            print(f"  실패(매칭 계산 불가): {e}")
            had_error = True
            continue
        for plan in plans:
            print(f"  [{plan.action}] {plan.label}")
        for w in nested_exclusion_warnings(src_model, plans, exclude_labels):
            print(f"  경고: {w}")
    return 1 if had_error else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("src", type=Path, help="레시피 소스 .song 파일")
    parser.add_argument("dst", type=Path, nargs="+", help="적용 대상 .song 파일(들)")
    parser.add_argument("--exclude", action="append", default=[], metavar="LABEL",
                        help="제외할 채널 라벨(반복 지정 가능, 정확 일치)")
    parser.add_argument("--bus", action="append", default=None, metavar="LABEL",
                        help="전송할 버스 루트 라벨(반복 지정 가능). 미지정 시 전체 버스 루트")
    parser.add_argument("--bus-none", action="store_true",
                        help="버스/병렬 구조를 전혀 건드리지 않고 트랙 체인만 적용")
    parser.add_argument("--plan-only", action="store_true",
                        help="전송을 시도하지 않고 라벨 매칭 결과만 표시(가장 가벼운 사전 확인)")
    parser.add_argument("--apply", action="store_true",
                        help="미지정 시 미리보기만 하고 실제로 쓰지 않음(기본 안전값)")
    parser.add_argument("--allow-nested-exclusion-warnings", action="store_true",
                        help="제외 라벨이 버스 서브트리 내부에 중첩돼 실제로는 배제되지 "
                             "않는 상황이어도 강행(기본은 안전하게 거부)")
    args = parser.parse_args()

    exclude_labels = set(args.exclude)
    include_bus_labels = set() if args.bus_none else (
        set(args.bus) if args.bus is not None else None)

    if args.plan_only:
        return _print_plan_only(args.src, args.dst, exclude_labels, include_bus_labels)

    outcomes = apply_recipe_to_songs(
        args.src, args.dst, exclude_labels, dry_run=not args.apply,
        include_bus_labels=include_bus_labels,
        allow_nested_exclusion_warnings=args.allow_nested_exclusion_warnings)

    for dst_path, outcome in outcomes.items():
        print(f"\n=== {dst_path} ===")
        if not outcome.ok:
            print(f"  실패(파일 미변경): {outcome.error}")
            continue
        for plan in outcome.result.plans:
            print(f"  [{plan.action}] {plan.label}")
        for w in outcome.result.warnings:
            print(f"  경고: {w}")
        if outcome.backup_path:
            print(f"  적용 완료 — 백업: {outcome.backup_path}")
        else:
            print("  (미리보기 — 실제 저장 안 됨. --apply로 실제 적용)")

    failed = [p for p, o in outcomes.items() if not o.ok]
    if failed:
        print(f"\n실패한 대상 {len(failed)}개 — 위 로그 참고.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
