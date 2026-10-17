"""Web check: what does the internet say about WHO posted this job?

The model judges the TEXT. This looks for evidence about the poster:
    company name + "scam/fraud/complaint"   -> victims' complaints on forums and review sites
    a phone number from the text            -> reported scam numbers
    a recruiter email from the text         -> reported scam addresses
    company name + "official website"       -> does a real company site exist?

Results are EVIDENCE shown to the user with links, not mixed into the model's score:
web results are noisy (a name like "Typing Solutions" can match unrelated pages), and
keeping them separate keeps the model's metrics, quality gate and retraining meaningful.
"""
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

from redis import Redis
from redis.exceptions import RedisError

from ..clients.search_client import SearchClient, SearchResult, SearchUnavailable

log = logging.getLogger(__name__)

PHONE = re.compile(r"(?:\+?91[\s-]?)?\b([6-9]\d{4}[\s-]?\d{5})\b")   # Indian mobile numbers
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SCAM_WORDS = ("scam", "fraud", "fake", "complaint", "cheat", "beware", "warning", "not genuine", "lost money")
# A complaint must ALSO be about jobs: "Company X fined for tax fraud" isn't a job-scam report
JOB_WORDS = ("job", "recruit", "hiring", "offer letter", "interview", "candidate", "internship", "work from home",
             "registration fee", "deposit", "salary", "vacancy")
# Job boards and social sites mention every company; they don't prove an official website
NOT_OFFICIAL = ("linkedin.", "indeed.", "naukri.", "glassdoor.", "ambitionbox.", "facebook.", "instagram.",
                "twitter.", "x.com", "justdial.", "quora.", "reddit.", "youtube.", "internshala.", "apna.")


# ---------------------------------------------------------------- what we search for
@dataclass
class Identifiers:
    company: str | None
    phones: list[str]
    emails: list[str]

    @property
    def empty(self) -> bool:
        return not (self.company or self.phones or self.emails)


def extract_identifiers(text: str, company: str | None) -> Identifiers:
    phones = list(dict.fromkeys(re.sub(r"\D", "", m)[-10:] for m in PHONE.findall(text)))
    emails = list(dict.fromkeys(e.lower() for e in EMAIL.findall(text)))
    company = " ".join(company.split()) if company and company.strip() else None
    # At most one phone and one email: every search costs API quota
    return Identifiers(company, phones[:1], emails[:1])


# ---------------------------------------------------------------- result
@dataclass
class Evidence:
    kind: str          # "company" | "phone" | "email"
    title: str
    url: str
    domain: str
    snippet: str
    complaint: bool    # mentions the subject, a scam word AND a job word, on a site that isn't the company's own
    official: bool = False   # published on the company's own domain (e.g. its "recruitment fraud alert" page)


@dataclass
class WebCheckResult:
    status: str        # impersonation_risk | complaints_found | no_reports_found | nothing_to_search | unavailable
    summary: str
    identifiers: Identifiers
    evidence: list[Evidence] = field(default_factory=list)
    official_site: Evidence | None = None
    searches: int = 0  # how many searches actually hit the API (0 = all from cache)


def _domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.")


def _safe(url: str) -> bool:
    """Only plain web links reach the browser (no javascript:, data:, etc.)."""
    return urlparse(url).scheme in ("http", "https")


def _main_word(company: str) -> str | None:
    """'Global Typing Solutions' -> 'solutions' is too generic, so take the LONGEST word of 4+
    letters as the brand word that should appear in the company's own domain."""
    words = [w for w in re.findall(r"[a-z0-9]+", company.lower()) if len(w) >= 4]
    return max(words, key=len) if words else None


def _is_company_domain(domain: str, main_word: str | None) -> bool:
    return bool(main_word) and main_word in domain.replace("-", "") and not any(s in domain for s in NOT_OFFICIAL)


# ---------------------------------------------------------------- the service
class WebCheckService:
    def __init__(self, search: SearchClient, redis: Redis, ttl_seconds: int):
        self.search = search
        self.redis = redis
        self.ttl = ttl_seconds
        self._api_calls = 0

    def _cached_search(self, query: str) -> list[SearchResult]:
        """Redis first (24 h). Same idea as the verdict cache: one search, many users."""
        key = "web:v1:" + hashlib.sha256(query.encode()).hexdigest()
        try:
            if (raw := self.redis.get(key)) is not None:
                return [SearchResult(**r) for r in json.loads(raw)]
        except RedisError as exc:
            log.warning("web cache read failed: %s", exc)

        results = self.search.search(query)      # may raise SearchUnavailable
        self._api_calls += 1
        try:
            self.redis.set(key, json.dumps([asdict(r) for r in results]), ex=self.ttl)
        except RedisError as exc:
            log.warning("web cache write failed: %s", exc)
        return results

    def check(self, text: str, company: str | None) -> WebCheckResult:
        ids = extract_identifiers(text, company)
        if ids.empty:
            return WebCheckResult("nothing_to_search",
                                  "Add the company name (or paste a posting with a phone number or email) "
                                  "to search the web.", ids)

        queries = []   # (kind, subject that must appear in a result, query)
        if ids.company:
            queries.append(("company", ids.company.lower(), f'"{ids.company}" scam OR fraud OR complaint'))
        if ids.phones:
            queries.append(("phone", ids.phones[0], f'"{ids.phones[0]}" scam OR fraud'))
        if ids.emails:
            queries.append(("email", ids.emails[0], f'"{ids.emails[0]}"'))

        main_word = _main_word(ids.company) if ids.company else None
        evidence, failures = [], 0
        for kind, subject, query in queries:
            try:
                results = self._cached_search(query)
            except SearchUnavailable as exc:
                log.warning("web search failed: %s", exc)
                failures += 1
                continue
            for r in results:
                if not _safe(r.url):
                    continue
                text_lower = f"{r.title} {r.content}".lower()
                mentions = subject in re.sub(r"[\s-]", "", text_lower) if kind == "phone" else subject in text_lower
                if not mentions:
                    continue      # a result that doesn't even mention the company/number isn't evidence
                domain = _domain(r.url)
                own_site = kind == "company" and _is_company_domain(domain, main_word)
                evidence.append(Evidence(
                    kind, r.title.strip()[:160], r.url, domain, " ".join(r.content.split())[:240],
                    # The company's OWN fraud-alert page is a notice, not a complaint against it
                    complaint=(not own_site and any(w in text_lower for w in SCAM_WORDS)
                               and any(w in text_lower for w in JOB_WORDS)),
                    official=own_site))

        official = self._official_site(ids.company) if ids.company and failures < len(queries) else None

        if failures == len(queries):
            return WebCheckResult("unavailable", "The web check is unavailable right now. "
                                  "The verdict above doesn't depend on it.", ids, searches=self._api_calls)

        complaints = [e for e in evidence if e.complaint]
        evidence.sort(key=lambda e: (not e.complaint, not e.official))   # complaints, then official notices

        # IMPERSONATION: the company has a real website, but the recruiter writes from another
        # domain (often Gmail). Scammers borrow big names; real HR uses the company's own domain.
        mismatched = [e for e in ids.emails if official and not _same_org(e.split("@")[1], official.domain)]
        if mismatched:
            return WebCheckResult(
                "impersonation_risk",
                f"{ids.company} has its own website ({official.domain}), but the recruiter writes from "
                f"{mismatched[0].split('@')[1]}. Scammers often impersonate real companies; confirm the offer "
                f"through {official.domain} directly.",
                ids, evidence[:6], official, self._api_calls)
        if complaints:
            status = "complaints_found"
            summary = (f"Found {len(complaints)} web page{'s' if len(complaints) != 1 else ''} mentioning "
                       "this poster together with words like scam or fraud. Open them and judge for yourself.")
        else:
            status = "no_reports_found"
            summary = ("No scam reports found online for these details. New scams often have no reports yet, "
                       "so this isn't proof the posting is safe.")
        return WebCheckResult(status, summary, ids, evidence[:6], official, self._api_calls)

    def _official_site(self, company: str) -> Evidence | None:
        """A result whose DOMAIN contains the company's brand word, and isn't a job board."""
        main_word = _main_word(company)
        if not main_word:
            return None
        try:
            results = self._cached_search(f'"{company}" official website')
        except SearchUnavailable:
            return None
        for r in results:
            domain = _domain(r.url)
            if _safe(r.url) and _is_company_domain(domain, main_word):
                return Evidence("company", r.title.strip()[:160], r.url, domain,
                                " ".join(r.content.split())[:240], complaint=False, official=True)
        return None


def _same_org(email_domain: str, site_domain: str) -> bool:
    """careers.infosys.com and infosys.com are the same organisation; gmail.com is not."""
    def org(d: str) -> str:
        parts = d.lower().split(".")
        # crude "registrable domain": last two labels, or three for .co.in / .org.in style
        country_style = len(parts) >= 3 and parts[-2] in ("co", "org", "net", "ac", "gov")
        return ".".join(parts[-3:] if country_style else parts[-2:])
    return org(email_domain) == org(site_domain)
