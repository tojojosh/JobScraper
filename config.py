"""Application configuration."""
import os


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(BASE_DIR, "data", "jobs.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'uk-job-scraper-dev-key-change-in-production')

    # Scraper schedule (24-hour format)
    SCRAPE_HOUR = int(os.environ.get('SCRAPE_HOUR', '6'))
    SCRAPE_MINUTE = int(os.environ.get('SCRAPE_MINUTE', '0'))

    # Scraper behavior
    REQUEST_DELAY_MIN = float(os.environ.get('REQUEST_DELAY_MIN', '1.5'))
    REQUEST_DELAY_MAX = float(os.environ.get('REQUEST_DELAY_MAX', '4.0'))
    MAX_PAGES_PER_SOURCE = int(os.environ.get('MAX_PAGES_PER_SOURCE', '10'))
    MAX_RESULTS_PER_COMPANY = int(os.environ.get('MAX_RESULTS_PER_COMPANY', '50'))

    # API Keys (optional – enables additional sources)
    ADZUNA_APP_ID = os.environ.get('ADZUNA_APP_ID', '')
    ADZUNA_API_KEY = os.environ.get('ADZUNA_API_KEY', '')
    REED_API_KEY = os.environ.get('REED_API_KEY', '')

    # Data paths
    TARGET_COMPANIES_FILE = os.path.join(BASE_DIR, 'data', 'target_companies.json')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')

    # Pagination
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200
