"""Arbeitnow API – free job board API with UK listings, no authentication required."""
import requests
import time
import logging
from typing import List, Optional
from .base import BaseSource, JobData


class ArbeitnowSource(BaseSource):
    """Free job board API – returns UK and global tech jobs."""

    name = "arbeitnow"
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def is_available(self) -> bool:
        return True  # Always available – no API key needed

    def scrape(self, companies: List[str], general_queries: List[str]) -> List[JobData]:
        jobs: List[JobData] = []
        company_set = {c.lower() for c in companies}
        page = 1
        max_pages = self.config.get('MAX_PAGES_PER_SOURCE', 5)

        while page <= max_pages:
            try:
                resp = requests.get(
                    self.BASE_URL,
                    params={'page': page},
                    timeout=30,
                    headers={'Accept': 'application/json'},
                )
                if resp.status_code != 200:
                    self.logger.warning(f"HTTP {resp.status_code} on page {page}")
                    break

                data = resp.json()
                items = data.get('data', [])
                if not items:
                    break

                for item in items:
                    location = item.get('location', '') or ''
                    remote = item.get('remote', False)

                    job = JobData(
                        title=item.get('title', ''),
                        company=item.get('company_name', ''),
                        location=location if location else ('Remote' if remote else ''),
                        url=item.get('url', ''),
                        source='arbeitnow',
                        category=self._extract_category(item.get('tags', [])),
                        experience_level=self._guess_experience(item.get('title', '')),
                        job_type='Remote' if remote else None,
                    )
                    if job.is_valid():
                        jobs.append(job)

                # Check if there are more pages
                if not data.get('links', {}).get('next'):
                    break

                page += 1
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Page {page} error: {e}")
                break

        self.logger.info(f"Fetched {len(jobs)} total jobs from Arbeitnow")
        return jobs

    @staticmethod
    def _extract_category(tags: list) -> Optional[str]:
        if not tags:
            return None
        # Use first meaningful tag as category
        skip = {'remote', 'full-time', 'part-time', 'contract', 'freelance'}
        for tag in tags:
            if tag.lower() not in skip:
                return tag.title()
        return None

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
