"""
Career Page scraper – fetches job listings directly from company career pages.

Many companies host careers on platforms such as Workday, Taleo, Greenhouse,
Lever, Oracle Cloud HCM, SmartRecruiters, etc.  This source:

  1. Fetches each career page URL stored in the target_companies table.
  2. Attempts generic HTML parsing (links containing job-like paths).
  3. Detects common ATS platforms and uses their public JSON/API endpoints
     when available.
  4. Falls back gracefully if a page is JS-only or blocked.

This is best-effort: it will capture what it can from server-rendered HTML
and known API patterns but won't cover every proprietary ATS.
"""
import re
import time
import random
import logging
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin, parse_qs, urlencode
from bs4 import BeautifulSoup

from .base import BaseSource, JobData

logger = logging.getLogger(__name__)


# ── Known ATS platform API patterns ─────────────────────────────────
# Maps a domain substring → a callable that returns (api_url, parser_func)

class CareerPageSource(BaseSource):
    """Scrapes company career pages for job listings."""

    name = "career_page"

    # Patterns in link href that likely point to individual job postings
    JOB_PATH_PATTERNS = [
        r'/job[s]?/',
        r'/position[s]?/',
        r'/vacanc(?:y|ies)/',
        r'/opening[s]?/',
        r'/career[s]?/.*\d',
        r'/role[s]?/',
        r'/apply/',
        r'/job-details/',
        r'/job_detail/',
        r'/requisition/',
        r'/posting/',
    ]

    # Compile once
    JOB_LINK_RE = re.compile('|'.join(JOB_PATH_PATTERNS), re.IGNORECASE)

    # Domains / URL fragments that indicate known ATS platforms
    WORKDAY_RE = re.compile(r'([\w-]+)\.wd\d?\.myworkdayjobs\.com', re.IGNORECASE)
    GREENHOUSE_RE = re.compile(r'boards\.greenhouse\.io/([\w-]+)', re.IGNORECASE)
    LEVER_RE = re.compile(r'jobs\.lever\.co/([\w-]+)', re.IGNORECASE)
    SMARTRECRUITERS_RE = re.compile(r'careers\.smartrecruiters\.com/([\w-]+)', re.IGNORECASE)
    TALEO_RE = re.compile(r'([\w-]+)\.taleo\.net', re.IGNORECASE)

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
    ]

    MAX_JOBS_PER_COMPANY = 100  # cap per company to avoid runaway scrapes

    def is_available(self) -> bool:
        return True  # Always available – uses stored career URLs

    def scrape(
        self, companies: List[str], general_queries: List[str]
    ) -> List[JobData]:
        """
        Scrape career pages.  `companies` is ignored here because
        we rely on career_urls passed via `scrape_career_pages`.
        """
        # This source is driven by career_urls, not company name lists.
        # The engine calls scrape_career_pages() directly.
        return []

    def scrape_career_pages(
        self, company_urls: List[Dict[str, str]]
    ) -> List[JobData]:
        """
        Scrape a list of company career pages.

        Args:
            company_urls: list of {"name": "Company", "career_url": "https://..."}

        Returns:
            List of JobData objects.
        """
        all_jobs: List[JobData] = []
        session = requests.Session()

        for entry in company_urls:
            company = entry['name']
            url = entry['career_url']

            if not url:
                continue

            try:
                self.logger.info(f"Scraping career page: {company} → {url[:80]}")
                jobs = self._scrape_one(session, company, url)
                self.logger.info(f"  → {len(jobs)} jobs from {company}")
                all_jobs.extend(jobs)
            except Exception as e:
                self.logger.error(f"  → Failed for {company}: {e}")

            # Respectful delay between companies
            time.sleep(random.uniform(
                self.config.get('REQUEST_DELAY_MIN', 1.5),
                self.config.get('REQUEST_DELAY_MAX', 4.0),
            ))

        self.logger.info(
            f"Career pages total: {len(all_jobs)} jobs from "
            f"{len([e for e in company_urls if e.get('career_url')])} pages"
        )
        return all_jobs

    # ── Per-company scraper ──────────────────────────────────────────
    def _scrape_one(
        self, session: requests.Session, company: str, url: str
    ) -> List[JobData]:
        """Try platform-specific API first, then fall back to HTML parsing."""

        # 1) Check for known ATS platforms
        platform_jobs = self._try_platform_api(session, company, url)
        if platform_jobs is not None:
            return platform_jobs[:self.MAX_JOBS_PER_COMPANY]

        # 2) Generic HTML scrape
        html = self._fetch_page(session, url)
        if not html:
            return []

        return self._parse_html_for_jobs(html, url, company)[:self.MAX_JOBS_PER_COMPANY]

    # ── Platform-specific APIs ───────────────────────────────────────
    def _try_platform_api(
        self, session: requests.Session, company: str, url: str
    ) -> Optional[List[JobData]]:
        """Detect ATS platform and use its API when possible."""

        # Greenhouse
        m = self.GREENHOUSE_RE.search(url)
        if m:
            return self._scrape_greenhouse(session, company, m.group(1))

        # Lever
        m = self.LEVER_RE.search(url)
        if m:
            return self._scrape_lever(session, company, m.group(1))

        # Workday
        m = self.WORKDAY_RE.search(url)
        if m:
            return self._scrape_workday_html(session, company, url)

        # SmartRecruiters
        m = self.SMARTRECRUITERS_RE.search(url)
        if m:
            return self._scrape_smartrecruiters(session, company, m.group(1))

        return None  # Not a recognized platform

    def _scrape_greenhouse(
        self, session: requests.Session, company: str, board_token: str
    ) -> List[JobData]:
        """Greenhouse exposes a public JSON API."""
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        try:
            resp = session.get(api_url, timeout=30, params={"content": "true"})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.logger.debug(f"Greenhouse API failed for {company}: {e}")
            return []

        jobs = []
        for item in data.get('jobs', []):
            location = item.get('location', {}).get('name', 'United Kingdom')
            job_url = item.get('absolute_url', '')
            title = item.get('title', '')
            if title and job_url:
                jobs.append(JobData(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    source="career_page",
                    category=self._guess_category(title),
                    experience_level=self._guess_experience(title),
                    job_type=self._guess_job_type(title),
                ))
        return jobs

    def _scrape_lever(
        self, session: requests.Session, company: str, company_slug: str
    ) -> List[JobData]:
        """Lever exposes listings as JSON when ?mode=json is appended."""
        api_url = f"https://api.lever.co/v0/postings/{company_slug}"
        try:
            resp = session.get(api_url, timeout=30, params={"mode": "json"})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.logger.debug(f"Lever API failed for {company}: {e}")
            return []

        jobs = []
        for item in data if isinstance(data, list) else []:
            title = item.get('text', '')
            location = (
                item.get('categories', {}).get('location', '') or
                item.get('workplaceType', '') or
                'United Kingdom'
            )
            job_url = item.get('hostedUrl', '') or item.get('applyUrl', '')
            if title and job_url:
                jobs.append(JobData(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    source="career_page",
                    category=self._guess_category(title),
                    experience_level=self._guess_experience(title),
                    job_type=self._guess_job_type(title),
                ))
        return jobs

    def _scrape_smartrecruiters(
        self, session: requests.Session, company: str, company_slug: str
    ) -> List[JobData]:
        """SmartRecruiters has a public API."""
        api_url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings"
        try:
            resp = session.get(api_url, timeout=30, params={"limit": 100})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.logger.debug(f"SmartRecruiters API failed for {company}: {e}")
            return []

        jobs = []
        for item in data.get('content', []):
            title = item.get('name', '')
            loc_obj = item.get('location', {})
            location = loc_obj.get('city', '') or loc_obj.get('country', '') or 'United Kingdom'
            job_url = item.get('ref', '') or item.get('company', {}).get('websiteUrl', '')
            if title and job_url:
                jobs.append(JobData(
                    title=title,
                    company=company,
                    location=location,
                    url=job_url,
                    source="career_page",
                    category=self._guess_category(title),
                    experience_level=self._guess_experience(title),
                    job_type=self._guess_job_type(title),
                ))
        return jobs

    def _scrape_workday_html(
        self, session: requests.Session, company: str, url: str
    ) -> List[JobData]:
        """Workday pages are mostly JS-rendered. Try fetching the HTML anyway."""
        # Workday is notoriously JS-heavy – best-effort HTML parse
        html = self._fetch_page(session, url)
        if not html:
            return []
        return self._parse_html_for_jobs(html, url, company)

    # ── Generic HTML parsing ─────────────────────────────────────────
    def _fetch_page(self, session: requests.Session, url: str) -> Optional[str]:
        """Fetch a page's HTML content."""
        try:
            session.headers.update({
                'User-Agent': random.choice(self.USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.9',
            })
            resp = session.get(url, timeout=30, allow_redirects=True)
            if resp.status_code != 200:
                self.logger.debug(f"HTTP {resp.status_code} for {url}")
                return None
            return resp.text
        except requests.RequestException as e:
            self.logger.debug(f"Request failed for {url}: {e}")
            return None

    def _parse_html_for_jobs(
        self, html: str, base_url: str, company: str
    ) -> List[JobData]:
        """
        Generic HTML parser: finds links that look like individual job postings
        by checking href patterns and link text.
        """
        soup = BeautifulSoup(html, 'lxml')
        seen_urls = set()
        jobs = []

        # Strategy 1: Links matching job path patterns
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)

            if full_url in seen_urls:
                continue

            # Must look like a job link
            if not self.JOB_LINK_RE.search(href):
                continue

            # Extract title from link text or nearest heading
            title = self._extract_title_from_link(a_tag)
            if not title or len(title) < 5 or len(title) > 300:
                continue

            # Skip navigation / generic links
            if self._is_generic_link(title):
                continue

            seen_urls.add(full_url)
            location = self._extract_location_near(a_tag) or 'United Kingdom'

            jobs.append(JobData(
                title=title,
                company=company,
                location=location,
                url=full_url,
                source="career_page",
                category=self._guess_category(title),
                experience_level=self._guess_experience(title),
                job_type=self._guess_job_type(title),
            ))

        # Strategy 2: Look for structured job cards (common patterns)
        if not jobs:
            jobs = self._parse_job_cards(soup, base_url, company)

        return jobs

    def _extract_title_from_link(self, a_tag) -> Optional[str]:
        """Get job title from the link text or nearby elements."""
        text = a_tag.get_text(strip=True)
        if text and len(text) >= 5:
            return text

        # Check for title/aria-label attributes
        for attr in ['title', 'aria-label']:
            val = a_tag.get(attr, '')
            if val and len(val) >= 5:
                return val.strip()

        # Check parent or sibling heading
        parent = a_tag.parent
        if parent:
            heading = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'span'])
            if heading:
                text = heading.get_text(strip=True)
                if text and len(text) >= 5:
                    return text

        return None

    def _extract_location_near(self, a_tag) -> Optional[str]:
        """Try to find a location string near the job link."""
        # Check parent container for location-like text
        parent = a_tag.parent
        if parent:
            parent = parent.parent  # go up one more level for card containers

        if not parent:
            return None

        # Look for elements that might contain location
        for sel in ['.location', '.job-location', '[data-location]',
                     '.city', '.region', '[class*="location"]']:
            loc_el = parent.select_one(sel)
            if loc_el:
                text = loc_el.get_text(strip=True)
                if text:
                    return text

        return None

    def _parse_job_cards(
        self, soup: BeautifulSoup, base_url: str, company: str
    ) -> List[JobData]:
        """Look for repeated card-like structures containing job info."""
        jobs = []
        seen = set()

        # Common card selectors used by career pages
        card_selectors = [
            '[class*="job-card"]', '[class*="job-item"]',
            '[class*="job-listing"]', '[class*="vacancy"]',
            '[class*="position-card"]', '[class*="opening"]',
            'li[class*="job"]', 'div[class*="result"]',
            'article', 'tr[class*="job"]',
        ]

        for selector in card_selectors:
            cards = soup.select(selector)
            if len(cards) < 2:
                continue  # Needs multiple to be a list

            for card in cards:
                link = card.find('a', href=True)
                if not link:
                    continue

                full_url = urljoin(base_url, link['href'])
                if full_url in seen:
                    continue

                title = self._extract_title_from_link(link)
                if not title or len(title) < 5 or self._is_generic_link(title):
                    continue

                seen.add(full_url)
                location = self._extract_location_near(link) or 'United Kingdom'

                jobs.append(JobData(
                    title=title,
                    company=company,
                    location=location,
                    url=full_url,
                    source="career_page",
                    category=self._guess_category(title),
                    experience_level=self._guess_experience(title),
                    job_type=self._guess_job_type(title),
                ))

            if jobs:
                break  # Found a working selector

        return jobs

    @staticmethod
    def _is_generic_link(text: str) -> bool:
        """Check if link text is generic (not a job title)."""
        generic = [
            'apply now', 'learn more', 'read more', 'view all',
            'see all', 'next', 'previous', 'back', 'home',
            'sign in', 'log in', 'register', 'search',
            'filter', 'sort', 'clear', 'reset', 'cookie',
            'privacy', 'terms', 'contact', 'about',
        ]
        lower = text.lower().strip()
        return lower in generic or len(lower) < 4

    # ── Guessers (shared with google_search logic) ───────────────────
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
