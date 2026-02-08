"""Base classes for job scraper sources."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class JobData:
    """Standardized job data container."""

    def __init__(
        self,
        title: str,
        company: str,
        location: str,
        url: str,
        source: str,
        category: Optional[str] = None,
        experience_level: Optional[str] = None,
        job_type: Optional[str] = None,
        salary: Optional[str] = None,
    ):
        self.title = title.strip() if title else ''
        self.company = company.strip() if company else ''
        self.location = location.strip() if location else ''
        self.url = url.strip() if url else ''
        self.source = source
        self.category = category.strip() if category else None
        self.experience_level = experience_level.strip() if experience_level else None
        self.job_type = job_type.strip() if job_type else None
        self.salary = salary.strip() if salary else None

    def is_valid(self) -> bool:
        """Check minimum required fields are present."""
        return bool(self.title and self.company and self.location and self.url)

    def is_uk_based(self) -> bool:
        """Check if the job is UK-based or UK-eligible (remote covering UK)."""
        import re
        location_lower = self.location.lower().strip()

        # Reject explicitly non-UK locations first
        non_uk_indicators = [
            'usa only', 'us only', 'united states only',
            'canada only', 'australia only',
        ]
        if any(ind in location_lower for ind in non_uk_indicators):
            return False

        # Explicit UK place names (safe as substring matches)
        uk_places = [
            'united kingdom', 'england', 'scotland', 'wales',
            'northern ireland', 'london', 'manchester', 'birmingham',
            'leeds', 'glasgow', 'liverpool', 'edinburgh', 'bristol',
            'sheffield', 'newcastle', 'nottingham', 'southampton',
            'cardiff', 'belfast', 'leicester', 'coventry',
            'cambridge', 'oxford', 'brighton', 'york', 'aberdeen',
            'dundee', 'exeter', 'norwich', 'plymouth', 'derby',
            'swansea', 'portsmouth', 'wolverhampton',
            'warwick', 'surrey', 'essex', 'kent', 'sussex',
            'hampshire', 'hertfordshire', 'berkshire', 'middlesex',
            'staffordshire', 'lancashire', 'cheshire', 'somerset',
            'dorset', 'devon', 'cornwall', 'wiltshire', 'norfolk',
            'suffolk', 'cambridgeshire', 'oxfordshire', 'buckinghamshire',
            'greater london', 'west midlands', 'east midlands',
            'north west', 'north east', 'south west', 'south east',
            'east anglia', 'yorkshire', 'great britain',
            'remote, uk', 'remote - uk', 'hybrid - uk',
        ]
        if any(p in location_lower for p in uk_places):
            return True

        # Short codes that need word-boundary matching to avoid false positives
        # e.g. "uk" should match "UK" or "UK, Remote" but not "Kaufbeuren"
        short_codes = ['uk', 'gb']
        for code in short_codes:
            if re.search(r'\b' + code + r'\b', location_lower):
                return True

        # UK-eligible remote/global locations (word-boundary for short terms)
        global_exact = ['worldwide', 'global', 'anywhere', 'international',
                        'europe', 'emea', 'remote', 'hybrid', 'remote/hybrid']
        for term in global_exact:
            if re.search(r'\b' + re.escape(term) + r'\b', location_lower):
                return True

        return False

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'url': self.url,
            'source': self.source,
            'category': self.category,
            'experience_level': self.experience_level,
            'job_type': self.job_type,
            'salary': self.salary,
        }


class BaseSource(ABC):
    """Abstract base class for job sources."""

    name: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this source is configured and available."""
        pass

    @abstractmethod
    def scrape(self, companies: List[str], general_queries: List[str]) -> List[JobData]:
        """
        Scrape jobs from this source.

        Args:
            companies: List of target company names to search for.
            general_queries: List of general search queries for broader discovery.

        Returns:
            List of JobData objects.
        """
        pass
