import { useEffect, useState } from "react";

import { api, type Evidence, type PostingInput, type WebCheck } from "../api";
import { useSessionState } from "../useSessionState";

type Props = { checkId: number; posting: PostingInput; onError: (err: unknown) => string };

const STATUS: Record<WebCheck["status"], { label: string; band: string }> = {
  impersonation_risk: { label: "Possible impersonation", band: "bad" },
  complaints_found: { label: "Scam reports found online", band: "bad" },
  no_reports_found: { label: "No reports found online", band: "neutral" },
  nothing_to_search: { label: "Nothing to search", band: "neutral" },
  unavailable: { label: "Web check unavailable", band: "neutral" },
};

const KIND: Record<Evidence["kind"], string> = { company: "Company", phone: "Phone", email: "Email" };

// Loads AFTER the verdict, so a slow web search never delays the main result.
// Kept per check in sessionStorage, so switching tabs doesn't search (and spend quota) again.
export default function WebEvidence({ checkId, posting, onError }: Props) {
  const [saved, setSaved] = useSessionState<{ checkId: number; result: WebCheck } | null>("web-check", null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const result = saved?.checkId === checkId ? saved.result : null;

  useEffect(() => {
    if (result) return;
    let current = true;
    setLoading(true);
    setError(null);
    api
      .webCheck(posting)
      .then((r) => current && setSaved({ checkId, result: r }))
      .catch((err) => current && setError(onError(err)))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [checkId]);

  return (
    <section className="card web" aria-live="polite" aria-busy={loading}>
      <div className="row-between">
        <h2>Web check</h2>
        {result && <span className={`pill ${STATUS[result.status].band}`}>{STATUS[result.status].label}</span>}
      </div>

      {loading && (
        <div aria-label="Searching the web">
          <p className="muted small" style={{ marginBottom: 10 }}>Searching for the company, phone number and email…</p>
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}

      {result && (
        <>
          <p className="small">{result.summary}</p>

          {result.official_site && (
            <a className="evidence official" href={result.official_site.url} target="_blank"
               rel="noopener noreferrer nofollow">
              <span className="tag">Possible official site</span>
              <strong>{result.official_site.domain}</strong>
              <span className="muted small">{result.official_site.title}</span>
            </a>
          )}

          {result.evidence.length > 0 && (
            <ul className="evidence-list">
              {result.evidence.map((e) => (
                <li key={e.url}>
                  {/* Plain text + a normal link only: search results are untrusted content */}
                  <a className="evidence" href={e.url} target="_blank" rel="noopener noreferrer nofollow">
                    <span className="evidence-head">
                      <span className={`pill ${e.complaint ? "bad" : e.official ? "ok" : "neutral"}`}>
                        {e.complaint ? "Complaint" : e.official ? "Company's own page" : "Mention"}
                      </span>
                      <span className="muted small">{KIND[e.kind]} · {e.domain}</span>
                    </span>
                    <strong>{e.title}</strong>
                    <span className="muted small">{e.snippet}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}

          <p className="muted small web-foot">
            Searched: {[result.identifiers.company, ...result.identifiers.phones, ...result.identifiers.emails]
              .filter(Boolean).join(" · ") || "nothing"}
            {" · "}only these details were sent to the search provider, not the posting.
          </p>
        </>
      )}
    </section>
  );
}
