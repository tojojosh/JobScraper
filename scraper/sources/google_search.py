"""
Web Search scraper – uses DuckDuckGo to search the entire web for UK job
listings.  DuckDuckGo's HTML endpoint returns server-rendered results that
are easy to parse (unlike Google, which requires JavaScript rendering).

This effectively "scrapes the web" – every job board, career page, LinkedIn
listing, and recruitment site indexed by the search engine is a potential hit.
"""
import requests
import time
import random
import re
import logging
from typing import List, Optional, Dict, Tuple
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from .base import BaseSource, JobData


class GoogleSearchSource(BaseSource):
    """
    Primary web-scraping source.  Searches the web via DuckDuckGo HTML
    and extracts UK job listings from across all indexed sites.

    Named 'google_search' for the UI badge (source label).  Under the hood
    it uses DuckDuckGo's HTML endpoint which reliably returns server-side-
    rendered search results.
    """

    name = "google_search"
    SEARCH_URL = "https://html.duckduckgo.com/html/"

    USER_AGENTS = [
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.3 Safari/605.1.15"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
            "Gecko/20100101 Firefox/123.0"
        ),
    ]

    # Domains that never represent job listings
    SKIP_DOMAINS = frozenset({
        "duckduckgo.com", "google.com", "google.co.uk", "bing.com",
        "youtube.com", "wikipedia.org", "wikimedia.org",
        "facebook.com", "twitter.com", "x.com", "instagram.com",
        "tiktok.com", "reddit.com", "pinterest.com",
        "amazon.co.uk", "ebay.co.uk", "bbc.co.uk",
    })

    # Job-board domains (helps company extraction from titles)
    JOB_BOARDS = {
        "linkedin.com": "LinkedIn",
        "indeed.co.uk": "Indeed",
        "indeed.com": "Indeed",
        "glassdoor.co.uk": "Glassdoor",
        "glassdoor.com": "Glassdoor",
        "reed.co.uk": "Reed",
        "totaljobs.com": "Totaljobs",
        "cv-library.co.uk": "CV-Library",
        "monster.co.uk": "Monster",
        "cwjobs.co.uk": "CWJobs",
        "adzuna.co.uk": "Adzuna",
        "jobsite.co.uk": "Jobsite",
        "workable.com": "Workable",
        "lever.co": "Lever",
        "greenhouse.io": "Greenhouse",
        "findajob.dwp.gov.uk": "Find a Job (Gov.uk)",
    }

    COMPANY_BATCH_SIZE = 3
    MAX_QUERIES = 70

    # ──────────────────────────────────────────────────────────────
    def is_available(self) -> bool:
        return True

    def scrape(
        self, companies: List[str], general_queries: List[str]
    ) -> List[JobData]:
        queries = self._build_queries(companies, general_queries)
        jobs: List[JobData] = []
        seen_urls: set = set()

        session = requests.Session()
        consecutive_failures = 0

        for idx, query in enumerate(queries[: self.MAX_QUERIES]):
            if consecutive_failures >= 5:
                self.logger.warning(
                    f"Stopping web search after {consecutive_failures} "
                    f"consecutive failures ({len(jobs)} jobs found so far)"
                )
                break

            session.headers.update({
                "User-Agent": random.choice(self.USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Referer": "https://html.duckduckgo.com/",
            })

            try:
                results = self._search(session, query)

                if results is None:
                    consecutive_failures += 1
                    time.sleep(random.uniform(5, 10))
                    continue

                consecutive_failures = 0
                batch_new = 0

                for r in results:
                    if r["url"] in seen_urls:
                        continue
                    job = self._result_to_job(r)
                    if job and job.is_valid():
                        seen_urls.add(r["url"])
                        jobs.append(job)
                        batch_new += 1

                self.logger.info(
                    f"Query {idx+1}/{min(len(queries), self.MAX_QUERIES)}: "
                    f"{len(results)} results, {batch_new} new jobs | {query[:70]}"
                )

            except Exception as e:
                self.logger.error(f"Search error: {e}")
                consecutive_failures += 1

            # Respectful delay – DuckDuckGo rate-limits quickly
            time.sleep(random.uniform(3.0, 6.0))

        self.logger.info(f"Web search total: {len(jobs)} jobs extracted")
        return jobs

    # ── Query builder ────────────────────────────────────────────
    def _build_queries(
        self, companies: List[str], general_queries: List[str]
    ) -> List[str]:
        queries: List[str] = []

        # 1) Individual target-company queries (highest priority)
        for company in companies:
            queries.append(f'"{company}" jobs UK hiring')

        # 2) General skilled-role queries for broader discovery
        for q in general_queries:
            queries.append(f"{q} jobs hiring 2026")

        # 3) Extra discovery / niche queries
        extras = [
            "graduate scheme UK 2026 hiring",
            "tech jobs London hiring 2026",
            "engineering vacancies UK 2026",
            "finance jobs City of London 2026",
            "consulting jobs UK hiring 2026",
            "legal jobs UK solicitor 2026",
            "NHS jobs UK careers",
            "renewable energy jobs UK 2026",
            "AI machine learning jobs UK",
            "cyber security analyst UK jobs",
        ]
        queries.extend(extras)

        # Shuffle so if we hit the cap we sample from all categories
        random.shuffle(queries)
        return queries

    # ── HTTP fetch ───────────────────────────────────────────────
    def _search(
        self, session: requests.Session, query: str
    ) -> Optional[List[Dict]]:
        try:
            resp = session.get(
                self.SEARCH_URL,
                params={"q": query},
                timeout=30,
            )
        except requests.RequestException as e:
            self.logger.warning(f"Request failed: {e}")
            return None

        if resp.status_code == 202:
            # DuckDuckGo rate limit – wait and retry once
            self.logger.info("Rate limited (202) – waiting before retry…")
            time.sleep(random.uniform(15, 25))
            try:
                resp = session.get(
                    self.SEARCH_URL,
                    params={"q": query},
                    timeout=30,
                )
                if resp.status_code != 200:
                    self.logger.warning(f"Retry still got HTTP {resp.status_code}")
                    return None
            except requests.RequestException:
                return None

        if resp.status_code != 200:
            self.logger.warning(f"HTTP {resp.status_code}")
            return None

        return self._parse_results(resp.text)

    # ── Result parser ────────────────────────────────────────────
    def _parse_results(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "lxml")
        results: List[Dict] = []

        for result_div in soup.select(".result"):
            title_el = result_div.select_one(".result__a")
            snippet_el = result_div.select_one(".result__snippet")

            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            raw_href = title_el.get("href", "")
            url = self._unwrap_ddg_url(raw_href)

            if not url:
                continue

            try:
                domain = urlparse(url).netloc.lower().replace("www.", "")
            except Exception:
                continue

            if any(skip in domain for skip in self.SKIP_DOMAINS):
                continue

            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "domain": domain,
            })

        return results

    @staticmethod
    def _unwrap_ddg_url(href: str) -> Optional[str]:
        """Extract the real URL from DuckDuckGo's redirect wrapper."""
        if "uddg=" in href:
            try:
                qs = parse_qs(href.split("?", 1)[1]) if "?" in href else {}
                urls = qs.get("uddg", [])
                if urls:
                    return unquote(urls[0])
            except Exception:
                pass
        if href.startswith("http") and "duckduckgo" not in href:
            return href
        return None

    # ── Result → JobData ─────────────────────────────────────────
    def _result_to_job(self, result: Dict) -> Optional[JobData]:
        raw_title = result["title"]
        url = result["url"]
        snippet = result.get("snippet", "")
        domain = result.get("domain", "")

        company = self._extract_company(raw_title, url, domain)
        location = self._extract_location(raw_title, snippet)
        clean_title = self._clean_title(raw_title, company, domain)

        # Reject generic search-result pages (e.g. "1,234 Software Engineer jobs")
        if self._is_search_results_page(clean_title):
            return None

        if not clean_title or len(clean_title) < 4:
            return None
        if not company or company.lower() in ("jobs", "careers", "hiring", "search"):
            return None

        return JobData(
            title=clean_title,
            company=company,
            location=location or "United Kingdom",
            url=url,
            source="google_search",
            category=self._guess_category(clean_title),
            experience_level=self._guess_experience(clean_title),
            job_type=self._guess_job_type(clean_title + " " + snippet),
        )

    @staticmethod
    def _is_search_results_page(title: str) -> bool:
        """Detect pages that aren't individual job listings."""
        patterns = [
            r"\d[\d,]+\+?\s+(jobs?|vacancies|positions|results)",
            r"jobs?\s+in\s+(united kingdom|uk|london|manchester|birmingham)",
            r"^(search|find|browse)\s+",
            r"\|\s*(reed|indeed|glassdoor|totaljobs|linkedin)\s*$",
            r"\bhow\s+(to|ai|is)\b",     # Blog posts ("How to...", "How AI is...")
            r"\btop\s+\d+\s+",            # Listicles ("Top 10...")
            r"\bguide\b",                  # Guides
            r"\btips\b",                   # Tips articles
            r"\bsalary\b.*\bguide\b",     # Salary guides
            r"\bbest\s+(companies|employers|places)\b",
        ]
        t = title.lower()
        for p in patterns:
            if re.search(p, t, re.IGNORECASE):
                return True
        return False

    # ── Company extraction ───────────────────────────────────────
    def _extract_company(
        self, title: str, url: str, domain: str
    ) -> str:
        board = self._job_board_for_domain(domain)

        if board:
            company = self._company_from_board_title(title, board)
            if company:
                return company

        # "Title - Company" or "Title | Company"
        for sep in [" - ", " | ", " – ", " — "]:
            if sep in title:
                parts = title.rsplit(sep, 1)
                candidate = self._strip_suffixes(parts[-1].strip())
                if 2 < len(candidate) < 80:
                    return candidate

        # "... at Company"
        m = re.search(r"\bat\s+(.+?)$", title, re.IGNORECASE)
        if m:
            candidate = self._strip_suffixes(m.group(1).strip())
            if len(candidate) > 2:
                return candidate

        # Derive from domain
        clean_domain = domain.replace("careers.", "").replace("jobs.", "")
        base = clean_domain.split(".")[0]
        if len(base) > 2:
            return base.replace("-", " ").title()

        return ""

    def _company_from_board_title(self, title: str, board: str) -> str:
        cleaned = title
        for suffix in [
            f"| {board}", f"- {board}", f"— {board}",
            f"· {board}", board,
        ]:
            cleaned = cleaned.replace(suffix, "").strip()

        for sep in [" - ", " | ", " – ", " — "]:
            if sep in cleaned:
                parts = cleaned.rsplit(sep, 1)
                candidate = self._strip_suffixes(parts[-1].strip())
                if 2 < len(candidate) < 80:
                    return candidate

        m = re.search(r"\bat\s+(.+?)$", cleaned, re.IGNORECASE)
        if m:
            return self._strip_suffixes(m.group(1).strip())

        return ""

    @staticmethod
    def _strip_suffixes(name: str) -> str:
        for s in [
            "Careers", "Jobs", "Hiring", "Vacancies",
            "careers", "jobs", "hiring", "vacancies",
            "LinkedIn", "Indeed", "Glassdoor", "Reed",
            "UK", "Ltd", "Limited", "PLC", "plc", "Inc",
        ]:
            name = re.sub(rf"\s*\b{re.escape(s)}\s*$", "", name).strip()
        return name

    def _job_board_for_domain(self, domain: str) -> Optional[str]:
        for pattern, board in self.JOB_BOARDS.items():
            if pattern in domain:
                return board
        return None

    # ── Location extraction ──────────────────────────────────────
    @staticmethod
    def _extract_location(title: str, snippet: str) -> Optional[str]:
        text = f"{title} {snippet}"
        uk_cities = [
            "London", "Manchester", "Birmingham", "Leeds", "Glasgow",
            "Liverpool", "Edinburgh", "Bristol", "Sheffield", "Newcastle",
            "Nottingham", "Southampton", "Cardiff", "Belfast", "Leicester",
            "Coventry", "Reading", "Cambridge", "Oxford", "Brighton",
            "York", "Aberdeen", "Bath", "Dundee", "Exeter", "Norwich",
            "Plymouth", "Derby", "Swansea", "Portsmouth", "Warwick",
            "Milton Keynes", "Swindon", "Guildford", "Cheltenham",
            "Canary Wharf", "Slough", "Luton", "Croydon", "Watford",
        ]
        found = []
        for city in uk_cities:
            if re.search(r"\b" + re.escape(city) + r"\b", text, re.IGNORECASE):
                found.append(city)
        if found:
            return ", ".join(found[:2]) + ", UK"

        if re.search(r"\bUnited Kingdom\b", text, re.IGNORECASE):
            return "United Kingdom"
        if re.search(r"\bRemote\b", text, re.IGNORECASE):
            return "Remote, UK"
        if re.search(r"\bHybrid\b", text, re.IGNORECASE):
            return "Hybrid, UK"
        if re.search(r"\b(UK|U\.K\.)\b", text):
            return "United Kingdom"

        return None

    # ── Title cleaning ───────────────────────────────────────────
    def _clean_title(self, title: str, company: str, domain: str) -> str:
        cleaned = title
        for tag in [
            "| LinkedIn", "- LinkedIn", "| Indeed", "- Indeed",
            "| Glassdoor", "- Glassdoor", "| Reed", "- Reed",
            "| Totaljobs", "- Totaljobs", "| CV-Library",
            "| Workable", "| Lever", "| Greenhouse",
            "| Find a Job", "- Find a Job", "| CWJobs",
        ]:
            cleaned = cleaned.replace(tag, "").strip()

        if company:
            for sep in [" - ", " | ", " – ", " — ", " at ", " @ "]:
                pattern = re.escape(sep) + re.escape(company) + r"\s*$"
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(r"\s*[-|–—]\s*$", "", cleaned).strip()
        return cleaned

    # ── Guessers ─────────────────────────────────────────────────
    @staticmethod
    def _guess_experience(title: str) -> Optional[str]:
        t = title.lower()
        if any(k in t for k in ("senior", "sr.", "sr ", "lead", "principal", "staff")):
            return "Senior Level"
        if any(k in t for k in ("junior", "jr.", "jr ", "entry", "graduate", "trainee", "intern", "apprentice")):
            return "Entry Level"
        if any(k in t for k in ("mid", "intermediate")):
            return "Mid Level"
        if any(k in t for k in ("director", "head of", "vp ", "vice president", "chief", "cto", "cfo")):
            return "Director / Executive"
        if "manager" in t:
            return "Manager"
        return None

    @staticmethod
    def _guess_category(title: str) -> Optional[str]:
        t = title.lower()
        mapping = [
            (["software", "developer", "engineer", "frontend", "backend",
              "full-stack", "fullstack", "devops", "sre", "platform"],
             "Technology"),
            (["data scientist", "data engineer", "data analyst",
              "machine learning", "ai ", "artificial intelligence", "ml "],
             "Data & AI"),
            (["product manager", "product owner", "product lead"], "Product"),
            (["designer", "ux", "ui", "design"], "Design"),
            (["finance", "accountant", "auditor", "actuary", "tax",
              "investment", "banking"], "Finance"),
            (["solicitor", "lawyer", "legal", "paralegal", "barrister"], "Legal"),
            (["consultant", "consulting", "advisory"], "Consulting"),
            (["marketing", "seo", "content", "brand"], "Marketing"),
            (["sales", "business development", "account executive"], "Sales"),
            (["nurse", "doctor", "clinical", "medical", "healthcare", "nhs"],
             "Healthcare"),
            (["mechanical", "electrical", "civil", "structural", "chemical"],
             "Engineering"),
            (["cyber", "security", "infosec", "penetration"], "Cybersecurity"),
            (["project manager", "programme manager", "scrum", "delivery"],
             "Project Management"),
            (["analyst", "research", "quantitative"], "Research & Analysis"),
        ]
        for keywords, category in mapping:
            if any(k in t for k in keywords):
                return category
        return None

    @staticmethod
    def _guess_job_type(text: str) -> Optional[str]:
        t = text.lower()
        parts = []
        if "full-time" in t or "full time" in t or "permanent" in t:
            parts.append("Full-time")
        if "part-time" in t or "part time" in t:
            parts.append("Part-time")
        if "contract" in t:
            parts.append("Contract")
        if "freelance" in t:
            parts.append("Freelance")
        return ", ".join(parts) if parts else None
