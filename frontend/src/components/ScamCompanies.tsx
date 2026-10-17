import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type Company, type Trending } from "../api";

const reportsLabel = (n: number) => `${n} ${n === 1 ? "report" : "reports"}`;

// Search box + this week's trending list. Both endpoints are public and read-only,
// so errors just show an empty state.
export default function ScamCompanies() {
  const [trending, setTrending] = useState<Trending | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Company[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    api.trending().then(setTrending).catch(() => setTrending({ items: [], source: "fallback" }));
  }, []);

  // Search as you type, but only once typing pauses for 250 ms (DEBOUNCE)
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

  const searchingNow = query.trim().length >= 2;

  return (
    <div className="stack-lg">
      <section className="card companies">
        <div className="card-head"><h2>Search</h2></div>
        <div style={{ position: "relative" }}>
          <Search size={15} className="muted" style={{ position: "absolute", left: 12, top: 11 }} aria-hidden="true" />
          <input type="search" aria-label="Search a company name" placeholder="Search a company name…"
                 value={query} onChange={(e) => setQuery(e.target.value)} maxLength={100}
                 style={{ paddingLeft: 34 }} />
        </div>
        {searchingNow && (
          searching || results === null ? (
            <p className="muted small">Searching…</p>
          ) : results.length ? (
            <ul className="list two-col">
              {results.map((c) => (
                <li key={c.id}>
                  <span className="company-name">{c.name}</span>
                  <span className="pill bad">{reportsLabel(c.verified_reports)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted small">
              No confirmed reports for “{query.trim()}”. That isn't proof it's safe; check the posting itself.
            </p>
          )
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>{trending?.source === "fallback" ? "Most reported" : "Trending this week"}</h2>
          <span className="tag">{trending?.source === "fallback" ? "database" : "live"}</span>
        </div>
        {trending === null ? (
          <p className="muted small" style={{ marginTop: 12 }}>Loading…</p>
        ) : trending.items.length ? (
          <ul className="list">
            {trending.items.map((c, i) => (
              <li key={c.id}>
                <span className="rank">{i + 1}</span>
                <span className="company-name">{c.name}</span>
                <span className="pill bad">
                  {c.this_week !== null ? `${c.this_week} this week` : reportsLabel(c.verified_reports)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small" style={{ marginTop: 12 }}>No confirmed scams this week yet.</p>
        )}
      </section>
    </div>
  );
}
