import { type FormEvent, useState } from "react";

import { api, tokenStore, type User } from "../api";
import banner from "../assets/banner.png";

type Props = { onLoggedIn: (user: User) => void };

export default function AuthForm({ onLoggedIn }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "register") await api.register(email, password);
      const { access_token } = await api.login(email, password);
      tokenStore.set(access_token);
      onLoggedIn(await api.me());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  function switchMode() {
    setMode(mode === "login" ? "register" : "login");
    setError(null);
  }

  return (
    <div className="auth-page">
      <figure className="hero glass">
        <img src={banner} alt="FakeHire: spot fake job postings, save your time" />
      </figure>

      <section className="auth glass">
        <div>
          <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="muted">
            {mode === "login"
              ? "Sign in to check a posting before you reply to a recruiter."
              : "Free. Your checks stay private to your account."}
          </p>
        </div>

        <form onSubmit={submit} className="stack">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" required value={email}
                 placeholder="you@example.com" onChange={(e) => setEmail(e.target.value)} />

          <label htmlFor="password">Password</label>
          <input id="password" type="password" required minLength={8} maxLength={64}
                 autoComplete={mode === "login" ? "current-password" : "new-password"}
                 value={password} onChange={(e) => setPassword(e.target.value)} />
          {mode === "register" && <small className="muted">At least 8 characters.</small>}

          {error && <p className="error" role="alert">{error}</p>}

          <button className="btn btn-filled btn-block btn-large" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="switch">
          {mode === "login" ? "New to FakeHire?" : "Already have an account?"}
          <button className="btn btn-plain" onClick={switchMode}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </section>
    </div>
  );
}
