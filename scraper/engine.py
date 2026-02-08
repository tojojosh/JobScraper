"""Main scraping orchestrator – coordinates sources, dedup, and storage."""
import logging
import json
from datetime import date, datetime
from typing import List, Optional

from .sources.base import JobData
from .sources.google_search import GoogleSearchSource
from .sources.themuse import TheMuseSource
from .sources.devitjobs import DevITJobsSource
from .sources.jobicy import JobicySource
from .sources.workingnomads import WorkingNomadsSource
from .sources.adzuna import AdzunaSource
from .sources.reed import ReedSource
from .sources.remotive import RemotiveSource
from .sources.career_pages import CareerPageSource
from .dedup import deduplicate_jobs, url_hash

logger = logging.getLogger(__name__)

# General discovery queries – used by Google Search (primary) and API sources
GENERAL_QUERIES = [
    'software engineer UK',
    'data scientist UK',
    'data engineer UK',
    'product manager UK',
    'business analyst UK',
    'DevOps engineer UK',
    'machine learning engineer UK',
    'cybersecurity analyst UK',
    'finance analyst UK',
    'management consultant UK',
    'mechanical engineer UK',
    'electrical engineer UK',
    'civil engineer UK',
    'project manager UK',
    'UX designer UK',
    'cloud architect UK',
    'quantitative analyst UK',
    'solicitor UK',
    'actuary UK',
    'biomedical scientist UK',
]


class ScrapingEngine:
    """Runs a full scrape cycle: fetch → filter → dedup → store."""

    def __init__(self, app):
        self.app = app
        self.config = {
            'ADZUNA_APP_ID': app.config.get('ADZUNA_APP_ID', ''),
            'ADZUNA_API_KEY': app.config.get('ADZUNA_API_KEY', ''),
            'REED_API_KEY': app.config.get('REED_API_KEY', ''),
            'REQUEST_DELAY_MIN': app.config.get('REQUEST_DELAY_MIN', 1.5),
            'REQUEST_DELAY_MAX': app.config.get('REQUEST_DELAY_MAX', 4.0),
            'MAX_PAGES_PER_SOURCE': app.config.get('MAX_PAGES_PER_SOURCE', 5),
            'MAX_RESULTS_PER_COMPANY': app.config.get('MAX_RESULTS_PER_COMPANY', 50),
        }

        # Sources ordered by expected yield (highest first).
        # All free sources run first, then API-key sources.
        self.sources = [
            DevITJobsSource(self.config),       # Free: 3,400+ UK tech jobs w/ salary
            TheMuseSource(self.config),         # Free: hundreds of UK jobs
            GoogleSearchSource(self.config),    # Free: web search via DuckDuckGo
            JobicySource(self.config),          # Free: remote jobs, ~12 UK-eligible
            WorkingNomadsSource(self.config),   # Free: curated remote listings
            RemotiveSource(self.config),         # Free: remote jobs open to UK
            AdzunaSource(self.config),          # UK job API (needs free key)
            ReedSource(self.config),            # UK job API (needs free key)
        ]

        # Career page scraper (runs separately with career URLs)
        self.career_page_source = CareerPageSource(self.config)

    # ------------------------------------------------------------------
    def run(self, target_date: Optional[date] = None) -> dict:
        """Execute a full scraping run for *target_date* (defaults to today)."""
        from models import db, Job, TargetCompany, ScrapeRun

        if target_date is None:
            target_date = date.today()

        logger.info(f"=== Starting scrape run for {target_date} ===")

        with self.app.app_context():
            # Create a run record
            run = ScrapeRun(
                run_date=target_date,
                status='running',
                started_at=datetime.utcnow(),
            )
            db.session.add(run)
            db.session.commit()

            try:
                # Load target companies (names + career URLs)
                target_rows = TargetCompany.query.filter_by(active=True).all()
                companies = [c.name for c in target_rows]
                company_urls = [
                    {'name': c.name, 'career_url': c.career_url}
                    for c in target_rows
                    if c.career_url
                ]
                logger.info(
                    f"Loaded {len(companies)} target companies "
                    f"({len(company_urls)} with career URLs)"
                )

                # ---- Scrape from all available sources ----
                all_jobs: List[JobData] = []
                failed_sources = 0

                for source in self.sources:
                    if not source.is_available():
                        logger.info(
                            f"Source '{source.name}' skipped (not configured)"
                        )
                        continue

                    try:
                        logger.info(f"Scraping source: {source.name}")
                        source_jobs = source.scrape(companies, GENERAL_QUERIES)
                        logger.info(
                            f"Source '{source.name}' returned "
                            f"{len(source_jobs)} raw jobs"
                        )
                        all_jobs.extend(source_jobs)
                    except Exception as e:
                        logger.error(f"Source '{source.name}' failed: {e}")
                        failed_sources += 1

                # ---- Scrape company career pages ----
                if company_urls:
                    try:
                        logger.info(
                            f"Scraping {len(company_urls)} company career pages"
                        )
                        career_jobs = self.career_page_source.scrape_career_pages(
                            company_urls
                        )
                        logger.info(
                            f"Career pages returned {len(career_jobs)} raw jobs"
                        )
                        all_jobs.extend(career_jobs)
                    except Exception as e:
                        logger.error(f"Career page source failed: {e}")
                        failed_sources += 1

                # ---- Filter UK-only ----
                uk_jobs = [j for j in all_jobs if j.is_uk_based()]
                logger.info(
                    f"UK filter: {len(uk_jobs)} kept from {len(all_jobs)} total"
                )

                # ---- Deduplicate within batch ----
                unique_jobs, batch_dupes = deduplicate_jobs(uk_jobs)
                logger.info(
                    f"Batch dedup: {len(unique_jobs)} unique, "
                    f"{batch_dupes} duplicates removed"
                )

                # ---- Store in database ----
                new_count = 0
                cross_day_dupes = 0

                for job_data in unique_jobs:
                    h = url_hash(job_data.url)

                    # Already stored for this date?
                    existing_today = Job.query.filter_by(
                        url_hash=h, scrape_date=target_date
                    ).first()
                    if existing_today:
                        cross_day_dupes += 1
                        continue

                    # Seen on a previous day?
                    existing_prev = (
                        Job.query.filter_by(url_hash=h)
                        .order_by(Job.scrape_date.desc())
                        .first()
                    )
                    first_seen = (
                        existing_prev.first_seen_date
                        if existing_prev
                        else target_date
                    )
                    if existing_prev:
                        existing_prev.last_seen_date = target_date

                    new_job = Job(
                        title=job_data.title,
                        company=job_data.company,
                        location=job_data.location,
                        category=job_data.category,
                        experience_level=job_data.experience_level,
                        job_type=job_data.job_type,
                        salary=job_data.salary,
                        url=job_data.url,
                        url_hash=h,
                        source=job_data.source,
                        scrape_date=target_date,
                        first_seen_date=first_seen,
                        last_seen_date=target_date,
                    )
                    db.session.add(new_job)
                    new_count += 1

                db.session.commit()

                # ---- Update run record ----
                run.status = 'completed'
                run.jobs_found = len(all_jobs)
                run.new_jobs = new_count
                run.duplicates = batch_dupes + cross_day_dupes
                run.failed_sources = failed_sources
                run.completed_at = datetime.utcnow()
                run.log = json.dumps({
                    'total_scraped': len(all_jobs),
                    'uk_filtered': len(uk_jobs),
                    'batch_deduped': len(unique_jobs),
                    'new_stored': new_count,
                    'cross_day_dupes': cross_day_dupes,
                    'failed_sources': failed_sources,
                })
                db.session.commit()

                result = {
                    'status': 'completed',
                    'date': target_date.isoformat(),
                    'jobs_found': len(all_jobs),
                    'new_jobs': new_count,
                    'duplicates': batch_dupes + cross_day_dupes,
                    'failed_sources': failed_sources,
                }
                logger.info(f"=== Scrape run completed: {result} ===")
                return result

            except Exception as e:
                logger.error(f"Scrape run failed: {e}", exc_info=True)
                run.status = 'failed'
                run.completed_at = datetime.utcnow()
                run.log = str(e)
                db.session.commit()
                return {
                    'status': 'failed',
                    'error': str(e),
                    'date': target_date.isoformat(),
                }
