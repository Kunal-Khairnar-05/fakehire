import { useEffect, useState } from "react";

import { api, type CheckSummary } from "../api";
import { useSessionState } from "../useSessionState";
import { bandClass } from "./VerdictCard";

type Props = { onError: (err: unknown) => string };

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function HistoryList({ onError }: Props) {
  // The last list shown is kept, so reopening this page shows it instantly while fresh data loads
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

  // Refresh the first page every time the page opens (picks up checks you just made)
  useEffect(() => {
    loadPage(null);
  }, []);

  if (!loading && !error && items.length === 0) {
    return (
      <section className="card empty">
        <h2>No checks yet</h2>
        <p className="muted">Postings you check appear here, newest first.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Checks</h2>
        <span className="muted small">{loading ? "Refreshing…" : `${items.length} shown`}</span>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="list with-time">
        {items.map((c) => (
          <li key={c.id}>
            <span className={`score-chip ${bandClass(c.verdict)}`}>{c.score}</span>
            <div className="list-text">
              <strong>{c.title || "Untitled posting"}</strong>
              <span className="muted">{c.snippet}</span>
            </div>
            <time dateTime={c.created_at}>{when(c.created_at)}</time>
          </li>
        ))}
      </ul>
      {nextBefore && (
        <button className="btn btn-secondary btn-block list-more" disabled={loading} onClick={() => loadPage(nextBefore)}>
          {loading ? "Loading…" : "Load older checks"}
        </button>
      )}
    </section>
  );
}
