"""
The Muse API – free job board with thousands of real UK listings.
No authentication required.  Supports location and category filtering.
https://www.themuse.com/developers/api/v2
"""
import requests
import time
import random
import logging
from typing import List, Optional
from .base import BaseSource, JobData


class TheMuseSource(BaseSource):
    """Free job API with excellent UK coverage – no API key needed."""

    name = "themuse"
    BASE_URL = "https://www.themuse.com/api/public/jobs"

    # High-yield UK location queries for The Muse API.
    # "London" and "United Kingdom" cover the vast majority of UK listings.
    # "Flexible / Remote" captures remote roles from UK-based companies.
    UK_LOCATIONS = [
        "London, United Kingdom",
        "United Kingdom",
        "Flexible / Remote",
    ]

    # Experience levels supported by The Muse API
    LEVELS = [
        "Entry Level",
        "Mid Level",
        "Senior Level",
    ]

    def is_available(self) -> bool:
        return True  # Always available – no API key

    def scrape(
        self, companies: List[str], general_queries: List[str]
    ) -> List[JobData]:
        jobs: List[JobData] = []
        seen_ids: set = set()
        max_pages_per_location = self.config.get('MAX_PAGES_PER_SOURCE', 5)

        target_set = {c.lower() for c in companies}

        for location in self.UK_LOCATIONS:
            try:
                loc_jobs = self._fetch_location(
                    location, max_pages_per_location, seen_ids, target_set
                )
                jobs.extend(loc_jobs)
                self.logger.info(
                    f"Fetched {len(loc_jobs)} jobs for '{location}'"
                )
            except Exception as e:
                self.logger.error(f"Error fetching '{location}': {e}")

            time.sleep(random.uniform(0.5, 1.5))

        self.logger.info(f"The Muse total: {len(jobs)} UK jobs extracted")
        return jobs

    def _fetch_location(
        self,
        location: str,
        max_pages: int,
        seen_ids: set,
        target_set: set,
    ) -> List[JobData]:
        jobs: List[JobData] = []

        for page in range(max_pages):
            try:
                resp = requests.get(
                    self.BASE_URL,
                    params={"location": location, "page": page},
                    timeout=30,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code != 200:
                    self.logger.warning(
                        f"HTTP {resp.status_code} for {location} page {page}"
                    )
                    break

                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    job_id = item.get("id")
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    company_info = item.get("company", {})
                    company_name = company_info.get("name", "")

                    # Build location string from the locations list
                    locs = item.get("locations", [])
                    loc_names = [
                        loc.get("name", "")
                        for loc in locs
                        if loc.get("name", "")
                    ]
                    loc_str = ", ".join(loc_names) if loc_names else location

                    # Build the direct job URL
                    landing = item.get("refs", {}).get("landing_page", "")
                    if not landing:
                        short_name = item.get("short_name", "")
                        if short_name:
                            landing = f"https://www.themuse.com/jobs/{company_name.lower().replace(' ','-')}/{short_name}"

                    # Determine experience level from the API levels
                    levels = item.get("levels", [])
                    exp_level = None
                    if levels:
                        level_name = levels[0].get("name", "")
                        if level_name:
                            exp_level = level_name

                    # Category from tags / categories
                    categories = item.get("categories", [])
                    category = categories[0].get("name") if categories else None

                    # Check if this is a priority company
                    is_priority = company_name.lower() in target_set

                    job = JobData(
                        title=item.get("name", ""),
                        company=company_name,
                        location=loc_str,
                        url=landing,
                        source="themuse",
                        category=category,
                        experience_level=exp_level,
                        job_type=self._guess_job_type(
                            item.get("name", ""), loc_str
                        ),
                    )

                    if job.is_valid():
                        jobs.append(job)

                # Check if there are more pages
                page_count = data.get("page_count", 0)
                if page + 1 >= page_count:
                    break

                time.sleep(random.uniform(0.3, 0.8))

            except Exception as e:
                self.logger.error(
                    f"Page {page} error for {location}: {e}"
                )
                break

        return jobs

    @staticmethod
    def _guess_job_type(title: str, location: str) -> Optional[str]:
        parts = []
        text = f"{title} {location}".lower()
        if "flexible" in text or "remote" in text:
            parts.append("Remote")
        if "part-time" in text or "part time" in text:
            parts.append("Part-time")
        if "contract" in text:
            parts.append("Contract")
        if "intern" in text:
            parts.append("Internship")
        if not parts:
            parts.append("Full-time")
        return ", ".join(parts)
