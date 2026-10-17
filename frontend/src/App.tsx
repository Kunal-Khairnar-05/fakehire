import { type CSSProperties, useCallback, useEffect, useState } from "react";

import { api, ApiError, tokenStore, type User } from "./api";
import AuthForm from "./components/AuthForm";
import CheckForm from "./components/CheckForm";
import HistoryList from "./components/HistoryList";
import Logo from "./components/Logo";
import ModerationQueue from "./components/ModerationQueue";
import MyReports from "./components/MyReports";
import { clearSessionState, useSessionState } from "./useSessionState";

type Tab = "check" | "history" | "moderation";
const BASE_TABS: { id: Tab; label: string }[] = [
  { id: "check", label: "Check a posting" },
  { id: "history", label: "My checks" },
];

// The API is what actually protects moderation (403 for students). Hiding the tab is
// only about not showing people a button they can't use.
const canModerate = (user: User) => user.role === "moderator" || user.role === "admin";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useSessionState<Tab>("tab", "check");

  const logout = useCallback(() => {
    tokenStore.clear();
    clearSessionState(); // forget form, result and history for the next person
    setTab("check");
    setUser(null);
  }, [setTab]);

  // Any 401 anywhere (token expired) sends you back to the login screen
  const handleError = useCallback(
    (err: unknown): string => {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        return "Your session expired. Please log in again.";
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

  const tabs = user && canModerate(user)
    ? [...BASE_TABS, { id: "moderation" as Tab, label: "Moderation" }]
    : BASE_TABS;
  // A saved "moderation" tab from an earlier session falls back to "check" for non-moderators
  const active = tabs.some((t) => t.id === tab) ? tab : "check";
  const tabIndex = tabs.findIndex((t) => t.id === active);

  return (
    <>
      <div className="backdrop" aria-hidden="true" />

      {booting ? (
        <div className="boot">Loading…</div>
      ) : !user ? (
        <AuthForm onLoggedIn={setUser} />
      ) : (
        <>
          <header className="topbar glass">
            <Logo height={30} />
            <div className="who">
              {canModerate(user) && <span className="pill neutral">{user.role}</span>}
              <span className="who-email">{user.email}</span>
              <button className="btn btn-gray btn-small" onClick={logout}>Log out</button>
            </div>
          </header>

          <main className="shell">
            {/* iOS-style segmented control; the thumb slides to the selected tab */}
            <div className="segmented" role="tablist"
                 style={{ "--i": tabIndex, "--n": tabs.length } as CSSProperties}>
              <span className="segmented-thumb" aria-hidden="true" />
              {tabs.map((t) => (
                <button key={t.id} role="tab" aria-selected={active === t.id} onClick={() => setTab(t.id)}>
                  {t.label}
                </button>
              ))}
            </div>

            {active === "check" && <CheckForm onError={handleError} />}
            {active === "history" && (
              <div className="stack-lg">
                <HistoryList onError={handleError} />
                <MyReports onError={handleError} />
              </div>
            )}
            {active === "moderation" && <ModerationQueue onError={handleError} />}

            <footer className="foot">
              Scores combine hand-written red-flag rules with a model trained on 17,880 job postings. A verdict is
              guidance, not proof. Never pay to get a job.
            </footer>
          </main>
        </>
      )}
    </>
  );
}
