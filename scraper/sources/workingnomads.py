"""
Working Nomads – curated list of remote jobs.
Free API, no key required.

API endpoint: https://www.workingnomads.com/api/exposed_jobs/
"""
import requests
import logging
from typing import List, Optional
from .base import BaseSource, JobData


class WorkingNomadsSource(BaseSource):
    """Free curated remote job listings."""

    name = "workingnomads"
    API_URL = "https://www.workingnomads.com/api/exposed_jobs/"

    def is_available(self) -> bool:
        return True

    def scrape(
        self, companies: List[str], general_queries: List[str]
    ) -> List[JobData]:
        jobs: List[JobData] = []

        try:
            resp = requests.get(
                self.API_URL,
                timeout=30,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                self.logger.error("Unexpected Working Nomads response")
                return jobs

            self.logger.info(
                f"Working Nomads returned {len(data)} total jobs"
            )

            for item in data:
                try:
                    job = self._parse_job(item)
                    if job and job.is_valid():
                        jobs.append(job)
                except Exception as e:
                    self.logger.debug(f"Parse error: {e}")

        except requests.RequestException as e:
            self.logger.error(f"Working Nomads API error: {e}")
        except Exception as e:
            self.logger.error(f"Working Nomads unexpected error: {e}")

        self.logger.info(
            f"Working Nomads total: {len(jobs)} jobs extracted"
        )
        return jobs

    def _parse_job(self, item: dict) -> Optional[JobData]:
        title = (item.get("title") or "").strip()
        company = (item.get("company_name") or "").strip()
        if not title or not company:
            return None

        url = (item.get("url") or "").strip()
        if not url:
            return None

        location = (item.get("location") or "Remote").strip()
        category = (item.get("category_name") or "").strip() or None

        # Tags may contain useful info
        tags = item.get("tags", "")
        if isinstance(tags, str) and tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            if not category and tag_list:
                category = ", ".join(tag_list[:3])

        return JobData(
            title=title,
            company=company,
            location=location,
            url=url,
            source="workingnomads",
            category=category,
            job_type="Remote",
        )
