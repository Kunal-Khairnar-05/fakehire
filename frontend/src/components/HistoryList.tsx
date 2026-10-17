import { useEffect, useState } from "react";

import { api, type CheckSummary } from "../api";
import { useSessionState } from "../useSessionState";
import { bandClass } from "./VerdictCard";

type Props = { onError: (err: unknown) => string };

export default function HistoryList({ onError }: Props) {
  // The last list shown is kept, so reopening this tab shows it instantly while fresh data loads
  const [items, setItems] = useSessionState<CheckSummary[]>("history-items", []);
  const [nextBefore, setNextBefore] = useSessionState<string | null>("history-next", null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Keyset pagination: each page asks for checks older than the last one shown
  async function loadPage(before: string | null) {
    setLoading(true);
    try {
      const page = await api.history(before);
      setItems((prev) => (before ? [...prev, ...page.items] : page.items));
      setNextBefore(page.next_before);
    } catch (err) {
      setError(onError(err));
    } finally {
      setLoading(false);
    }
  }

  // Refresh the first page every time the tab opens (picks up checks you just made)
  useEffect(() => {
    loadPage(null);
  }, []);

  if (!loading && !error && items.length === 0) {
    return (
      <div className="glass panel empty">
        <h2>No checks yet</h2>
        <p className="muted">Postings you check appear here, newest first.</p>
      </div>
    );
  }

  return (
    <section className="glass panel">
      <div className="row-between">
        <h2>My checks</h2>
        {loading && <span className="muted small">Refreshing…</span>}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="history">
        {items.map((c) => (
          <li key={c.id}>
            <span className={`score-chip ${bandClass(c.verdict)}`}>{c.score}</span>
            <div className="history-text">
              <strong>{c.title || "Untitled posting"}</strong>
              <span className="muted">{c.snippet}</span>
            </div>
            <time className="muted" dateTime={c.created_at}>
              {new Date(c.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
            </time>
          </li>
        ))}
      </ul>
      {nextBefore && (
        <button className="btn btn-gray btn-block" disabled={loading} onClick={() => loadPage(nextBefore)}>
          {loading ? "Loading…" : "Load older checks"}
        </button>
      )}
    </section>
  );
}
