"""Adzuna API job source – free, UK-focused job API."""
import requests
import time
import random
from typing import List, Optional
from .base import BaseSource, JobData


class AdzunaSource(BaseSource):
    """Scraper using the Adzuna public API (requires free API key)."""

    name = "adzuna"
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/gb/search"

    def is_available(self) -> bool:
        return bool(
            self.config.get('ADZUNA_APP_ID') and self.config.get('ADZUNA_API_KEY')
        )

    def scrape(self, companies: List[str], general_queries: List[str]) -> List[JobData]:
        jobs: List[JobData] = []
        all_queries: List[str] = []

        # Build queries for target companies
        for company in companies:
            all_queries.append(company)

        # Add general discovery queries
        all_queries.extend(general_queries)

        for query in all_queries:
            try:
                page_jobs = self._search(query)
                jobs.extend(page_jobs)
                self.logger.info(f"Found {len(page_jobs)} jobs for query '{query}'")
            except Exception as e:
                self.logger.error(f"Error searching for '{query}': {e}")

            time.sleep(random.uniform(
                self.config.get('REQUEST_DELAY_MIN', 1.0),
                self.config.get('REQUEST_DELAY_MAX', 3.0),
            ))

        return jobs

    def _search(self, query: str, max_pages: int = None) -> List[JobData]:
        if max_pages is None:
            max_pages = self.config.get('MAX_PAGES_PER_SOURCE', 3)

        jobs: List[JobData] = []
        app_id = self.config['ADZUNA_APP_ID']
        api_key = self.config['ADZUNA_API_KEY']

        for page in range(1, max_pages + 1):
            try:
                url = f"{self.BASE_URL}/{page}"
                params = {
                    'app_id': app_id,
                    'app_key': api_key,
                    'results_per_page': 50,
                    'what': query,
                    'where': 'United Kingdom',
                    'content-type': 'application/json',
                }

                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if not results:
                    break

                for item in results:
                    job = JobData(
                        title=item.get('title', ''),
                        company=item.get('company', {}).get('display_name', ''),
                        location=item.get('location', {}).get('display_name', ''),
                        url=item.get('redirect_url', ''),
                        source='adzuna',
                        category=item.get('category', {}).get('label', None),
                        experience_level=self._guess_experience(item.get('title', '')),
                        job_type=self._extract_job_type(item),
                    )
                    if job.is_valid():
                        jobs.append(job)

                # Stop if we've fetched all available results
                if page * 50 >= data.get('count', 0):
                    break

                time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                self.logger.error(f"Page {page} error for '{query}': {e}")
                break

        return jobs

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_job_type(item: dict) -> Optional[str]:
        contract_time = item.get('contract_time', '')
        contract_type = item.get('contract_type', '')
        parts = []
        if contract_time:
            parts.append(contract_time.replace('_', ' ').title())
        if contract_type:
            parts.append(contract_type.replace('_', ' ').title())
        return ', '.join(parts) if parts else None

    @staticmethod
    def _guess_experience(title: str) -> Optional[str]:
        title_lower = title.lower()
        if any(k in title_lower for k in ('senior', 'sr.', 'sr ', 'lead', 'principal', 'staff')):
            return 'Senior Level'
        if any(k in title_lower for k in ('junior', 'jr.', 'jr ', 'entry', 'graduate', 'trainee', 'intern')):
            return 'Entry Level'
        if any(k in title_lower for k in ('mid', 'intermediate')):
            return 'Mid Level'
        if any(k in title_lower for k in ('director', 'head of', 'vp ', 'vice president', 'chief', 'cto', 'cfo')):
            return 'Director / Executive'
        if 'manager' in title_lower:
            return 'Manager'
        return None
