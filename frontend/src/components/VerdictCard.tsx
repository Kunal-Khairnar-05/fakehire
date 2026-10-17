import { AlertTriangle } from "lucide-react";

import type { PostingInput, Verdict } from "../api";
import ReportScam from "./ReportScam";

// Same bands as ml/fakehire_ml/scoring.py: 0-39 Safe, 40-69 Suspicious, 70-100 Likely scam
export function bandClass(verdict: Verdict["verdict"]): string {
  return verdict === "Likely scam" ? "bad" : verdict === "Suspicious" ? "warn" : "ok";
}

const ADVICE: Record<Verdict["verdict"], string> = {
  "Likely scam": "Do not pay anything or share documents. Real employers never charge candidates.",
  Suspicious: "Verify the company independently before you share personal details.",
  Safe: "No common scam patterns found. Still verify the company before sharing documents.",
};

type Props = { v: Verdict; posting: PostingInput | null; onError: (err: unknown) => string };

export default function VerdictCard({ v, posting, onError }: Props) {
  const band = bandClass(v.verdict);

  return (
    <section className={`card verdict ${band}`} aria-live="polite">
      <div className="verdict-head">
        <div>
          <h3>Risk score</h3>
          <div className="score" aria-label={`Risk score ${v.score} out of 100`}>
            <span className="score-num">{v.score}</span>
            <span className="score-max">/ 100</span>
          </div>
        </div>
        <span className={`pill ${band}`}>{v.verdict}</span>
      </div>

      {/* Bands marked at 40 and 70 */}
      <div className="meter" role="img" aria-label={`Score ${v.score}: ${v.verdict}`}>
        <div className="meter-fill" style={{ width: `${v.score}%` }} />
        <span className="tick" style={{ left: "40%" }} />
        <span className="tick" style={{ left: "70%" }} />
      </div>
      <div className="meter-labels"><span>Safe</span><span>Suspicious</span><span>Likely scam</span></div>

      <p className="advice">{ADVICE[v.verdict]}</p>
      {v.note && <p className="note">{v.note}</p>}

      <h3 className="section-title">Red flags · {v.flags.length}</h3>
      {v.flags.length ? (
        <ul className="flags">
          {v.flags.map((f) => (
            <li key={f.rule}>
              <AlertTriangle size={14} aria-hidden="true" />
              <span>{f.message}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted small" style={{ marginTop: 8 }}>
          None of the rules matched. The score comes from the model alone.
        </p>
      )}

      <div className="meta">
        <span className="tag">model {v.model_version}</span>
        <span className="tag">{v.cache_hit ? "cache hit" : "scored"}</span>
        <span className="tag">{v.took_ms} ms</span>
        <span className="tag">check #{v.id}</span>
      </div>

      <ReportScam checkId={v.id} posting={posting} onError={onError} />
    </section>
  );
}
