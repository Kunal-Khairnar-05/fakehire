import { useEffect, useState } from "react";

import { api, type Company, type Trending } from "../api";

// "Known scam companies": search box + this week's trending list.
// Both endpoints are public and read-only, so errors just show an empty state.
export default function ScamCompanies() {
  const [trending, setTrending] = useState<Trending | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Company[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    api.trending().then(setTrending).catch(() => setTrending({ items: [], source: "fallback" }));
  }, []);

  // Search as you type, but wait until typing pauses for 250 ms (DEBOUNCE): typing
  // "global" sends 1 request instead of 6.
  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setResults(null);
      return;
    }
    let current = true; // ignore answers to older searches that arrive late
    setSearching(true);
    const timer = setTimeout(() => {
      api
        .searchCompanies(term)
        .then((r) => current && setResults(r))
        .catch(() => current && setResults([]))
        .finally(() => current && setSearching(false));
    }, 250);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [query]);

  return (
    <section className="glass panel companies">
      <h2>Known scam companies</h2>
      <p className="muted small">Confirmed by moderators from user reports.</p>

      <input type="search" aria-label="Search a company name" placeholder="Search a company name…"
             value={query} onChange={(e) => setQuery(e.target.value)} maxLength={100} />

      {query.trim().length >= 2 ? (
        <>
          <h3>{searching || results === null ? "Searching…" : `Results for “${query.trim()}”`}</h3>
          {results === null ? null : results.length ? (
            <ol className="company-list">
              {results.map((c) => (
                <li key={c.id}>
                  <span className="company-name">{c.name}</span>
                  <span className="pill bad">{c.verified_reports} {c.verified_reports === 1 ? "report" : "reports"}</span>
                </li>
              ))}
            </ol>
          ) : (
            !searching && (
              <p className="muted small">
                No confirmed reports for this name. That isn't proof it's safe; check the posting itself.
              </p>
            )
          )}
        </>
      ) : (
        <>
          <h3>{trending?.source === "fallback" ? "Most reported" : "Trending this week"}</h3>
          {trending === null ? (
            <p className="muted small">Loading…</p>
          ) : trending.items.length ? (
            <ol className="company-list ranked">
              {trending.items.map((c, i) => (
                <li key={c.id}>
                  <span className="rank">{i + 1}</span>
                  <span className="company-name">{c.name}</span>
                  <span className="pill bad">
                    {c.this_week !== null ? `${c.this_week} this week` : `${c.verified_reports} total`}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted small">No confirmed scams this week yet.</p>
          )}
        </>
      )}
    </section>
  );
}
