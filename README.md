# UK Skilled Jobs Portal

A web portal that **daily scrapes the web** for high-quality skilled jobs in the UK, stores results in a database, and provides a searchable/filterable table with CSV, Excel, and daily JSON exports.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python app.py
```

Open **http://localhost:5050** in your browser.

---

## Features

- **Daily scraping engine** with multiple job sources (Adzuna, Reed, Arbeitnow, Remotive, Indeed UK)
- **171 priority target companies** pre-loaded (configurable via `data/target_companies.json`)
- **Searchable & filterable table** with server-side pagination
- **Sort** by date, company, title, location
- **Date range filter** (defaults to last 7 days)
- **CSV and Excel exports** respecting current filters
- **Daily JSON download** per scrape date
- **Manual scrape trigger** from the UI
- **Automatic daily scrape** via APScheduler (default: 6:00 AM)
- **Deduplication** across and within days (URL hash + title/company similarity)
- **UK-only filtering** with intelligent location matching
- **Dark mode** toggle
- **Observability**: full logging with run statistics

---

## Data Sources

| Source | Type | API Key Required | Notes |
|--------|------|-----------------|-------|
| **Web Search** | Web scraping (DuckDuckGo) | No | **Primary source** – searches the entire web for UK job listings across all job boards, career pages, LinkedIn, etc. |
| **Adzuna** | REST API | Yes (free) | Excellent UK coverage. Register at [developer.adzuna.com](https://developer.adzuna.com/) |
| **Reed** | REST API | Yes (free) | UK-focused. Register at [reed.co.uk/developers](https://www.reed.co.uk/developers) |
| **Arbeitnow** | REST API | No | Global jobs, UK-eligible roles filtered |
| **Remotive** | REST API | No | Remote jobs accessible from UK |

The **Web Search** source is the primary scraper – it uses DuckDuckGo's search engine to discover UK job listings across the entire indexed web, including company career pages, LinkedIn, Indeed, Glassdoor, Reed, Totaljobs, and any other site. This means the scraper isn't limited to specific job boards.

> **Tip**: For the highest yield, also register for free Adzuna and Reed API keys. These provide structured, high-quality UK job data that complements the web search results.

---

## Configuration

### Environment Variables

Copy `.env.example` and set your values:

```bash
# API Keys (optional but recommended for best results)
ADZUNA_APP_ID=your_app_id
ADZUNA_API_KEY=your_api_key
REED_API_KEY=your_api_key

# Scrape schedule (24h, UTC)
SCRAPE_HOUR=6
SCRAPE_MINUTE=0

# Rate limiting
REQUEST_DELAY_MIN=1.5
REQUEST_DELAY_MAX=4.0
```

Export them before running:

```bash
export ADZUNA_APP_ID=xxx
export ADZUNA_API_KEY=yyy
export REED_API_KEY=zzz
python app.py
```

### Target Companies

The priority company list is stored in `data/target_companies.json`. Edit this file to add/remove companies — changes take effect on the next app restart.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | Paginated job list (supports `page`, `page_size`, `date_from`, `date_to`, `search`, `source`, `sort_by`, `sort_order`) |
| GET | `/api/jobs/export/csv` | Download filtered jobs as CSV |
| GET | `/api/jobs/export/excel` | Download filtered jobs as Excel (.xlsx) |
| GET | `/api/jobs/daily-json/<date>` | Download all jobs for a specific date as JSON |
| GET | `/api/stats` | Summary statistics for current filter |
| GET | `/api/dates` | List of scrape dates with job counts |
| GET | `/api/companies` | List of target companies |
| POST | `/api/scrape` | Trigger a manual scrape run |
| GET | `/api/scrape/status` | Status of the last scrape run |

---

## Project Structure

```
JobScraper/
├── app.py                          # Main Flask application + scheduler
├── config.py                       # Configuration
├── models.py                       # Database models (Job, TargetCompany, ScrapeRun)
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── data/
│   ├── target_companies.json       # Priority company list (editable)
│   └── jobs.db                     # SQLite database (auto-created)
├── scraper/
│   ├── engine.py                   # Scraping orchestrator
│   ├── dedup.py                    # Deduplication logic
│   └── sources/
│       ├── base.py                 # Abstract base + JobData model
│       ├── google_search.py        # Web search scraper (primary - scrapes the web)
│       ├── adzuna.py               # Adzuna API source
│       ├── reed.py                 # Reed API source
│       ├── arbeitnow.py            # Arbeitnow API source (free, no key)
│       └── remotive.py             # Remotive API source (free, no key)
├── routes/
│   ├── api.py                      # REST API endpoints
│   └── views.py                    # HTML page routes
├── templates/
│   └── index.html                  # Main portal template
├── static/
│   ├── css/style.css               # Custom styles
│   └── js/app.js                   # Frontend application
└── logs/
    └── app.log                     # Application logs
```

---

## Production Deployment

```bash
# Using gunicorn
gunicorn app:app -b 0.0.0.0:8000 -w 4

# Or with environment variables
SCRAPE_HOUR=6 ADZUNA_APP_ID=xxx ADZUNA_API_KEY=yyy gunicorn app:app -b 0.0.0.0:8000
```

---

## Adding New Scraper Sources

1. Create a new file in `scraper/sources/` (e.g., `my_source.py`)
2. Extend `BaseSource` and implement `is_available()` and `scrape()`
3. Import and add the source in `scraper/engine.py`

```python
from .sources.base import BaseSource, JobData

class MySource(BaseSource):
    name = "my_source"

    def is_available(self) -> bool:
        return True

    def scrape(self, companies, general_queries):
        jobs = []
        # ... fetch and parse jobs ...
        return jobs
```
