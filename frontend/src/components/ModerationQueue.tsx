import { useEffect, useState } from "react";

import { api, ApiError, type QueueItem } from "../api";
import { useSessionState } from "../useSessionState";
import { bandClass } from "./VerdictCard";

type Props = { onError: (err: unknown) => string };

// Moderators only: pending reports, oldest first. Decide each one: confirm or reject.
export default function ModerationQueue({ onError }: Props) {
  const [items, setItems] = useSessionState<QueueItem[]>("queue-items", []);
  const [nextAfter, setNextAfter] = useSessionState<string | null>("queue-next", null);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadPage(after: string | null) {
    setLoading(true);
    try {
      const page = await api.queue(after);
      setItems((prev) => (after ? [...prev, ...page.items] : page.items));
      setNextAfter(page.next_after);
    } catch (err) {
      setError(onError(err));
    } finally {
      setLoading(false);
    }
  }

  // Fresh queue every time the tab opens
  useEffect(() => {
    loadPage(null);
  }, []);

  async function decide(item: QueueItem, status: "verified" | "rejected") {
    setDeciding(item.id);
    setError(null);
    setNotice(null);
    try {
      await api.review(item.id, status);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      setNotice(`${item.company_name}: ${status === "verified" ? "confirmed as a scam" : "marked as not a scam"}.`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Another moderator got there first (the API locks the row, so only one review counts)
        setItems((prev) => prev.filter((i) => i.id !== item.id));
        setNotice(`${item.company_name} was already reviewed by another moderator.`);
      } else {
        setError(onError(err));
      }
    } finally {
      setDeciding(null);
    }
  }

  if (!loading && !error && items.length === 0) {
    return (
      <div className="glass panel empty">
        <h2>The queue is clear</h2>
        <p className="muted">{notice ?? "New scam reports from users will appear here, oldest first."}</p>
      </div>
    );
  }

  return (
    <section className="glass panel">
      <div className="row-between">
        <h2>Reports to review</h2>
        {loading && <span className="muted small">Refreshing…</span>}
      </div>
      {notice && <p className="success" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      <ul className="queue">
        {items.map((item) => (
          <li key={item.id} className="queue-item">
            <div className="queue-head">
              <span className={`score-chip ${bandClass(item.verdict)}`} title="Score when it was checked">
                {item.score}
              </span>
              <div className="history-text">
                <strong>{item.company_name}</strong>
                <span className="muted">
                  Reported {new Date(item.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </span>
              </div>
            </div>

            {item.reason && <p className="queue-reason">“{item.reason}”</p>}

            <div className="queue-posting">
              <strong>{item.title || "Untitled posting"}</strong>
              <p className="muted">{item.snippet}</p>
            </div>

            <div className="actions">
              <button className="btn btn-gray btn-small" disabled={deciding !== null}
                      onClick={() => decide(item, "rejected")}>
                Not a scam
              </button>
              <button className="btn btn-destructive btn-small" disabled={deciding !== null}
                      onClick={() => decide(item, "verified")}>
                {deciding === item.id ? "Saving…" : "Confirm scam"}
              </button>
            </div>
          </li>
        ))}
      </ul>

      {nextAfter && (
        <button className="btn btn-gray btn-block" disabled={loading} onClick={() => loadPage(nextAfter)}>
          {loading ? "Loading…" : "Load more"}
        </button>
      )}
    </section>
  );
}
