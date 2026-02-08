"""
Jobicy – remote job board with solid UK/EMEA coverage.
Free API, no key required.  Returns up to 50 remote jobs per request.

API endpoint: https://jobicy.com/api/v2/remote-jobs
"""
import requests
import logging
from typing import List, Optional
from .base import BaseSource, JobData


class JobicySource(BaseSource):
    """Free remote job API with UK/EMEA listings."""

    name = "jobicy"
    API_URL = "https://jobicy.com/api/v2/remote-jobs"

    def is_available(self) -> bool:
        return True

    def scrape(
        self, companies: List[str], general_queries: List[str]
    ) -> List[JobData]:
        jobs: List[JobData] = []

        try:
            resp = requests.get(
                self.API_URL,
                params={"count": 50},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_jobs = data.get("jobs", [])
            self.logger.info(f"Jobicy returned {len(raw_jobs)} jobs")

            for item in raw_jobs:
                try:
                    job = self._parse_job(item)
                    if job and job.is_valid():
                        jobs.append(job)
                except Exception as e:
                    self.logger.debug(f"Parse error: {e}")

        except requests.RequestException as e:
            self.logger.error(f"Jobicy API error: {e}")
        except Exception as e:
            self.logger.error(f"Jobicy unexpected error: {e}")

        self.logger.info(f"Jobicy total: {len(jobs)} jobs extracted")
        return jobs

    def _parse_job(self, item: dict) -> Optional[JobData]:
        title = (item.get("jobTitle") or "").strip()
        company = (item.get("companyName") or "").strip()
        if not title or not company:
            return None

        geo = (item.get("jobGeo") or "Remote").strip()
        url = (item.get("url") or "").strip()
        if not url:
            return None

        industry = item.get("jobIndustry", [])
        category = ", ".join(industry) if isinstance(industry, list) else str(industry) if industry else None

        job_type_raw = (item.get("jobType") or "").strip()
        job_type = self._normalize_job_type(job_type_raw)

        level = (item.get("jobLevel") or "").strip()

        return JobData(
            title=title,
            company=company,
            location=geo,
            url=url,
            source="jobicy",
            category=category,
            experience_level=level if level else None,
            job_type=f"Remote, {job_type}" if job_type else "Remote",
        )

    @staticmethod
    def _normalize_job_type(raw: str) -> Optional[str]:
        mapping = {
            "full-time": "Full-time",
            "full_time": "Full-time",
            "part-time": "Part-time",
            "contract": "Contract",
            "freelance": "Freelance",
            "internship": "Internship",
        }
        return mapping.get(raw.lower().strip(), raw if raw else None)
