"""
DevITjobs.uk – UK developer & tech job board.
Free API, no key required.  Returns ~3,400+ UK-based tech jobs with
salary data, experience level, technologies, visa sponsorship, and more.

API endpoint: https://devitjobs.uk/api/jobsLight
"""
import requests
import logging
from typing import List, Optional
from .base import BaseSource, JobData


class DevITJobsSource(BaseSource):
    """UK tech jobs with salary data – free, no API key."""

    name = "devitjobs"
    API_URL = "https://devitjobs.uk/api/jobsLight"

    def is_available(self) -> bool:
        return True  # Always available

    def scrape(
        self, companies: List[str], general_queries: List[str]
    ) -> List[JobData]:
        jobs: List[JobData] = []
        target_set = {c.lower() for c in companies}

        try:
            resp = requests.get(
                self.API_URL,
                timeout=60,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                self.logger.error("Unexpected response format from DevITjobs")
                return jobs

            self.logger.info(
                f"DevITjobs API returned {len(data)} total listings"
            )

            for item in data:
                try:
                    job = self._parse_job(item, target_set)
                    if job and job.is_valid():
                        jobs.append(job)
                except Exception as e:
                    self.logger.debug(f"Parse error: {e}")
                    continue

        except requests.RequestException as e:
            self.logger.error(f"DevITjobs API request failed: {e}")
        except Exception as e:
            self.logger.error(f"DevITjobs unexpected error: {e}")

        self.logger.info(f"DevITjobs total: {len(jobs)} UK jobs extracted")
        return jobs

    def _parse_job(
        self, item: dict, target_set: set
    ) -> Optional[JobData]:
        title = (item.get("name") or "").strip()
        company = (item.get("company") or "").strip()
        if not title or not company:
            return None

        # Build location from city + workplace type
        city = (item.get("actualCity") or "").strip()
        workplace = (item.get("workplace") or "").strip()
        location_parts = []
        if city:
            location_parts.append(city)
        if workplace:
            location_parts.append(workplace.capitalize())
        location_parts.append("UK")
        location = ", ".join(location_parts)

        # Build full URL from slug
        slug = item.get("jobUrl", "")
        url = f"https://devitjobs.uk/jobs/{slug}" if slug else ""
        if not url:
            return None

        # Salary info
        salary_from = item.get("annualSalaryFrom")
        salary_to = item.get("annualSalaryTo")
        salary_str = None
        if salary_from and salary_to:
            salary_str = f"£{salary_from:,.0f} – £{salary_to:,.0f}"
        elif salary_from:
            salary_str = f"From £{salary_from:,.0f}"

        # Experience level
        exp = item.get("expLevel", "")
        exp_map = {
            "Junior": "Entry Level",
            "Regular": "Mid Level",
            "Senior": "Senior Level",
            "Lead": "Lead / Principal",
        }
        experience_level = exp_map.get(exp, exp if exp else None)

        # Technologies as category
        techs = item.get("technologies", [])
        category = ", ".join(techs[:3]) if techs else item.get("techCategory")

        # Job type
        job_type_raw = item.get("jobType", "Full-Time")
        if workplace == "remote":
            job_type_raw = f"Remote, {job_type_raw}"
        elif workplace == "hybrid":
            job_type_raw = f"Hybrid, {job_type_raw}"

        return JobData(
            title=title,
            company=company,
            location=location,
            url=url,
            source="devitjobs",
            salary=salary_str,
            category=category,
            experience_level=experience_level,
            job_type=job_type_raw,
        )
