"""Indeed UK web scraper – best-effort HTML parsing of search results."""
import requests
import time
import random
import re
import json
from typing import List, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from .base import BaseSource, JobData


class IndeedSource(BaseSource):
    """Web scraper for Indeed UK search results."""

    name = "indeed_uk"
    BASE_URL = "https://uk.indeed.com"

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        ),
        'Accept': (
            'text/html,application/xhtml+xml,application/xml;'
            'q=0.9,image/avif,image/webp,*/*;q=0.8'
        ),
        'Accept-Language': 'en-GB,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def is_available(self) -> bool:
        return True  # Always available (web scraping)

    def scrape(self, companies: List[str], general_queries: List[str]) -> List[JobData]:
        jobs: List[JobData] = []
        all_queries: List[str] = []

        # Limit company queries to avoid excessive requests
        for company in companies[:25]:
            all_queries.append(f'"{company}"')

        all_queries.extend(general_queries)

        session = requests.Session()
        session.headers.update(self.HEADERS)

        consecutive_failures = 0
        max_consecutive_failures = 3

        for query in all_queries:
            if consecutive_failures >= max_consecutive_failures:
                self.logger.warning(
                    f"Stopping Indeed scraper after {max_consecutive_failures} "
                    "consecutive failures (site is blocking requests)"
                )
                break

            try:
                page_jobs = self._search(session, query)
                jobs.extend(page_jobs)
                self.logger.info(f"Found {len(page_jobs)} jobs for query '{query}'")
                if page_jobs:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception as e:
                self.logger.error(f"Error searching for '{query}': {e}")
                consecutive_failures += 1

            time.sleep(random.uniform(
                self.config.get('REQUEST_DELAY_MIN', 2.0),
                self.config.get('REQUEST_DELAY_MAX', 5.0),
            ))

        return jobs

    def _search(self, session: requests.Session, query: str) -> List[JobData]:
        jobs: List[JobData] = []
        max_pages = min(self.config.get('MAX_PAGES_PER_SOURCE', 3), 3)

        for page in range(max_pages):
            try:
                url = f"{self.BASE_URL}/jobs"
                params = {
                    'q': query,
                    'l': 'United Kingdom',
                    'start': page * 10,
                }

                response = session.get(url, params=params, timeout=30)

                if response.status_code == 403:
                    self.logger.warning("Access forbidden – rate limited")
                    break

                if response.status_code != 200:
                    self.logger.warning(f"HTTP {response.status_code}")
                    break

                page_jobs = self._parse_results(response.text)
                jobs.extend(page_jobs)

                if not page_jobs:
                    break

                time.sleep(random.uniform(3.0, 6.0))

            except Exception as e:
                self.logger.error(f"Page {page} error: {e}")
                break

        return jobs

    def _parse_results(self, html: str) -> List[JobData]:
        """Parse Indeed search results page."""
        # Try embedded JSON first (more stable than HTML selectors)
        jobs_from_json = self._parse_json_data(html)
        if jobs_from_json:
            return jobs_from_json

        # Fallback: parse HTML directly
        return self._parse_html(html)

    def _parse_json_data(self, html: str) -> List[JobData]:
        """Extract job data from embedded JSON in the page."""
        jobs: List[JobData] = []
        try:
            pattern = (
                r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]'
                r'\s*=\s*({.*?});'
            )
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                return []

            data = json.loads(match.group(1))
            results = (
                data.get('metaData', {})
                .get('mosaicProviderJobCardsModel', {})
                .get('results', [])
            )

            for item in results:
                job_types = item.get('jobTypes', [])
                job = JobData(
                    title=item.get('title', ''),
                    company=item.get('company', ''),
                    location=(
                        item.get('formattedLocation', '')
                        or item.get('location', '')
                    ),
                    url=f"{self.BASE_URL}/viewjob?jk={item.get('jobkey', '')}",
                    source='indeed_uk',
                    job_type=job_types[0] if job_types else None,
                    experience_level=self._guess_experience(item.get('title', '')),
                )
                if job.is_valid():
                    jobs.append(job)

        except Exception as e:
            self.logger.debug(f"Could not parse Indeed JSON data: {e}")

        return jobs

    def _parse_html(self, html: str) -> List[JobData]:
        """Fallback HTML parser for Indeed results."""
        jobs: List[JobData] = []
        soup = BeautifulSoup(html, 'lxml')

        job_cards = soup.select(
            'div.job_seen_beacon, div.cardOutline, '
            'div.resultContent, li div[data-jk]'
        )

        for card in job_cards:
            try:
                # Title
                title_el = card.select_one(
                    'h2.jobTitle a, h2 a, a[data-jk], '
                    'span[id^="jobTitle"]'
                )
                title = title_el.get_text(strip=True) if title_el else ''

                # Job key / URL
                jk = None
                link_el = card.select_one('a[data-jk]')
                if link_el:
                    jk = link_el.get('data-jk', '')
                elif title_el and title_el.get('href'):
                    href = title_el['href']
                    if 'jk=' in href:
                        jk = href.split('jk=')[1].split('&')[0]

                url = f"{self.BASE_URL}/viewjob?jk={jk}" if jk else ''

                # Company
                company_el = card.select_one(
                    '[data-testid="company-name"], '
                    'span.companyName, .company'
                )
                company = company_el.get_text(strip=True) if company_el else ''

                # Location
                location_el = card.select_one(
                    '[data-testid="text-location"], '
                    'div.companyLocation, .location'
                )
                location = location_el.get_text(strip=True) if location_el else ''

                job = JobData(
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    source='indeed_uk',
                    experience_level=self._guess_experience(title),
                )

                if job.is_valid():
                    jobs.append(job)

            except Exception as e:
                self.logger.debug(f"Error parsing job card: {e}")
                continue

        return jobs

    @staticmethod
    def _guess_experience(title: str) -> Optional[str]:
        tl = title.lower()
        if any(k in tl for k in ('senior', 'sr.', 'lead', 'principal', 'staff')):
            return 'Senior Level'
        if any(k in tl for k in ('junior', 'jr.', 'entry', 'graduate', 'trainee', 'intern')):
            return 'Entry Level'
        if any(k in tl for k in ('mid', 'intermediate')):
            return 'Mid Level'
        if any(k in tl for k in ('director', 'head of', 'vp ', 'vice president', 'chief')):
            return 'Director / Executive'
        if 'manager' in tl:
            return 'Manager'
        return None
