import { RotateCcw } from "lucide-react";
import { type FormEvent, useState } from "react";

import { api, type PostingInput, type Verdict } from "../api";
import { useSessionState } from "../useSessionState";
import VerdictCard from "./VerdictCard";
import WebEvidence from "./WebEvidence";

type Props = { onError: (err: unknown) => string };

const EMPTY: PostingInput = { title: "", company_name: "", description: "", company_profile: "", salary_range: "" };

// Example inputs so a first-time visitor sees what the tool does in one click
const SAMPLE_SCAM: PostingInput = {
  title: "Data Entry Work From Home",
  company_name: "Global Typing Solutions",
  description:
    "No interview needed! Earn Rs 30000 per month from home. Pay a registration fee of Rs 1999 to " +
    "confirm your seat. Limited seats, immediate joining. Message HR on WhatsApp 9876543210.",
  company_profile: "",
  salary_range: "",
};

const SAMPLE_REAL: PostingInput = {
  title: "Backend Developer Intern",
  company_name: "Ledgerly",
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
  // The posting exactly as it was checked: the form may be edited afterwards, but a report
  // must carry the original text (the API verifies its hash against the check).
  const [checked, setChecked] = useSessionState<PostingInput | null>("checked-posting", null);
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
      setChecked(form);
    } catch (err) {
      setError(onError(err));
    } finally {
      setBusy(false);
    }
  }

  function load(sample: PostingInput) {
    setForm(sample);
    setResult(null);
    setChecked(null);
    setError(null);
  }

  const isEmpty = Object.values(form).every((v) => !v);
  const clear = () => load(EMPTY);

  return (
    <div className="check-layout">
      <form className="card stack" onSubmit={submit}>
        <div className="card-head">
          <h2>Posting</h2>
          <div className="samples">
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => load(SAMPLE_SCAM)}>
              Sample scam
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => load(SAMPLE_REAL)}>
              Sample real
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={clear}
                    disabled={busy || (isEmpty && !result)} title="Clear the form and the result">
              <RotateCcw size={13} aria-hidden="true" /> Clear
            </button>
          </div>
        </div>

        <label htmlFor="title">Job title</label>
        <input id="title" maxLength={300} value={form.title} onChange={set("title")}
               placeholder="e.g. Data Entry Operator" />

        <label htmlFor="company-name">
          Company name <span className="optional">Optional · used for the web check</span>
        </label>
        <input id="company-name" maxLength={200} value={form.company_name ?? ""} onChange={set("company_name")}
               placeholder="As written in the posting" />

        <label htmlFor="description">Description or recruiter message</label>
        <textarea id="description" required minLength={20} maxLength={10000} rows={8}
                  value={form.description} onChange={set("description")}
                  placeholder="Paste the full posting, WhatsApp message or email here" />
        <small className="counter">{form.description.length.toLocaleString()} / 10,000</small>

        <label htmlFor="company">
          About the company <span className="optional">Optional · improves accuracy</span>
        </label>
        <textarea id="company" maxLength={5000} rows={3} value={form.company_profile}
                  onChange={set("company_profile")} placeholder="Paste the 'About us' section if there is one" />

        <label htmlFor="salary">Salary or stipend <span className="optional">Optional</span></label>
        <input id="salary" maxLength={100} value={form.salary_range} onChange={set("salary_range")}
               placeholder="e.g. 25,000 per month" />

        {error && <p className="error" role="alert">{error}</p>}

        <div className="actions">
          <button type="button" className="btn btn-secondary" onClick={clear} disabled={busy || (isEmpty && !result)}>
            Clear
          </button>
          <button className="btn btn-primary" disabled={busy || form.description.trim().length < 20}>
            {busy ? "Checking…" : "Check posting"}
          </button>
        </div>
      </form>

      <div className="stack-lg">
        {result ? (
          <>
            <VerdictCard v={result} posting={checked} onError={onError} onNewCheck={clear} />
            {checked && <WebEvidence checkId={result.id} posting={checked} onError={onError} />}
          </>
        ) : (
          <section className="card">
            <h2>How a posting is checked</h2>
            <ol className="steps">
              <li>
                <span className="step-n">1</span>
                <div><strong>Red-flag rules</strong><p className="muted small">Fee or deposit requests, WhatsApp or
                  Telegram-only contact, Gmail recruiters, daily-pay promises: patterns common in Indian job scams.</p></div>
              </li>
              <li>
                <span className="step-n">2</span>
                <div><strong>Trained model</strong><p className="muted small">A text classifier trained on 17,880 real and
                  fake postings, retrained with moderator-verified reports.</p></div>
              </li>
              <li>
                <span className="step-n">3</span>
                <div><strong>Web check</strong><p className="muted small">Searches the company, phone number and email
                  for complaints and for an official website. Only those details leave FakeHire.</p></div>
              </li>
              <li>
                <span className="step-n">4</span>
                <div><strong>Community reports</strong><p className="muted small">Reports from users, confirmed by
                  moderators, appear under Scam companies.</p></div>
              </li>
            </ol>
          </section>
        )}
      </div>
    </div>
  );
}
