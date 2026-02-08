"""SQLAlchemy database models."""
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Job(db.Model):
    """Scraped job listing."""
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    company = db.Column(db.String(300), nullable=False)
    location = db.Column(db.String(300), nullable=False)
    category = db.Column(db.String(200), nullable=True)
    experience_level = db.Column(db.String(100), nullable=True)
    job_type = db.Column(db.String(100), nullable=True)
    salary = db.Column(db.String(200), nullable=True)
    url = db.Column(db.String(2000), nullable=False)
    url_hash = db.Column(db.String(64), nullable=False, index=True)
    source = db.Column(db.String(100), nullable=False)
    scrape_date = db.Column(db.Date, nullable=False, index=True)
    first_seen_date = db.Column(db.Date, nullable=False)
    last_seen_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('url_hash', 'scrape_date', name='uq_job_url_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'category': self.category,
            'experience_level': self.experience_level,
            'job_type': self.job_type,
            'salary': self.salary,
            'url': self.url,
            'source': self.source,
            'scrape_date': self.scrape_date.isoformat(),
            'first_seen_date': self.first_seen_date.isoformat(),
            'last_seen_date': self.last_seen_date.isoformat(),
        }

    def to_json_export(self):
        return {
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'category': self.category,
            'experience_level': self.experience_level,
            'job_type': self.job_type,
            'salary': self.salary,
            'url': self.url,
        }


class TargetCompany(db.Model):
    """Priority company for scraping."""
    __tablename__ = 'target_companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False, unique=True)
    career_url = db.Column(db.String(2000), nullable=True)
    active = db.Column(db.Boolean, default=True)


class ScrapeRun(db.Model):
    """Record of a scraping run."""
    __tablename__ = 'scrape_runs'

    id = db.Column(db.Integer, primary_key=True)
    run_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='running')
    jobs_found = db.Column(db.Integer, default=0)
    new_jobs = db.Column(db.Integer, default=0)
    duplicates = db.Column(db.Integer, default=0)
    failed_sources = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    log = db.Column(db.Text, nullable=True)
