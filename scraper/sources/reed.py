"""Reed.co.uk API job source – free UK job board API."""
import requests
import base64
import time
import random
from typing import List, Optional
from .base import BaseSource, JobData


class ReedSource(BaseSource):
    """Scraper using the Reed developer API (requires free API key)."""

    name = "reed"
    BASE_URL = "https://www.reed.co.uk/api/1.0/search"

    def is_available(self) -> bool:
        return bool(self.config.get('REED_API_KEY'))

    def scrape(self, companies: List[str], general_queries: List[str]) -> List[JobData]:
        jobs: List[JobData] = []
        all_queries: List[str] = []

        for company in companies:
            all_queries.append(company)

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

    def _search(self, query: str) -> List[JobData]:
        jobs: List[JobData] = []
        api_key = self.config['REED_API_KEY']
        auth = base64.b64encode(f"{api_key}:".encode()).decode()
        max_results = self.config.get('MAX_RESULTS_PER_COMPANY', 100)
        results_per_page = 100

        for skip in range(0, max_results, results_per_page):
            try:
                params = {
                    'keywords': query,
                    'locationName': 'United Kingdom',
                    'resultsToTake': results_per_page,
                    'resultsToSkip': skip,
                }
                headers = {'Authorization': f'Basic {auth}'}

                response = requests.get(
                    self.BASE_URL, params=params, headers=headers, timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if not results:
                    break

                for item in results:
                    url = item.get('jobUrl', '')
                    if not url and item.get('jobId'):
                        url = f"https://www.reed.co.uk/jobs/{item['jobId']}"

                    job = JobData(
                        title=item.get('jobTitle', ''),
                        company=item.get('employerName', ''),
                        location=item.get('locationName', ''),
                        url=url,
                        source='reed',
                        job_type=self._get_job_type(item),
                        experience_level=self._guess_experience(item.get('jobTitle', '')),
                    )
                    if job.is_valid():
                        jobs.append(job)

                total = data.get('totalResults', 0)
                if skip + results_per_page >= total:
                    break

                time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                self.logger.error(f"Page error for '{query}': {e}")
                break

        return jobs

    @staticmethod
    def _get_job_type(item: dict) -> Optional[str]:
        parts = []
        if item.get('partTime'):
            parts.append('Part-time')
        elif item.get('fullTime'):
            parts.append('Full-time')
        if item.get('contractType'):
            parts.append(item['contractType'])
        return ', '.join(parts) if parts else None

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
