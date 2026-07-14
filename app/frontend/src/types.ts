export interface InsertInfo {
  slot: string;
  order: number;
  uid: string;
  classId: string;
  deviceName: string;
  pluginName: string;
  subCategory: string;
  presetPath: string | null;
}

export interface SendInfo {
  destinationUid: string;
  destinationName: string;
}

export interface ChannelInfo {
  tag: string;
  group: string;
  name: string;
  label: string;
  uid: string;
  kind: string;
  speakerType: string | null;
  destinationUid: string | null;
  destinationName: string | null;
  inserts: InsertInfo[];
  sends: SendInfo[];
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: "output" | "send";
}

export interface SongModel {
  channels: ChannelInfo[];
  graph: {
    nodes: { uid: string; label: string; kind: string; group: string; insertCount: number }[];
    edges: GraphEdge[];
  };
}

export interface SongDoc {
  id: string;
  path: string;
  fileName: string;
  model: SongModel;
}

export interface ParamValue {
  name: string;
  value: string;
}

export interface InterpretResult {
  status: "ok" | "uninterpretable" | "error";
  pluginName: string;
  params: ParamValue[];
  message?: string;
}

export interface TransferResponse {
  status: "ok" | "conflict" | "error";
  conflicts?: { label: string; kind: string }[];
  message?: string;
  savedBackup?: string;
  droppedSends?: string[];
  newModel?: SongModel;
}

export interface PrewarmStatus {
  done: number;
  total: number;
}

export interface UndoResponse {
  status: "ok" | "error";
  model?: SongModel;
  message?: string;
}

export interface CompareParamDiff {
  name: string;
  leftValue: string | null;
  rightValue: string | null;
}

export interface CompareRow {
  slot: number;
  rowType: "match" | "value-diff" | "chain-mismatch";
  leftPlugin: string | null;
  rightPlugin: string | null;
  interpretable: boolean;
  diffs: CompareParamDiff[];
}

export interface CompareResponse {
  status: "ok" | "error";
  leftLabel?: string;
  rightLabel?: string;
  rows?: CompareRow[];
  message?: string;
}

export interface DragPayload {
  docId: string;
  srcPath: string;
  rootUid: string;
  label: string;
  mode: "subtree" | "chain" | "track";
}

export interface BulkPlanRow {
  label: string;
  // "bus-subtree" | "chain-replace" | "excluded" | "no-match" | "not-selected"
  // | "unknown-bus-label"
  action: string;
}

export interface BulkPreviewEntry {
  path: string;
  status: "ok" | "error";
  plans?: BulkPlanRow[];
  warnings?: string[];
  message?: string;
}

export interface BulkPreviewResponse {
  status: "ok" | "error";
  busRoots?: string[];
  previews?: BulkPreviewEntry[];
  message?: string;
}

export interface BulkApplyOutcome {
  path: string;
  status: "ok" | "error";
  savedBackup?: string;
  warnings?: string[];
  message?: string;
}

export interface BulkApplyResponse {
  status: "ok" | "error";
  outcomes?: BulkApplyOutcome[];
  message?: string;
}

export interface BusTreeNode {
  label: string;
  depth: number;
  parentLabel: string | null;
}

export interface DescribeSourceResponse {
  status: "ok" | "error";
  trackLabels?: string[];
  busTree?: BusTreeNode[];
  message?: string;
}

export interface PickDirectoryResponse {
  status: "ok" | "cancelled" | "error";
  path?: string;
}

export interface ScanSongEntry {
  path: string;
  status: "ok" | "error";
  trackLabels?: string[];
  busCount?: number;
  message?: string;
}

export interface ScanSongDirectoryResponse {
  status: "ok" | "error";
  entries?: ScanSongEntry[];
  message?: string;
}

export interface PickFilesResponse {
  status: "ok" | "cancelled" | "error";
  paths?: string[];
  message?: string;
}
