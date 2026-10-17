import { useEffect, useState } from "react";

import { api, type Report, type ReportStatus } from "../api";

type Props = { onError: (err: unknown) => string };

const STATUS: Record<ReportStatus, { label: string; band: string }> = {
  pending: { label: "Under review", band: "neutral" },
  verified: { label: "Confirmed scam", band: "bad" },
  rejected: { label: "Not confirmed", band: "ok" },
};

export default function MyReports({ onError }: Props) {
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.myReports().then(setReports).catch((err) => setError(onError(err)));
  }, [onError]);

  if (reports !== null && reports.length === 0 && !error) {
    return (
      <section className="card empty">
        <h2>No reports yet</h2>
        <p className="muted">After checking a posting, use "Report as scam" on the result. You'll follow its review here.</p>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Reports</h2>
        <span className="muted small">{reports === null ? "Loading…" : `${reports.length} total`}</span>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="list two-col">
        {(reports ?? []).map((r) => (
          <li key={r.id}>
            <div className="list-text">
              <strong>{r.company_name}</strong>
              <span className="muted">{r.reason || "No reason given"}</span>
            </div>
            <span className={`pill ${STATUS[r.status].band}`}>{STATUS[r.status].label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
