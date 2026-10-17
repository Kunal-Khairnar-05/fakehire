import { useEffect, useState } from "react";

import { api, type Report, type ReportStatus } from "../api";

type Props = { onError: (err: unknown) => string };

const STATUS: Record<ReportStatus, { label: string; band: string }> = {
  pending: { label: "Under review", band: "neutral" },
  verified: { label: "Confirmed scam", band: "bad" },
  rejected: { label: "Not confirmed", band: "ok" },
};

// Your reports and what moderators decided. Hidden entirely until you've reported something.
export default function MyReports({ onError }: Props) {
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.myReports().then(setReports).catch((err) => setError(onError(err)));
  }, [onError]);

  if (!error && reports.length === 0) return null;

  return (
    <section className="glass panel">
      <h2>My reports</h2>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="report-list">
        {reports.map((r) => (
          <li key={r.id}>
            <div className="history-text">
              <strong>{r.company_name}</strong>
              {r.reason && <span className="muted">{r.reason}</span>}
            </div>
            <span className={`pill ${STATUS[r.status].band}`}>{STATUS[r.status].label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
