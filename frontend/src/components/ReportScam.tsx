import { type FormEvent, useState } from "react";

import { api, ApiError, type PostingInput } from "../api";
import { useSessionState } from "../useSessionState";

type Props = { checkId: number; posting: PostingInput | null; onError: (err: unknown) => string };

// Inline "Report as scam" form at the bottom of a result card
export default function ReportScam({ checkId, posting, onError }: Props) {
  // Remember which checks were reported in this session, so the form doesn't come back
  const [reported, setReported] = useSessionState<number[]>("reported-checks", []);
  const [open, setOpen] = useState(false);
  const [company, setCompany] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const markReported = () => setReported((ids) => [...ids, checkId]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.report(checkId, company, reason, posting);
      markReported();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) markReported(); // already reported earlier
      else setError(onError(err));
    } finally {
      setBusy(false);
    }
  }

  if (reported.includes(checkId)) {
    return (
      <p className="success" role="status">
        Thanks for reporting. A moderator will review it; you can follow it under My checks.
      </p>
    );
  }

  if (!open) {
    return (
      <div className="report-cta">
        <span className="muted small">Know this is a scam? Reporting it helps the next person.</span>
        <button className="btn btn-tinted btn-small" onClick={() => setOpen(true)}>Report as scam</button>
      </div>
    );
  }

  return (
    <form className="report-box stack" onSubmit={submit}>
      <label htmlFor="report-company">Company name used in the posting</label>
      <input id="report-company" required minLength={2} maxLength={200} value={company}
             onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Global Typing Solutions" />

      <label htmlFor="report-reason">What happened? <span className="muted optional">Optional</span></label>
      <textarea id="report-reason" rows={2} maxLength={1000} value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Asked for a Rs 499 deposit on Telegram" />

      {!posting && (
        <small className="muted">
          This result is from an earlier session, so the posting text can't be attached and the report
          won't help retrain the model. Check the posting again first if you can.
        </small>
      )}
      {error && <p className="error" role="alert">{error}</p>}

      <div className="actions">
        <button type="button" className="btn btn-gray btn-small" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </button>
        <button className="btn btn-filled btn-small" disabled={busy || company.trim().length < 2}>
          {busy ? "Sending…" : "Send report"}
        </button>
      </div>
    </form>
  );
}
