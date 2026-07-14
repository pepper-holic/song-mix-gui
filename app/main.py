"""Song Mix GUI — PySide6 + QWebEngineView(React Flow) + songcore 인프로세스.

실행:  python app/main.py
헤드리스 자기검증:  QT_QPA_PLATFORM=offscreen python app/main.py --self-test
"""
import json
import shutil
import sys
import threading
import time
from pathlib import Path

_PROC_START = time.perf_counter()  # P1 성능 계측(spikes/perf_budget.py)의 "시작" 기준점

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QObject, QSettings, QTimer, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from engine.introspect import InterpretService, Inventory, compare_chains
from engine.songcore import (MIXER_ENTRY, SongContainer, SongLockedError,
                             load_model)
from engine.songcore.bulk_apply import (apply_recipe, bus_channel_tree,
                                        find_bus_roots,
                                        nested_exclusion_warnings, plan_recipe)
from engine.songcore.mixer_parser import parse_mixer
from engine.songcore.topology import build_graph
from engine.songcore.transfer import (TransferError, detect_conflicts,
                                      replace_insert_chain,
                                      subtree_transfer_set, transfer_subtree,
                                      transfer_track)
from engine.songcore.uid_refs import errors_of, validate
from engine.songcore.undo import UndoStack, cleanup_stale_sessions

DIST_INDEX = ROOT / "app/frontend/dist/index.html"
RECENT_MAX = 10  # 최근 파일 목록 최대 개수 (US-V2-003)


def is_history_snapshot(song_path: Path) -> bool:
    """Studio One은 자동저장/명명된 스냅샷을 전부 각 곡 폴더 하위 History/에
    쌓아둔다(예: "naiite_1 20260617-125453 (Autosaved).song") — 폴더 스캔 시
    이런 항목이 섞이면 "원본" 파일을 찾기 어려워지므로 경로에 History 컴포넌트가
    있으면 걸러낸다."""
    return any(part.lower() == "history" for part in song_path.parts)


def song_payload(path: Path) -> dict:
    container = SongContainer.read(path)
    model = load_model(container)
    payload = model.to_dict()
    payload["graph"] = build_graph(model).to_dict()
    return payload


def save_pipeline(dst: SongContainer, target: Path) -> dict:
    """잠금 검사 → .bak → 덮어쓰기 → 재파싱 + 무결성 검사. (US-021)"""
    bak = dst.save_over(target)  # 내부에서 잠금 검사 + 백업
    reread = SongContainer.read(target)
    model = load_model(reread)
    errs = errors_of(validate(reread, model))
    if errs:
        # 검증 실패 → 백업 복원 안내와 함께 실패 보고 (파일은 그대로, 사용자가 판단)
        shutil.copy2(bak, target)
        raise TransferError(
            "저장 후 재검증 실패 — 백업에서 자동 복원함: "
            + "; ".join(p.message for p in errs[:3]))
    return {"backup": str(bak)}


class Bridge(QObject):
    def __init__(self, window: QMainWindow):
        super().__init__()
        self.window = window
        self.interpreter = InterpretService(Inventory())
        self.undo = UndoStack()
        self._prewarmed: set[str] = set()
        self.settings = QSettings("songmix", "app")

    def _push_undo(self, path: str) -> bool:
        """save_pipeline 호출 직전에 대상 파일 바이트를 undo 스택에 push (US-V2-004)."""
        return self.undo.push(Path(path))

    # ---- 최근 파일 (US-V2-003) ----
    def _recent_list(self) -> list[str]:
        raw = self.settings.value("recentFiles", [])
        if not raw:
            return []
        if isinstance(raw, str):
            return [raw]
        return list(raw)

    def _record_recent(self, path: str) -> None:
        norm = str(Path(path))
        recent = [p for p in self._recent_list() if p != norm]
        recent.insert(0, norm)
        self.settings.setValue("recentFiles", recent[:RECENT_MAX])

    @Slot(result=str)
    def get_recent(self) -> str:
        return json.dumps(self._recent_list(), ensure_ascii=False)

    def _start_prewarm(self, path: str) -> None:
        """song의 전체 인서트 프리셋을 백그라운드에서 미리 해석해 캐시.

        플러그인당 1회 로드(배치 프로브)라 첫 클릭 대기(특히 WaveShell 수십 초)를 제거한다.
        """
        if path in self._prewarmed:
            return
        self._prewarmed.add(path)

        def work() -> None:
            try:
                model = load_model(SongContainer.read(Path(path)))
                inserts = [(i.preset_path, i.plugin_name)
                           for ch in model.channels for i in ch.inserts
                           if i.preset_path]
                stats = self.interpreter.prewarm(Path(path), inserts)
                print(f"[prewarm] {Path(path).name}: {stats}", flush=True)
            except Exception as exc:  # noqa: BLE001 — 프리웜 실패는 기능 저하일 뿐
                print(f"[prewarm] 실패 {path}: {exc}", flush=True)

        threading.Thread(target=work, daemon=True).start()

    # ---- 열기 ----
    @Slot(result=str)
    def open_song_dialog(self) -> str:
        path, _f = QFileDialog.getOpenFileName(
            self.window, "song 열기",
            str(Path.home() / "Documents/Studio Pro/Songs"),
            "Studio One Song (*.song)")
        if not path:
            return json.dumps({"status": "cancelled"})
        return self.open_song(path)

    @Slot(str, result=str)
    def open_song(self, path: str) -> str:
        try:
            payload = song_payload(Path(path))
            self._start_prewarm(path)
            self._record_recent(path)
            return json.dumps({"status": "ok", "path": path, "model": payload},
                              ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 — UI 경계: 모든 실패를 사용자 메시지로
            return json.dumps({"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    # ---- 전송 ----
    @Slot(str, str, str, bool, bool, result=str)
    def transfer_subtree(self, src_path: str, root_uid: str, dst_path: str,
                         confirmed: bool, preserve_sends: bool = False) -> str:
        try:
            src = SongContainer.read(Path(src_path))
            src_model = load_model(src)
            dst = SongContainer.read(Path(dst_path))
            if not confirmed:
                uids = subtree_transfer_set(src_model, root_uid)
                conflicts = detect_conflicts(src_model, uids, dst, load_model(dst))
                if conflicts:
                    return json.dumps({
                        "status": "conflict",
                        "conflicts": [{"label": c.label, "kind": c.kind}
                                      for c in conflicts]}, ensure_ascii=False)
            result = transfer_subtree(src, src_model, root_uid, dst,
                                      overwrite_confirmed=confirmed,
                                      preserve_external_sends=preserve_sends)
            pushed = self._push_undo(dst_path)
            try:
                saved = save_pipeline(dst, Path(dst_path))
            except Exception:
                if pushed:
                    self.undo.discard_last(Path(dst_path))
                raise
            if pushed:
                self.undo.confirm_saved(Path(dst_path))
            return json.dumps({"status": "ok", "savedBackup": saved["backup"],
                               "droppedSends": result.dropped_sends},
                              ensure_ascii=False)
        except (TransferError, SongLockedError) as exc:
            return json.dumps({"status": "error", "message": str(exc)},
                              ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error",
                               "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    @Slot(str, str, str, str, result=str)
    def replace_chain(self, src_path: str, src_uid: str, dst_path: str,
                      dst_uid: str) -> str:
        try:
            src = SongContainer.read(Path(src_path))
            src_model = load_model(src)
            dst = SongContainer.read(Path(dst_path))
            replace_insert_chain(src, src_model, src_uid, dst, dst_uid)
            pushed = self._push_undo(dst_path)
            try:
                saved = save_pipeline(dst, Path(dst_path))
            except Exception:
                if pushed:
                    self.undo.discard_last(Path(dst_path))
                raise
            if pushed:
                self.undo.confirm_saved(Path(dst_path))
            return json.dumps({"status": "ok", "savedBackup": saved["backup"]},
                              ensure_ascii=False)
        except (TransferError, SongLockedError, KeyError) as exc:
            return json.dumps({"status": "error", "message": str(exc)},
                              ensure_ascii=False)

    # ---- 트랙 채널 전송 (S4b/S4d, US-V2-017/018) ----
    @Slot(str, str, str, bool, result=str)
    def transfer_track(self, src_path: str, channel_uid: str, dst_path: str,
                       include_events: bool) -> str:
        try:
            src = SongContainer.read(Path(src_path))
            src_model = load_model(src)
            dst = SongContainer.read(Path(dst_path))
            result = transfer_track(src, src_model, channel_uid, dst,
                                    include_events=include_events)
            pushed = self._push_undo(dst_path)
            try:
                saved = save_pipeline(dst, Path(dst_path))
            except Exception:
                if pushed:
                    self.undo.discard_last(Path(dst_path))
                raise
            if pushed:
                self.undo.confirm_saved(Path(dst_path))
            warnings = [n for n in result.notes if n.startswith("경고")]
            return json.dumps({"status": "ok", "savedBackup": saved["backup"],
                               "message": "; ".join(warnings) if warnings else None},
                              ensure_ascii=False)
        except (TransferError, SongLockedError) as exc:
            return json.dumps({"status": "error", "message": str(exc)},
                              ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error",
                               "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    # ---- 해석 ----
    @Slot(str, str, result=str)
    def interpret_preset(self, song_path: str, preset_entry: str) -> str:
        try:
            container = SongContainer.read(Path(song_path))
            model = load_model(container)
            plugin_name = next(
                (i.plugin_name for ch in model.channels for i in ch.inserts
                 if i.preset_path == preset_entry), None)
            if plugin_name is None:
                return json.dumps({"status": "error", "pluginName": "?",
                                   "params": [],
                                   "message": "인서트를 찾을 수 없음"}, ensure_ascii=False)
            out = self.interpreter.interpret(Path(song_path), preset_entry,
                                             plugin_name)
            return json.dumps(out, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "pluginName": "?", "params": [],
                               "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    # ---- 프리웜 우선순위/진행률 (US-V2-011, P3) ----
    @Slot(str, str, result=str)
    def hint_visible(self, song_path: str, uids_json: str) -> str:
        """가시/선택 채널의 플러그인 그룹을 프리웜 큐 선두로 승격."""
        try:
            uids = json.loads(uids_json)
            model = load_model(SongContainer.read(Path(song_path)))
            by_uid = model.by_uid()
            plugin_names = {i.plugin_name for uid in uids if (ch := by_uid.get(uid))
                            for i in ch.inserts if i.plugin_name}
            self.interpreter.hint_visible(list(plugin_names))
            return json.dumps({"status": "ok"})
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    @Slot(result=str)
    def prewarm_status(self) -> str:
        return json.dumps(self.interpreter.prewarm_status(), ensure_ascii=False)

    # ---- 체인 비교 (US-V2-004b / U4, AC-4) ----
    @Slot(str, str, str, str, result=str)
    def compare_channels(self, left_path: str, left_uid: str,
                         right_path: str, right_uid: str) -> str:
        """두 채널의 인서트 체인을 diff — 계산은 engine.introspect.compare.compare_chains 그대로 재사용."""
        try:
            left_model = load_model(SongContainer.read(Path(left_path)))
            right_model = load_model(SongContainer.read(Path(right_path)))
            left_ch = left_model.by_uid().get(left_uid)
            right_ch = right_model.by_uid().get(right_uid)
            if left_ch is None or right_ch is None:
                return json.dumps({"status": "error", "message": "채널을 찾을 수 없음"},
                                  ensure_ascii=False)

            # 좌/우가 서로 다른 song 파일일 수 있어 인서트별로 소속 파일을 기억해두고 해석한다
            # (compare_chains의 lookup은 Insert 1개만 받으므로 id() 키 캐시로 파일을 구분).
            interpreted: dict[int, dict | None] = {}
            for song_path, ch in ((left_path, left_ch), (right_path, right_ch)):
                for ins in ch.inserts:
                    interpreted[id(ins)] = (
                        self.interpreter.interpret(Path(song_path), ins.preset_path,
                                                   ins.plugin_name)
                        if ins.preset_path else None)

            rows = compare_chains(list(left_ch.inserts), list(right_ch.inserts),
                                  lambda ins: interpreted.get(id(ins)))
            out_rows = [{
                "slot": r.slot, "rowType": r.row_type,
                "leftPlugin": r.left_plugin, "rightPlugin": r.right_plugin,
                "interpretable": r.interpretable,
                "diffs": [{"name": d.name, "leftValue": d.left_value,
                          "rightValue": d.right_value} for d in r.diffs],
            } for r in rows]
            return json.dumps({"status": "ok", "leftLabel": left_ch.label,
                               "rightLabel": right_ch.label, "rows": out_rows},
                              ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error",
                               "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    # ---- 여러 곡 일괄 레시피 적용 (US-V3-001) ----
    @Slot(result=str)
    def pick_song_files_dialog(self) -> str:
        """대상 곡 여러 개를 한 번에 선택하는 파일 다이얼로그(다중 선택)."""
        paths, _f = QFileDialog.getOpenFileNames(
            self.window, "대상 곡 선택(여러 개 가능)",
            str(Path.home() / "Documents/Studio Pro/Songs"),
            "Studio One Song (*.song)")
        return json.dumps({"status": "ok" if paths else "cancelled", "paths": paths},
                          ensure_ascii=False)

    @Slot(str, result=str)
    def describe_source(self, src_path: str) -> str:
        """소스 곡의 트랙 라벨 + 버스 트리(중첩 포함)를 즉시 조회(대상 불필요) —
        일괄 적용 다이얼로그가 제외 라벨 체크박스/버스 선택 목록을 미리보기 없이
        바로 채울 수 있도록 한다(자유 텍스트 대신 실제 라벨을 골라 오타를 방지).
        busTree는 최상위 루트뿐 아니라 중첩 버스도 depth와 함께 전부 노출한다
        (find_bus_roots만 쓰면 "직접 선택" 체크박스에서 중첩 버스를 고를 방법이
        없어져 UI가 실제로 존재하는 버스보다 적게 보여주는 문제가 있었음)."""
        try:
            model = load_model(SongContainer.read(Path(src_path)))
            track_labels = [c.label for c in model.channels if c.tag == "AudioTrackChannel"]
            bus_tree = [{"label": ch.label, "depth": depth, "parentLabel": parent}
                       for ch, depth, parent in bus_channel_tree(model)]
            return json.dumps({"status": "ok", "trackLabels": track_labels,
                               "busTree": bus_tree}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    @Slot(result=str)
    def pick_song_directory_dialog(self) -> str:
        """일괄 적용 대상 곡을 폴더 단위로 찾기 위한 폴더 선택 다이얼로그."""
        path = QFileDialog.getExistingDirectory(
            self.window, "폴더에서 song 파일 검색",
            str(Path.home() / "Documents/Studio Pro/Songs"))
        return json.dumps({"status": "ok" if path else "cancelled", "path": path},
                          ensure_ascii=False)

    @Slot(str, result=str)
    def scan_song_directory(self, dir_path: str) -> str:
        """경로 하위 .song 파일을 재귀 탐색하고 파일별 트랙 현황(라벨+버스 개수)을
        반환 — 대상 곡을 하나씩 파일 다이얼로그로 고르는 대신, 폴더를 지정하면
        그 안의 곡들을 미리 훑어보고 어떤 걸 일괄 적용 대상에 넣을지 고를 수
        있게 한다. 개별 파일 파싱 실패는 그 파일만 error로 격리(배치 전체를
        막지 않음 — apply_bulk_recipe의 fail-closed 격리 방식과 동일한 원칙)."""
        try:
            root = Path(dir_path)
            entries = []
            for song_path in sorted(root.rglob("*.song")):
                if is_history_snapshot(song_path):
                    continue  # 자동저장/히스토리 스냅샷 제외 — 원본만 노출
                try:
                    model = load_model(SongContainer.read(song_path))
                    track_labels = [c.label for c in model.channels
                                    if c.tag == "AudioTrackChannel"]
                    bus_count = len(find_bus_roots(model))
                    entries.append({"path": str(song_path), "status": "ok",
                                    "trackLabels": track_labels, "busCount": bus_count})
                except Exception as exc:  # noqa: BLE001 — 파일 단위 격리
                    entries.append({"path": str(song_path), "status": "error",
                                    "message": f"{type(exc).__name__}: {exc}"})
            return json.dumps({"status": "ok", "entries": entries}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    @Slot(str, str, str, str, result=str)
    def preview_bulk_recipe(self, src_path: str, dst_paths_json: str,
                            exclude_labels_json: str, include_bus_labels_json: str) -> str:
        """전송을 시도하지 않고 라벨 매칭 결과 + 버스 루트 목록만 계산(엔진 bulk_apply 그대로 재사용)."""
        try:
            dst_paths = json.loads(dst_paths_json)
            exclude_labels = set(json.loads(exclude_labels_json))
            raw_bus = json.loads(include_bus_labels_json)
            include_bus_labels = set(raw_bus) if raw_bus is not None else None

            src_model = load_model(SongContainer.read(Path(src_path)))
            bus_roots = [c.label for c in find_bus_roots(src_model)]
            previews = []
            for dst_path in dst_paths:
                try:
                    dst_model = load_model(SongContainer.read(Path(dst_path)))
                    plans = plan_recipe(src_model, dst_model, exclude_labels,
                                        include_bus_labels)
                    warnings = nested_exclusion_warnings(src_model, plans, exclude_labels)
                    previews.append({
                        "path": dst_path, "status": "ok",
                        "plans": [{"label": p.label, "action": p.action} for p in plans],
                        "warnings": warnings})
                except Exception as exc:  # noqa: BLE001 — UI 경계: per-dst 실패를 격리
                    previews.append({"path": dst_path, "status": "error",
                                     "message": f"{type(exc).__name__}: {exc}"})
            return json.dumps({"status": "ok", "busRoots": bus_roots, "previews": previews},
                              ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    @Slot(str, str, str, str, bool, result=str)
    def apply_bulk_recipe(self, src_path: str, dst_paths_json: str,
                          exclude_labels_json: str, include_bus_labels_json: str,
                          allow_nested_exclusion_warnings: bool) -> str:
        """여러 dst song에 src의 믹스 레시피를 일괄 적용 — 파일 단위 fail-closed 격리 +
        기존 단일 전송 슬롯과 동일하게 Undo 스택에 편입(save_pipeline 재사용)."""
        try:
            dst_paths = json.loads(dst_paths_json)
            exclude_labels = set(json.loads(exclude_labels_json))
            raw_bus = json.loads(include_bus_labels_json)
            include_bus_labels = set(raw_bus) if raw_bus is not None else None

            src = SongContainer.read(Path(src_path))
            src_model = load_model(src)
            outcomes = []
            for dst_path in dst_paths:
                try:
                    dst = SongContainer.read(Path(dst_path))
                    result = apply_recipe(src, src_model, dst, exclude_labels,
                                          include_bus_labels=include_bus_labels,
                                          allow_nested_exclusion_warnings=
                                          allow_nested_exclusion_warnings)
                    pushed = self._push_undo(dst_path)
                    try:
                        saved = save_pipeline(dst, Path(dst_path))
                    except Exception:
                        if pushed:
                            self.undo.discard_last(Path(dst_path))
                        raise
                    if pushed:
                        self.undo.confirm_saved(Path(dst_path))
                    outcomes.append({"path": dst_path, "status": "ok",
                                     "savedBackup": saved["backup"],
                                     "warnings": result.warnings})
                except (TransferError, SongLockedError) as exc:
                    outcomes.append({"path": dst_path, "status": "error", "message": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    outcomes.append({"path": dst_path, "status": "error",
                                     "message": f"{type(exc).__name__}: {exc}"})
            return json.dumps({"status": "ok", "outcomes": outcomes}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"status": "error", "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)

    # ---- 창 제목 (상용 앱 관례: 현재 활성 파일 표시) ----
    @Slot(str)
    def set_window_title(self, title: str) -> None:
        self.window.setWindowTitle(title)

    # ---- Undo (US-V2-004) ----
    @Slot(str, result=str)
    def undo_last(self, path: str) -> str:
        try:
            result = self.undo.undo_last(Path(path))
            if result["status"] != "ok":
                return json.dumps(result, ensure_ascii=False)
            payload = song_payload(Path(path))
            fname = Path(path).name
            return json.dumps({"status": "ok", "model": payload,
                               "message": f"복원됨: {fname}"}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 — UI 경계: 모든 실패를 사용자 메시지로
            return json.dumps({"status": "error",
                               "message": f"{type(exc).__name__}: {exc}"},
                              ensure_ascii=False)


def run_self_test(window: QMainWindow, view: QWebEngineView, app: QApplication) -> None:
    """헤드리스 자기검증: naiite_14 로드 → React Flow 노드 수 확인 → 스크린샷.

    P1 성능 계측(spikes/perf_budget.py)을 위해 두 구간의 타임스탬프를 stdout에 출력한다:
    [perf] startup=...s (프로세스 시작~열기 요청 직전) / [perf] open_to_graph=...s (열기 요청~그래프 렌더 완료).
    """
    naiite = "C:/Users/yhkze/Documents/Studio Pro/Songs/NAIITE_EP/naiite_14/naiite_14.song"
    checks = {"done": False}
    open_start = time.perf_counter()
    print(f"[perf] startup={open_start - _PROC_START:.3f}s", flush=True)

    def probe():
        js = """(() => {
          const nodes = document.querySelectorAll('.react-flow__node').length;
          const edges = document.querySelectorAll('.react-flow__edge').length;
          const tabs = document.querySelectorAll('.tab').length;
          return JSON.stringify({nodes, edges, tabs});
        })()"""
        def handle(result):
            data = json.loads(result or "{}")
            # 노드가 엣지보다 먼저 렌더되므로 둘 다 나타난 뒤에만 판정 (미달 시 타임아웃이 실패 처리)
            if data.get("nodes", 0) > 0 and data.get("edges", 0) > 0 and not checks["done"]:
                checks["done"] = True
                print(f"[perf] open_to_graph={time.perf_counter() - open_start:.3f}s", flush=True)
                shot = ROOT / "spikes/out/gui_selftest.png"
                view.grab().save(str(shot))
                # 기대: 입력 3채널 제외 30 노드
                ok = data["nodes"] == 30 and data["edges"] >= 29
                print(f"SELF-TEST {'PASS' if ok else 'FAIL'}: {data} → {shot}")
                app.exit(0 if ok else 1)
        view.page().runJavaScript(js, handle)

    poller = QTimer(window)
    poller.timeout.connect(probe)
    poller.start(500)
    QTimer.singleShot(30000, lambda: (print("SELF-TEST TIMEOUT"), app.exit(2)))
    # 프론트에 ?open= 쿼리로 자동 열기 지시
    url = QUrl.fromLocalFile(str(DIST_INDEX))
    url.setQuery(f"open={naiite}")
    view.load(url)


def main() -> int:
    cleanup_stale_sessions()  # 크래시로 남은 이전 세션의 undo 임시 폴더 정리
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Song Mix GUI — Studio One .song 믹스 분석/전송")
    view = QWebEngineView()
    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    bridge = Bridge(window)
    channel = QWebChannel()
    channel.registerObject("bridge", bridge)
    view.page().setWebChannel(channel)
    window.setCentralWidget(view)
    window.resize(1500, 950)

    if "--self-test" in sys.argv:
        run_self_test(window, view, app)
    else:
        view.load(QUrl.fromLocalFile(str(DIST_INDEX)))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
