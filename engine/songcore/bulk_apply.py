"""여러 song 파일에 걸친 믹스 레시피 일괄 적용(US-V3-001).

한 곡(src)에서 완성한 채널별 플러그인 체인 + 버스/병렬 구조를 라벨이 일치하는
다른 곡들(dst 여러 개)에 그대로 반영한다. 트랙 라벨은 곡마다 표기가 달라질 수
있어(예: "kick" vs "1 - kick") 자동 유사매칭은 하지 않고 정확한 라벨 일치만
인정한다 — 불일치는 "no-match"로 보고해 사용자가 직접 확인/제외하도록 한다.
"""
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import ParseError

from .container import SongContainer, SongLockedError
from .mixer_parser import Channel, MixerModel, parse_mixer
from .transfer import (MIXER, TransferError, TransferResult, replace_insert_chain,
                       subtree_transfer_set, transfer_subtree)

# SongContainer.read()/parse_mixer()가 손상되거나 지원하지 않는 zip/XML을 만나면
# 던지는 예외들 — 배치의 한 dst 파일 단위 격리를 위해 전부 잡아야 한다(그렇지 않으면
# 이후 dst 파일들이 아예 시도되지 못하고 배치 전체가 죽는다).
UNREADABLE_SONG_ERRORS = (OSError, ValueError, NotImplementedError,
                         zipfile.BadZipFile, ParseError)

BUS_TAGS = ("AudioGroupChannel", "AudioEffectChannel")
TRACK_TAG = "AudioTrackChannel"


@dataclass(frozen=True)
class ChannelPlan:
    label: str
    # "bus-subtree" | "chain-replace" | "excluded" | "no-match" | "not-selected"
    # | "unknown-bus-label"
    action: str
    src_uid: str
    dst_uid: str | None = None


def find_bus_roots(model: MixerModel) -> list[Channel]:
    """버스/FX 서브트리의 최상위 루트만 반환(다른 버스로부터 먹히지 않는 채널).

    transfer_subtree(root)는 root로 라우팅되는 하위 버스까지 전부 따라가므로,
    최상위 루트만 골라 호출해야 중첩 버스가 중복 전송되지 않는다.
    """
    by_uid = model.by_uid()
    roots = []
    for ch in model.channels:
        if ch.tag not in BUS_TAGS:
            continue
        dest = by_uid.get(ch.destination_uid) if ch.destination_uid else None
        if dest is None or dest.tag not in BUS_TAGS:
            roots.append(ch)
    return roots


def bus_channel_tree(model: MixerModel) -> list[tuple[Channel, int, str | None]]:
    """모든 버스/FX 채널을 트리 순서(DFS, 부모 먼저)로 depth + 부모 라벨과 함께 반환.

    find_bus_roots는 "전체" 자동탐색이 서브트리를 중복 전송하지 않도록 최상위
    루트만 골라내지만, 그 결과 describe_source가 이 최상위 라벨만 노출하면 UI의
    "직접 선택" 체크박스에서 중첩 버스(예: MIXOUT 아래 DR.B)를 아예 고를 수 없게
    된다 — plan_recipe(include_bus_labels=...)는 애초에 중첩 라벨 직접 지정을
    지원하므로, 이 함수로 전체 버스 트리를 노출해 그 능력을 UI에서도 쓸 수 있게 한다.
    부모 라벨을 함께 주는 이유: 상위 버스를 고르면 그 서브트리 전체가 통째로
    전송되므로(transfer_subtree), UI가 상위 선택 시 하위 항목을 "포함됨"으로
    자동 표시/비활성화하려면 부모-자식 관계가 필요하다.
    """
    by_uid = model.by_uid()
    children: dict[str | None, list[Channel]] = {}
    for ch in model.channels:
        if ch.tag not in BUS_TAGS:
            continue
        dest = by_uid.get(ch.destination_uid) if ch.destination_uid else None
        parent_uid = dest.uid if dest is not None and dest.tag in BUS_TAGS else None
        children.setdefault(parent_uid, []).append(ch)

    out: list[tuple[Channel, int, str | None]] = []

    def walk(parent_uid: str | None, parent_label: str | None, depth: int) -> None:
        for ch in children.get(parent_uid, []):
            out.append((ch, depth, parent_label))
            walk(ch.uid, ch.label, depth + 1)

    walk(None, None, 0)
    return out


def plan_recipe(src_model: MixerModel, dst_model: MixerModel,
                exclude_labels: set[str],
                include_bus_labels: set[str] | None = None) -> list[ChannelPlan]:
    """dst에 쓰지 않고 라벨 매칭 결과만 계산 — 적용 전 미리보기로도 사용.

    include_bus_labels: None(기본)이면 find_bus_roots가 찾은 모든 최상위 버스
    루트를 대상으로 한다. set을 넘기면 그 라벨을 가진 버스/FX 채널을 곧바로
    서브트리 루트로 취급한다 — 최상위 루트가 아니라 중첩된 버스(예: 최종
    서브믹스버스 아래의 개별 드럼버스)를 사용자가 직접 골라도 그대로 존중한다
    (transfer_subtree는 어느 버스에서 시작하든 그 아래로 라우팅되는 것만 따라가므로
    독립적으로 작동 — 중복 실행 우려가 있는 자동탐색 때만 최상위로 제한하면 된다).
    이때 선택 안 된 최상위 루트는 "not-selected"로 표시(제외가 아니라 "이번엔
    안 고름"임을 구분). 빈 set()을 넘기면 버스/병렬 구조를 전혀 건드리지 않고
    트랙 chain-replace만 수행하게 된다. 소스에 없는 라벨은 "unknown-bus-label"로
    표시(조용히 무시하지 않음 — 오타 방지). 서로 조상-자손 관계인 라벨을 함께
    지정하면(예: {"MIXOUT", "DR.B"}) 어느 쪽이 최종 결과로 남을지 모호해지므로
    ValueError로 거부한다.

    주의 1(버스 전체 이식): include_bus_labels가 None이면 find_bus_roots가 찾은
    최상위 루트(보통 곡의 최종 서브믹스버스 하나)가 그 아래 중첩된 모든 버스/병렬
    구조를 한 번의 서브트리 전송으로 통째로 옮긴다. dst에 라벨은 다르지만 동등한
    역할의 마스터버스가 이미 있어도 인지하지 못하고 별개 채널로 새로 추가한다 —
    자동 병합 없음. include_bus_labels로 원하는 버스만 골라 이 블라스트 반경을
    좁힐 수 있다.
    주의 2(exclude_labels 범위): 최상위 버스 루트/트랙 채널에만 적용되며, 전송될
    버스 서브트리 내부에 중첩된 라벨(예: 최상위가 아닌 FX 버스)은 exclude_labels에
    있어도 서브트리 전송에 그대로 딸려간다 — apply_recipe()가 이 경우
    RecipeResult.warnings에 경고를 남긴다(배제는 하지 않음, 사전 인지용).
    """
    dst_by_label: dict[str, Channel] = {}
    for c in dst_model.channels:
        if c.label in dst_by_label:
            raise ValueError(f"대상 곡에 라벨 중복 채널 존재 — 매칭 불가: {c.label!r}")
        dst_by_label[c.label] = c
    plans: list[ChannelPlan] = []
    auto_roots = find_bus_roots(src_model)

    if include_bus_labels is None:
        for root in auto_roots:
            action = "excluded" if root.label in exclude_labels else "bus-subtree"
            plans.append(ChannelPlan(root.label, action, root.uid))
    else:
        bus_by_label: dict[str, Channel] = {}
        for c in src_model.channels:
            if c.tag not in BUS_TAGS:
                continue
            if c.label in bus_by_label:
                raise ValueError(f"소스 곡에 라벨 중복 버스 채널 존재 — "
                                 f"include_bus_labels로 특정 불가: {c.label!r}")
            bus_by_label[c.label] = c

        selected: list[Channel] = []
        for label in include_bus_labels:
            ch = bus_by_label.get(label)
            if ch is None:
                plans.append(ChannelPlan(label, "unknown-bus-label", ""))
            else:
                selected.append(ch)

        # 겹침(조상-자손) 검사: 하나의 선택이 다른 선택의 서브트리 안에 있으면
        # 어느 쪽이 최종 결과로 남을지 모호해지므로(중복 remove+재삽입) 명시적으로 거부한다.
        for ch in selected:
            subtree = subtree_transfer_set(src_model, ch.uid)
            nested = {o.label for o in selected if o.uid != ch.uid and o.uid in subtree}
            if nested:
                raise ValueError(
                    f"include_bus_labels에 서로 중첩된 버스가 함께 지정됨 — "
                    f"'{ch.label}' 서브트리 안에 {sorted(nested)}가 포함되어 결과가 "
                    f"모호합니다. 겹치지 않게 하나만 선택하세요.")

        for ch in selected:
            action = "excluded" if ch.label in exclude_labels else "bus-subtree"
            plans.append(ChannelPlan(ch.label, action, ch.uid))
        for root in auto_roots:
            if root.label not in include_bus_labels:
                plans.append(ChannelPlan(root.label, "not-selected", root.uid))

    for ch in src_model.channels:
        if ch.tag != TRACK_TAG:
            continue
        if ch.label in exclude_labels:
            plans.append(ChannelPlan(ch.label, "excluded", ch.uid))
            continue
        dst_ch = dst_by_label.get(ch.label)
        if dst_ch is None or dst_ch.tag != TRACK_TAG:
            plans.append(ChannelPlan(ch.label, "no-match", ch.uid))
        else:
            plans.append(ChannelPlan(ch.label, "chain-replace", ch.uid, dst_ch.uid))
    return plans


@dataclass
class RecipeResult:
    plans: list[ChannelPlan] = field(default_factory=list)
    transfers: list[TransferResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def nested_exclusion_warnings(src_model: MixerModel, plans: list[ChannelPlan],
                               exclude_labels: set[str]) -> list[str]:
    """exclude_labels 중 계획된 버스 서브트리 "내부"에 중첩된 라벨을 찾아 경고한다.

    exclude_labels는 최상위 항목에만 적용되므로(plan_recipe 주의 2), 서브트리
    내부 라벨은 실제로는 그대로 전송된다 — 조용히 넘어가지 않고 명시적으로 알린다.
    """
    by_uid = src_model.by_uid()
    warnings: list[str] = []
    for plan in plans:
        if plan.action != "bus-subtree":
            continue
        member_uids = subtree_transfer_set(src_model, plan.src_uid)
        member_labels = {by_uid[u].label for u in member_uids if u in by_uid}
        hit = (member_labels & exclude_labels) - {plan.label}
        if hit:
            warnings.append(
                f"'{plan.label}' 버스 서브트리 내부에 제외 지정 라벨이 포함돼 있어 "
                f"exclude_labels와 무관하게 그대로 전송됩니다(서브트리 내부 가지치기 "
                f"미지원): {sorted(hit)}")
    return warnings


def apply_recipe(src: SongContainer, src_model: MixerModel, dst: SongContainer,
                 exclude_labels: set[str],
                 preserve_external_sends: bool = True,
                 include_bus_labels: set[str] | None = None,
                 allow_nested_exclusion_warnings: bool = False) -> RecipeResult:
    """레시피를 dst 컨테이너에 메모리 상 적용(저장은 호출자가 save_over로 수행).

    fail-closed: 개별 전송 중 하나라도 TransferError를 던지면 그대로 전파한다.
    호출자는 이 함수가 예외 없이 반환했을 때만 dst.save_over()를 호출해야 한다.
    exclude_labels가 버스 서브트리 내부에 중첩되어(nested_exclusion_warnings 발생)
    실제로는 제외가 지켜지지 않는 상황이면, allow_nested_exclusion_warnings=True로
    명시적으로 허용하지 않는 한 어떤 전송도 시도하지 않고 TransferError로 거부한다
    (사용자가 "제외했다고 믿었는데 실제로는 전송됨"을 모르고 넘어가는 것을 방지).
    """
    dst_model = parse_mixer(dst.read_text(MIXER))
    plans = plan_recipe(src_model, dst_model, exclude_labels, include_bus_labels)
    warnings = nested_exclusion_warnings(src_model, plans, exclude_labels)
    if warnings and not allow_nested_exclusion_warnings:
        raise TransferError(
            "제외 지정 라벨이 버스 서브트리 내부에 중첩돼 있어 안전하게 적용할 수 "
            "없음(allow_nested_exclusion_warnings=True로 명시적으로 허용하거나 "
            "exclude_labels/include_bus_labels를 조정할 것): " + "; ".join(warnings))
    result = RecipeResult(plans=plans, warnings=warnings)
    # 버스/FX 서브트리를 먼저 전부 이식해 신규 uid 맵을 만든 뒤, 트랙 체인교체가 그
    # 맵을 참조해 "이번 배치에서 새로 이식된 버스/FX로의 send"만 함께 연결한다
    # (순서 고정 — plans 목록 자체의 원 순서와 무관하게 항상 버스 먼저 처리해야
    # 트랙이 아직 없는 버스로의 send를 놓치지 않는다).
    bus_uid_map: dict[str, str] = {}
    for plan in plans:
        if plan.action == "bus-subtree":
            transfer_result = transfer_subtree(
                src, src_model, plan.src_uid, dst, overwrite_confirmed=True,
                preserve_external_sends=preserve_external_sends)
            result.transfers.append(transfer_result)
            bus_uid_map.update(transfer_result.new_channel_uids)
    for plan in plans:
        if plan.action == "chain-replace":
            result.transfers.append(replace_insert_chain(
                src, src_model, plan.src_uid, dst, plan.dst_uid,
                bus_uid_map=bus_uid_map))
    return result


@dataclass
class BatchOutcome:
    ok: bool
    result: RecipeResult | None = None
    error: str | None = None
    backup_path: Path | None = None


def apply_recipe_to_songs(src_path: Path, dst_paths: list[Path],
                          exclude_labels: set[str],
                          preserve_external_sends: bool = True,
                          dry_run: bool = False,
                          include_bus_labels: set[str] | None = None,
                          allow_nested_exclusion_warnings: bool = False
                          ) -> dict[Path, "BatchOutcome"]:
    """src의 레시피를 여러 dst song 파일에 일괄 적용.

    파일 단위 fail-closed 격리: 한 dst에서 실패해도 다른 dst는 계속 진행한다.
    dry_run=True면 계획/전송을 메모리 상으로만 계산하고 저장하지 않는다
    (라벨 매칭 사전 확인용 — 실제 파일은 손대지 않음).
    """
    src = SongContainer.read(src_path)
    src_model = parse_mixer(src.read_text(MIXER))
    outcomes: dict[Path, BatchOutcome] = {}
    for raw_path in dst_paths:
        dst_path = Path(raw_path)
        try:
            dst = SongContainer.read(dst_path)
            result = apply_recipe(src, src_model, dst, exclude_labels,
                                  preserve_external_sends, include_bus_labels,
                                  allow_nested_exclusion_warnings)
            if dry_run:
                outcomes[dst_path] = BatchOutcome(ok=True, result=result)
            else:
                backup = dst.save_over()
                outcomes[dst_path] = BatchOutcome(ok=True, result=result,
                                                  backup_path=backup)
        except (TransferError, SongLockedError, *UNREADABLE_SONG_ERRORS) as e:
            outcomes[dst_path] = BatchOutcome(ok=False, error=str(e))
    return outcomes
