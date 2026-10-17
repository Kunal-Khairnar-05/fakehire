import { type FormEvent, useState } from "react";

import { api, type PostingInput, type Verdict } from "../api";
import { useSessionState } from "../useSessionState";
import ScamCompanies from "./ScamCompanies";
import VerdictCard from "./VerdictCard";

type Props = { onError: (err: unknown) => string };

const EMPTY: PostingInput = { title: "", description: "", company_profile: "", salary_range: "" };

// Example inputs so a first-time visitor sees what the tool does in one click
const SAMPLE_SCAM: PostingInput = {
  title: "Data Entry Work From Home",
  description:
    "No interview needed! Earn Rs 30000 per month from home. Pay a registration fee of Rs 1999 to " +
    "confirm your seat. Limited seats, immediate joining. Message HR on WhatsApp 9876543210.",
  company_profile: "",
  salary_range: "",
};

const SAMPLE_REAL: PostingInput = {
  title: "Backend Developer Intern",
  description:
    "We are looking for a backend intern to join our payments team for 6 months. You will build and test " +
    "REST APIs in Python, write SQL against PostgreSQL, and take part in code reviews. Selection process: " +
    "an online coding test followed by two technical interviews. Stipend 25,000 per month, on site in Pune.",
  company_profile:
    "Ledgerly builds accounting software used by over 2,000 small businesses across India. Founded in 2016, " +
    "we are a team of 120 engineers, designers and accountants.",
  salary_range: "",
};

export default function CheckForm({ onError }: Props) {
  // Kept in sessionStorage, so switching to "My checks" and back doesn't lose anything
  const [form, setForm] = useSessionState<PostingInput>("check-form", EMPTY);
  const [result, setResult] = useSessionState<Verdict | null>("check-result", null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (field: keyof PostingInput) => (e: { target: { value: string } }) =>
    setForm({ ...form, [field]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      setResult(await api.check(form));
    } catch (err) {
      setError(onError(err));
    } finally {
      setBusy(false);
    }
  }

  function load(sample: PostingInput) {
    setForm(sample);
    setResult(null);
    setError(null);
  }

  return (
    <div className="check-layout">
      <form className="glass panel stack" onSubmit={submit}>
        <div className="row-between">
          <h2>Paste the posting</h2>
          <div className="samples">
            <button type="button" className="btn btn-tinted btn-small" onClick={() => load(SAMPLE_SCAM)}>
              Sample scam
            </button>
            <button type="button" className="btn btn-tinted btn-small" onClick={() => load(SAMPLE_REAL)}>
              Sample real
            </button>
          </div>
        </div>

        <label htmlFor="title">Job title</label>
        <input id="title" maxLength={300} value={form.title} onChange={set("title")}
               placeholder="e.g. Data Entry Operator" />

        <label htmlFor="description">Description or recruiter message</label>
        <textarea id="description" required minLength={20} maxLength={10000} rows={7}
                  value={form.description} onChange={set("description")}
                  placeholder="Paste the full posting, WhatsApp message or email here" />
        <small className="muted counter">{form.description.length.toLocaleString()} / 10,000</small>

        <label htmlFor="company">
          About the company <span className="muted optional">Optional, improves accuracy</span>
        </label>
        <textarea id="company" maxLength={5000} rows={3} value={form.company_profile}
                  onChange={set("company_profile")} placeholder="Paste the 'About us' section if there is one" />

        <label htmlFor="salary">Salary or stipend <span className="muted optional">Optional</span></label>
        <input id="salary" maxLength={100} value={form.salary_range} onChange={set("salary_range")}
               placeholder="e.g. 25,000 per month" />

        {error && <p className="error" role="alert">{error}</p>}

        <div className="actions">
          <button type="button" className="btn btn-gray" onClick={() => load(EMPTY)}
                  disabled={busy || (!form.title && !form.description && !form.company_profile && !form.salary_range)}>
            Clear
          </button>
          <button className="btn btn-filled btn-large" disabled={busy || form.description.trim().length < 20}>
            {busy ? "Checking…" : "Check this posting"}
          </button>
        </div>
      </form>

      <div className="result-col stack-lg">
        {result ? (
          <VerdictCard v={result} onError={onError} />
        ) : (
          <div className="glass panel empty">
            <div className="dial placeholder" aria-hidden="true">
              <div className="dial-inner"><span className="dial-num">?</span></div>
            </div>
            <h2>Your result appears here</h2>
            <p className="muted">
              You get a 0–100 risk score and the specific red flags found, such as a fee request or a recruiter
              using a Gmail address. Try a sample to see how it works.
            </p>
          </div>
        )}
        <ScamCompanies />
      </div>
    </div>
  );
}
