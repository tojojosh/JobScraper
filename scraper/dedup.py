"""Deduplication utilities for scraped job data."""
import hashlib
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import List, Set, Tuple
from .sources.base import JobData

# Query-string parameters commonly used for tracking (not part of the job identity)
_TRACKING_PARAMS = frozenset({
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'ref', 'source', 'fbclid', 'gclid', 'mc_cid', 'mc_eid',
})


def canonicalize_url(url: str) -> str:
    """Normalize a URL for deduplication – strips tracking params, lowercases, etc."""
    try:
        parsed = urlparse(url.strip().lower())
        qs = parse_qs(parsed.query)
        filtered_qs = {k: v for k, v in qs.items() if k not in _TRACKING_PARAMS}
        clean_query = urlencode(filtered_qs, doseq=True)
        clean_path = parsed.path.rstrip('/')
        return urlunparse((parsed.scheme, parsed.netloc, clean_path, '', clean_query, ''))
    except Exception:
        return url.strip().lower()


def url_hash(url: str) -> str:
    """SHA-256 based hash (first 32 hex chars) of the canonicalized URL."""
    canonical = canonicalize_url(url)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]


def normalize_text(text: str) -> str:
    """Lowercase, strip non-alphanumeric chars, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def is_similar_job(job1: JobData, job2: JobData) -> bool:
    """Check if two jobs are likely duplicates."""
    if url_hash(job1.url) == url_hash(job2.url):
        return True

    title1 = normalize_text(job1.title)
    title2 = normalize_text(job2.title)
    company1 = normalize_text(job1.company)
    company2 = normalize_text(job2.company)

    # Same title + company → duplicate
    if title1 == title2 and company1 == company2:
        return True

    return False


def deduplicate_jobs(jobs: List[JobData]) -> Tuple[List[JobData], int]:
    """
    Remove duplicate jobs from a list.

    Returns:
        (unique_jobs, duplicate_count)
    """
    seen_hashes: Set[str] = set()
    seen_signatures: Set[str] = set()
    unique_jobs: List[JobData] = []
    duplicate_count = 0

    for job in jobs:
        h = url_hash(job.url)

        if h in seen_hashes:
            duplicate_count += 1
            continue

        sig = f"{normalize_text(job.title)}|{normalize_text(job.company)}"
        if sig in seen_signatures:
            duplicate_count += 1
            continue

        seen_hashes.add(h)
        seen_signatures.add(sig)
        unique_jobs.append(job)

    return unique_jobs, duplicate_count
