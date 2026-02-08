"""Remotive API – free remote job board API, no authentication required."""
import requests
import logging
from typing import List, Optional
from .base import BaseSource, JobData


class RemotiveSource(BaseSource):
    """Free remote jobs API – useful for UK-based remote roles."""

    name = "remotive"
    BASE_URL = "https://remotive.com/api/remote-jobs"

    # Categories that map to Remotive's API
    CATEGORIES = [
        'software-dev', 'data', 'devops', 'product',
        'business', 'finance', 'marketing', 'design',
        'customer-support', 'qa', 'all-others',
    ]

    def is_available(self) -> bool:
        return True  # Always available – no API key needed

    def scrape(self, companies: List[str], general_queries: List[str]) -> List[JobData]:
        jobs: List[JobData] = []

        try:
            resp = requests.get(
                self.BASE_URL,
                params={'limit': 500},
                timeout=30,
                headers={'Accept': 'application/json'},
            )
            if resp.status_code != 200:
                self.logger.warning(f"HTTP {resp.status_code}")
                return jobs

            data = resp.json()
            items = data.get('jobs', [])

            for item in items:
                candidate_location = item.get('candidate_required_location', '') or ''
                job = JobData(
                    title=item.get('title', ''),
                    company=item.get('company_name', ''),
                    location=candidate_location if candidate_location else 'Remote',
                    url=item.get('url', ''),
                    source='remotive',
                    category=item.get('category', None),
                    experience_level=self._guess_experience(item.get('title', '')),
                    job_type=item.get('job_type', '').replace('_', ' ').title() or None,
                )
                if job.is_valid():
                    jobs.append(job)

            self.logger.info(f"Fetched {len(jobs)} total jobs from Remotive")

        except Exception as e:
            self.logger.error(f"Error fetching Remotive jobs: {e}")

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
