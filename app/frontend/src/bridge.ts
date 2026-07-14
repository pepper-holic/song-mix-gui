import type { BulkApplyResponse, BulkPreviewResponse, CompareResponse, DescribeSourceResponse,
             InterpretResult, PickDirectoryResponse, PickFilesResponse, PrewarmStatus,
             ScanSongDirectoryResponse, SongModel, TransferResponse,
             UndoResponse } from "./types";

/** QWebChannel(Qt 내장) 브리지. 브라우저 dev 모드에서는 명시적 에러 반환. */
interface QtBridge {
  open_song_dialog: (cb: (json: string) => void) => void;
  open_song: (path: string, cb: (json: string) => void) => void;
  transfer_subtree: (srcPath: string, rootUid: string, dstPath: string,
                     confirmed: boolean, preserveSends: boolean,
                     cb: (json: string) => void) => void;
  replace_chain: (srcPath: string, srcUid: string, dstPath: string,
                  dstUid: string, cb: (json: string) => void) => void;
  interpret_preset: (songPath: string, presetEntry: string,
                     cb: (json: string) => void) => void;
  undo_last: (path: string, cb: (json: string) => void) => void;
  get_recent: (cb: (json: string) => void) => void;
  compare_channels: (leftPath: string, leftUid: string, rightPath: string,
                     rightUid: string, cb: (json: string) => void) => void;
  hint_visible: (songPath: string, uidsJson: string, cb: (json: string) => void) => void;
  prewarm_status: (cb: (json: string) => void) => void;
  transfer_track: (srcPath: string, channelUid: string, dstPath: string,
                   includeEvents: boolean, cb: (json: string) => void) => void;
  pick_song_files_dialog: (cb: (json: string) => void) => void;
  describe_source: (srcPath: string, cb: (json: string) => void) => void;
  pick_song_directory_dialog: (cb: (json: string) => void) => void;
  scan_song_directory: (dirPath: string, cb: (json: string) => void) => void;
  set_window_title: (title: string) => void;
  preview_bulk_recipe: (srcPath: string, dstPathsJson: string, excludeLabelsJson: string,
                        includeBusLabelsJson: string, cb: (json: string) => void) => void;
  apply_bulk_recipe: (srcPath: string, dstPathsJson: string, excludeLabelsJson: string,
                      includeBusLabelsJson: string, allowNestedExclusionWarnings: boolean,
                      cb: (json: string) => void) => void;
}

declare global {
  interface Window {
    qt?: { webChannelTransport: unknown };
    QWebChannel?: new (transport: unknown, cb: (ch: { objects: { bridge: QtBridge } }) => void) => void;
  }
}

let bridgePromise: Promise<QtBridge> | null = null;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`script load failed: ${src}`));
    document.head.appendChild(s);
  });
}

export function getBridge(): Promise<QtBridge> {
  if (!bridgePromise) {
    bridgePromise = (async () => {
      if (!window.qt) throw new Error("Qt 환경이 아닙니다 (dev 브라우저 모드)");
      if (!window.QWebChannel) {
        await loadScript("qrc:///qtwebchannel/qwebchannel.js");
      }
      return new Promise<QtBridge>((resolve) => {
        new window.QWebChannel!(window.qt!.webChannelTransport, (ch) =>
          resolve(ch.objects.bridge));
      });
    })();
  }
  return bridgePromise;
}

function call<T>(fn: (b: QtBridge, cb: (json: string) => void) => void): Promise<T> {
  return getBridge().then(
    (b) => new Promise<T>((resolve) => fn(b, (json) => resolve(JSON.parse(json)))));
}

export interface OpenResult {
  status: "ok" | "cancelled" | "error";
  path?: string;
  model?: SongModel;
  message?: string;
}

export const api = {
  openSongDialog: () => call<OpenResult>((b, cb) => b.open_song_dialog(cb)),
  openSong: (path: string) => call<OpenResult>((b, cb) => b.open_song(path, cb)),
  transferSubtree: (srcPath: string, rootUid: string, dstPath: string, confirmed: boolean,
                    preserveSends = false) =>
    call<TransferResponse>((b, cb) =>
      b.transfer_subtree(srcPath, rootUid, dstPath, confirmed, preserveSends, cb)),
  replaceChain: (srcPath: string, srcUid: string, dstPath: string, dstUid: string) =>
    call<TransferResponse>((b, cb) =>
      b.replace_chain(srcPath, srcUid, dstPath, dstUid, cb)),
  interpretPreset: (songPath: string, presetEntry: string) =>
    call<InterpretResult>((b, cb) => b.interpret_preset(songPath, presetEntry, cb)),
  undoLast: (path: string) =>
    call<UndoResponse>((b, cb) => b.undo_last(path, cb)),
  getRecent: () => call<string[]>((b, cb) => b.get_recent(cb)),
  compareChannels: (leftPath: string, leftUid: string, rightPath: string, rightUid: string) =>
    call<CompareResponse>((b, cb) =>
      b.compare_channels(leftPath, leftUid, rightPath, rightUid, cb)),
  hintVisible: (songPath: string, uids: string[]) =>
    call<{ status: string }>((b, cb) =>
      b.hint_visible(songPath, JSON.stringify(uids), cb)),
  prewarmStatus: () => call<PrewarmStatus>((b, cb) => b.prewarm_status(cb)),
  transferTrack: (srcPath: string, channelUid: string, dstPath: string, includeEvents: boolean) =>
    call<TransferResponse>((b, cb) =>
      b.transfer_track(srcPath, channelUid, dstPath, includeEvents, cb)),
  pickSongFiles: () => call<PickFilesResponse>((b, cb) => b.pick_song_files_dialog(cb)),
  describeSource: (srcPath: string) =>
    call<DescribeSourceResponse>((b, cb) => b.describe_source(srcPath, cb)),
  pickSongDirectory: () =>
    call<PickDirectoryResponse>((b, cb) => b.pick_song_directory_dialog(cb)),
  scanSongDirectory: (dirPath: string) =>
    call<ScanSongDirectoryResponse>((b, cb) => b.scan_song_directory(dirPath, cb)),
  setWindowTitle: (title: string) => {
    void getBridge().then((b) => b.set_window_title(title)).catch(() => {
      // Qt 브리지가 없는 dev 브라우저 모드 — 조용히 무시
    });
  },
  previewBulkRecipe: (srcPath: string, dstPaths: string[], excludeLabels: string[],
                     includeBusLabels: string[] | null) =>
    call<BulkPreviewResponse>((b, cb) =>
      b.preview_bulk_recipe(srcPath, JSON.stringify(dstPaths), JSON.stringify(excludeLabels),
                            JSON.stringify(includeBusLabels), cb)),
  applyBulkRecipe: (srcPath: string, dstPaths: string[], excludeLabels: string[],
                    includeBusLabels: string[] | null, allowNestedExclusionWarnings: boolean) =>
    call<BulkApplyResponse>((b, cb) =>
      b.apply_bulk_recipe(srcPath, JSON.stringify(dstPaths), JSON.stringify(excludeLabels),
                          JSON.stringify(includeBusLabels), allowNestedExclusionWarnings, cb)),
};
