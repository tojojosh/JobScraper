"""
UK Skilled Jobs Portal – Main Application
==========================================
Run with:
    python app.py              # development server on port 5000
    gunicorn app:app -b 0.0.0.0:8000  # production
"""
import os
import json
import logging
from datetime import datetime

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import db, TargetCompany

# ── Logging ──────────────────────────────────────────────────────
os.makedirs(Config.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(Config.LOG_DIR, 'app.log'), encoding='utf-8'
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ── App Factory ──────────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure data directory exists
    os.makedirs(os.path.join(Config.BASE_DIR, 'data'), exist_ok=True)

    # Init database
    db.init_app(app)

    with app.app_context():
        db.create_all()
        _seed_target_companies(app)

    # Register blueprints
    from routes.api import api_bp
    from routes.views import views_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Start scheduler
    _start_scheduler(app)

    logger.info("UK Skilled Jobs Portal started")
    return app


# ── Seed target companies from JSON ─────────────────────────────
def _seed_target_companies(app: Flask):
    """Load target companies from the JSON file if the table is empty."""
    with app.app_context():
        if TargetCompany.query.count() > 0:
            return

        path = app.config['TARGET_COMPANIES_FILE']
        if not os.path.exists(path):
            logger.warning(f"Target companies file not found: {path}")
            return

        with open(path, 'r') as f:
            companies = json.load(f)

        for name in companies:
            db.session.add(TargetCompany(name=name.strip(), active=True))

        db.session.commit()
        logger.info(f"Seeded {len(companies)} target companies")


# ── Scheduler ────────────────────────────────────────────────────
def _start_scheduler(app: Flask):
    """Set up APScheduler for the daily scrape job."""
    scheduler = BackgroundScheduler(daemon=True)

    def daily_scrape():
        logger.info("Scheduler: starting daily scrape")
        try:
            from scraper.engine import ScrapingEngine
            engine = ScrapingEngine(app)
            result = engine.run()
            logger.info(f"Scheduler: daily scrape result – {result}")
        except Exception as e:
            logger.error(f"Scheduler: daily scrape failed – {e}", exc_info=True)

    hour = app.config.get('SCRAPE_HOUR', 6)
    minute = app.config.get('SCRAPE_MINUTE', 0)

    scheduler.add_job(
        daily_scrape,
        trigger='cron',
        hour=hour,
        minute=minute,
        id='daily_scrape',
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info(f"Scheduler started – daily scrape at {hour:02d}:{minute:02d}")


# ── Entry Point ──────────────────────────────────────────────────
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050, use_reloader=False)
