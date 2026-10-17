// Everything that talks to the backend lives here. Components never call fetch() directly.
// URLs are relative ("/api/..."): the page and the API are served from the same address
// (Nginx), so the browser needs no CORS permission.

export type User = { id: number; email: string; role: string; created_at: string };
export type Flag = { rule: string; message: string };

export type Verdict = {
  id: number;
  score: number;
  verdict: "Safe" | "Suspicious" | "Likely scam";
  flags: Flag[];
  limited_info: boolean;
  note: string | null;
  model_version: string;
  cache_hit: boolean;
  created_at: string;
  took_ms: number;
};

export type CheckSummary = {
  id: number;
  title: string | null;
  snippet: string | null;
  score: number;
  verdict: Verdict["verdict"];
  created_at: string;
};

export type History = { items: CheckSummary[]; next_before: string | null };

export type ReportStatus = "pending" | "verified" | "rejected";

export type Report = {
  id: number;
  check_id: number;
  company_name: string;
  reason: string | null;
  status: ReportStatus;
  created_at: string;
  reviewed_at: string | null;
};

// A queue item = the report + the posting it's about, so moderators can judge it
export type QueueItem = Report & {
  title: string | null;
  snippet: string | null;
  score: number;
  verdict: Verdict["verdict"];
};

export type Queue = { items: QueueItem[]; next_after: string | null };

export type Evidence = {
  kind: "company" | "phone" | "email";
  title: string;
  url: string;
  domain: string;
  snippet: string;
  complaint: boolean;
  official: boolean;
};

export type WebCheck = {
  status: "impersonation_risk" | "complaints_found" | "no_reports_found" | "nothing_to_search" | "unavailable";
  summary: string;
  identifiers: { company: string | null; phones: string[]; emails: string[] };
  evidence: Evidence[];
  official_site: Evidence | null;
  searches: number;
};

export type Company = { id: number; name: string; verified_reports: number; last_reported_at: string | null };

// source "live" = this week's Redis leaderboard; "fallback" = Redis down, all-time counts
export type Trending = { items: (Company & { this_week: number | null })[]; source: "live" | "fallback" };

export type PostingInput = {
  title: string;
  description: string;
  company_profile: string;
  salary_range: string;
  // Not part of the text the model scores; used for the web check and to pre-fill reports
  company_name?: string;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// ---- token storage ----
// localStorage keeps you logged in across page reloads. Trade-off: any script running on
// the page could read it (an XSS risk). The stricter option is an httpOnly cookie that
// JavaScript can't see at all; that's planned with refresh tokens in Phase 2.
const TOKEN_KEY = "fakehire_token";

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* storage blocked: stay logged in for this tab only */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* nothing to clear */
    }
  },
};

// ---- one function for every request ----
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(path, { ...init, headers });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return res.json() as Promise<T>;
}

// Turn the API's error body into one readable sentence
async function errorMessage(res: Response): Promise<string> {
  if (res.status === 429) {
    const wait = res.headers.get("Retry-After");
    return wait ? `Too many checks. Try again in ${wait} seconds.` : "Too many requests. Slow down a little.";
  }
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    // 422 validation errors come as a list: [{ loc: [...], msg: "..." }]
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((d: { loc: string[]; msg: string }) => `${d.loc[d.loc.length - 1]}: ${d.msg}`)
        .join(". ");
    }
  } catch {
    /* body wasn't JSON (e.g. an Nginx error page) */
  }
  return `Request failed (${res.status})`;
}

const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  register: (email: string, password: string) =>
    request<User>("/api/v1/auth/register", json({ email, password })),

  // Login uses the OAuth2 form format (username + password), not JSON
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),

  me: () => request<User>("/api/v1/auth/me"),

  check: (posting: PostingInput) => request<Verdict>("/api/v1/check", json(posting)),

  history: (before?: string | null) => {
    const params = new URLSearchParams({ limit: "10" });
    if (before) params.set("before", before);
    return request<History>(`/api/v1/checks/me?${params}`);
  },

  // posting = the text exactly as checked; lets moderators' decisions become training data
  report: (check_id: number, company_name: string, reason: string, posting: PostingInput | null) =>
    request<Report>("/api/v1/reports", json({ check_id, company_name, reason: reason.trim() || null, posting })),

  myReports: () => request<Report[]>("/api/v1/reports/me"),

  // Moderators only (the API answers 403 for everyone else)
  queue: (after?: string | null) => {
    const params = new URLSearchParams({ limit: "10" });
    if (after) params.set("after", after);
    return request<Queue>(`/api/v1/reports/queue?${params}`);
  },

  review: (id: number, status: "verified" | "rejected") =>
    request<Report>(`/api/v1/reports/${id}`, json({ status }, "PATCH")),

  webCheck: (posting: PostingInput) =>
    request<WebCheck>("/api/v1/web-check", json({ posting, company_name: posting.company_name || null })),

  // Public: no login needed
  trending: () => request<Trending>("/api/v1/trending?limit=5"),

  searchCompanies: (q: string) =>
    request<Company[]>(`/api/v1/companies/search?${new URLSearchParams({ q, limit: "5" })}`),
};
