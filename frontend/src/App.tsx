import { Building2, ExternalLink, Flag, History, LogOut, ScanSearch, ShieldCheck } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useState } from "react";

import { api, ApiError, tokenStore, type User } from "./api";
import AuthForm from "./components/AuthForm";
import CheckForm from "./components/CheckForm";
import HistoryList from "./components/HistoryList";
import Logo from "./components/Logo";
import ModerationQueue from "./components/ModerationQueue";
import MyReports from "./components/MyReports";
import ScamCompanies from "./components/ScamCompanies";
import { clearSessionState, useSessionState } from "./useSessionState";

type Page = "check" | "history" | "reports" | "companies" | "moderation";

const PAGES: Record<Page, { label: string; icon: ReactNode; title: string; description: string }> = {
  check: {
    label: "Check a posting", icon: <ScanSearch size={16} />, title: "Check a posting",
    description: "Paste a job posting or recruiter message. You get a risk score, the red flags found, and what the web says about whoever posted it.",
  },
  history: {
    label: "History", icon: <History size={16} />, title: "History",
    description: "Every posting you've checked, newest first.",
  },
  reports: {
    label: "My reports", icon: <Flag size={16} />, title: "My reports",
    description: "Scams you reported, and what moderators decided.",
  },
  companies: {
    label: "Scam companies", icon: <Building2 size={16} />, title: "Known scam companies",
    description: "Companies with scam reports confirmed by moderators. Search before you reply to a recruiter.",
  },
  moderation: {
    label: "Moderation", icon: <ShieldCheck size={16} />, title: "Moderation",
    description: "Pending scam reports, oldest first. Confirmed reports feed the trending list and retraining.",
  },
};

// The API is what actually protects moderation (403 for students). Hiding the item only
// avoids showing people something they can't use.
const canModerate = (user: User) => user.role === "moderator" || user.role === "admin";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [page, setPage] = useSessionState<Page>("page", "check");

  const logout = useCallback(() => {
    tokenStore.clear();
    clearSessionState(); // forget form, results and lists for the next person on this browser
    setPage("check");
    setUser(null);
  }, [setPage]);

  // Any 401 anywhere (token expired) sends you back to the sign-in screen
  const handleError = useCallback(
    (err: unknown): string => {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        return "Your session expired. Please sign in again.";
      }
      return err instanceof Error ? err.message : "Something went wrong.";
    },
    [logout],
  );

  // On page load: if a token is saved, ask the API who we are
  useEffect(() => {
    if (!tokenStore.get()) {
      setBooting(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setBooting(false));
  }, []);

  if (booting) return <div className="boot">Loading…</div>;
  if (!user) return <AuthForm onLoggedIn={setUser} />;

  const pages: Page[] = ["check", "history", "reports", "companies", ...(canModerate(user) ? ["moderation" as Page] : [])];
  const active: Page = pages.includes(page) ? page : "check";
  const meta = PAGES[active];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-head">
          <Logo height={24} />
          <span className="chip">{user.role}</span>
        </div>

        <nav className="nav" aria-label="Main">
          {pages.map((p) => (
            <button key={p} aria-current={active === p ? "page" : undefined} onClick={() => setPage(p)}>
              {PAGES[p].icon}
              {PAGES[p].label}
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span className="avatar" aria-hidden="true">{user.email[0].toUpperCase()}</span>
          <div className="who">
            <span className="who-email" title={user.email}>{user.email}</span>
            <span className="muted small">Signed in</span>
          </div>
          <button className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="crumbs">
            <span className="muted">FakeHire</span>
            <span className="sep">/</span>
            <span>{meta.label}</span>
          </div>
          <div className="topbar-actions">
            <a className="btn btn-secondary btn-sm" href="/docs" target="_blank" rel="noopener noreferrer">
              API docs <ExternalLink size={13} />
            </a>
          </div>
        </header>

        <main className="page">
          <div className="page-head">
            <h1>{meta.title}</h1>
            <p>{meta.description}</p>
          </div>

          {active === "check" && <CheckForm onError={handleError} />}
          {active === "history" && <HistoryList onError={handleError} />}
          {active === "reports" && <MyReports onError={handleError} />}
          {active === "companies" && <ScamCompanies />}
          {active === "moderation" && <ModerationQueue onError={handleError} />}

          <p className="foot">
            Scores combine India-specific red-flag rules with a model trained on 17,880 job postings. A verdict is
            guidance, not proof. Never pay to get a job.
          </p>
        </main>
      </div>
    </div>
  );
}
