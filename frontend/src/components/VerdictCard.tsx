import type { CSSProperties } from "react";

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
    // key={v.id}: a new result remounts the card, so the dial animates from 0 again
    <section key={v.id} className={`glass panel verdict ${band}`} aria-live="polite">
      <div className="verdict-head">
        {/* Neumorphic dial: the ring fills to the score (conic-gradient driven by --p) */}
        <div className="dial" style={{ "--p": v.score } as CSSProperties}
             role="img" aria-label={`Risk score ${v.score} out of 100`}>
          <div className="dial-inner">
            <span className="dial-num">{v.score}</span>
            <span className="dial-max">of 100</span>
          </div>
        </div>
        <div className="verdict-text">
          <span className={`pill ${band}`}>{v.verdict}</span>
          <p>{ADVICE[v.verdict]}</p>
        </div>
      </div>

      {v.note && <p className="note">{v.note}</p>}

      <h3>Red flags found</h3>
      {v.flags.length ? (
        <ul className="flags">
          {v.flags.map((f) => <li key={f.rule}>{f.message}</li>)}
        </ul>
      ) : (
        <p className="muted">None of our rules matched. The score comes from the model alone.</p>
      )}

      <div className="meta">
        <span className="tag">Model {v.model_version}</span>
        <span className="tag">{v.cache_hit ? "Cached answer" : "Freshly scored"}</span>
        <span className="tag">{v.took_ms} ms</span>
      </div>

      <ReportScam checkId={v.id} posting={posting} onError={onError} />
    </section>
  );
}
