import { useEffect, useMemo, useState } from "react";
import { api } from "./bridge";
import type { ChannelInfo, InsertInfo, InterpretResult, ParamValue } from "./types";

type Props = {
  songPath: string;
  channel: ChannelInfo;
  onClose: () => void;
};

type SortKey = "name" | "value";

export function DetailPanel({ songPath, channel, onClose }: Props) {
  const [selectedInsert, setSelectedInsert] = useState<InsertInfo | null>(null);
  const [result, setResult] = useState<InterpretResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [paramFilter, setParamFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortAsc, setSortAsc] = useState(true);

  useEffect(() => {
    setSelectedInsert(null);
    setResult(null);
  }, [channel.uid]);

  useEffect(() => {
    setParamFilter("");
    setSortKey("name");
    setSortAsc(true);
    if (!selectedInsert?.presetPath) return;
    let cancelled = false;
    setIsLoading(true);
    setResult(null);
    api.interpretPreset(songPath, selectedInsert.presetPath)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch((e: Error) => {
        if (!cancelled) {
          setResult({ status: "error", pluginName: selectedInsert.pluginName,
                      params: [], message: e.message });
        }
      })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, [songPath, selectedInsert]);

  const visibleParams = useMemo(() => {
    const params: ParamValue[] = result?.params ?? [];
    const q = paramFilter.trim().toLowerCase();
    const filtered = q ? params.filter((p) => p.name.toLowerCase().includes(q)) : params;
    const dir = sortAsc ? 1 : -1;
    return [...filtered].sort((a, b) => a[sortKey].localeCompare(b[sortKey]) * dir);
  }, [result, paramFilter, sortKey, sortAsc]);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc((asc) => !asc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const sortIndicator = (key: SortKey) => (key === sortKey ? (sortAsc ? " ▲" : " ▼") : "");

  return (
    <aside className="detail-panel">
      <header>
        <h2>{channel.label}</h2>
        <span className="detail-kind">{channel.tag}</span>
        <button type="button" className="close-btn" onClick={onClose}>×</button>
      </header>
      <p className="detail-route">
        출력 → {channel.destinationName ?? "(없음)"}
        {channel.sends.map((s) => (
          <span key={s.destinationUid} className="send-tag">send→{s.destinationName}</span>
        ))}
      </p>
      <h3>인서트 체인 ({channel.inserts.length})</h3>
      <ol className="insert-list">
        {channel.inserts.map((ins) => (
          <li key={ins.uid}>
            <button
              type="button"
              className={selectedInsert?.uid === ins.uid ? "insert-item selected" : "insert-item"}
              onClick={() => setSelectedInsert(ins)}
            >
              <span className="insert-order">{ins.order + 1}</span>
              <span className="insert-name">{ins.pluginName}</span>
              <span className="insert-preset">{ins.deviceName}</span>
            </button>
          </li>
        ))}
      </ol>
      {isLoading && <p className="param-loading">파라미터 해석 중…</p>}
      {result && (
        <section className="param-section">
          <h3>
            {result.pluginName}
            {result.status !== "ok" && (
              <span className="badge-uninterpretable">해석 불가 (복사 가능)</span>
            )}
          </h3>
          {result.status === "ok" && (
            <>
              <input
                type="text"
                className="param-filter"
                placeholder="파라미터 검색…"
                value={paramFilter}
                onChange={(e) => setParamFilter(e.target.value)}
              />
              <table className="param-table">
                <thead>
                  <tr>
                    <th className="sortable" onClick={() => handleSort("name")}>
                      파라미터{sortIndicator("name")}
                    </th>
                    <th className="sortable" onClick={() => handleSort("value")}>
                      값{sortIndicator("value")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleParams.map((p) => (
                    <tr key={p.name}><td>{p.name}</td><td>{p.value}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {result.message && <p className="param-message">{result.message}</p>}
        </section>
      )}
    </aside>
  );
}
