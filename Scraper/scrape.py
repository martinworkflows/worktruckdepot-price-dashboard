"""
scrape.py — Work Truck Depot: Weekly Market Intelligence Scraper
================================================================
Reads URLs from:  ../Pricing URL/URL.txt
Template:         ../Dashboard Format/dashboard_template.html
Output:           ../multi_source_dashboard.html
Log:              scrape.log (in this directory)

Run manually:     python scrape.py
Scheduled:        via run_scraper.bat + Windows Task Scheduler
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ── Paths ─────────────────────────────────────────────────────────────────
THIS_DIR  = Path(__file__).parent
BASE_DIR  = THIS_DIR.parent
URL_FILE  = BASE_DIR / "Pricing URL" / "URL.txt"
TEMPLATE  = BASE_DIR / "Dashboard Format" / "dashboard_template.html"
OUTPUT    = BASE_DIR / "multi_source_dashboard.html"
LOG_FILE  = THIS_DIR / "scrape.log"
CACHE     = THIS_DIR / "last_scrape_data.json"

# ── Log rotation (keep file under 5 MB) ──────────────────────────────────
if LOG_FILE.exists() and LOG_FILE.stat().st_size > 5 * 1024 * 1024:
    LOG_FILE.rename(LOG_FILE.with_suffix(".log.1"))

# ── Logging setup ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)),
    ],
)
log = logging.getLogger(__name__)

# ── Site routing ──────────────────────────────────────────────────────────
TRADER_SITES = {
    "machinerytrader.com",
    "forestrytrader.com",
    "treetrader.com",
    "cranetrader.com",
}


def detect_scraper(url: str):
    host = urlparse(url).hostname or ""
    if any(site in host for site in TRADER_SITES):
        from scrape_trader import TraderScraper
        return TraderScraper(url)
    else:
        from scrape_generic import GenericScraper
        return GenericScraper(url)


def read_urls(path: Path) -> list:
    if not path.exists():
        log.error(f"URL file not found: {path}")
        return []
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main():
    log.info("=" * 60)
    log.info("Work Truck Depot — Market Intelligence Scraper")
    log.info(f"Run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    # ── Validate template ─────────────────────────────────────────────────
    if not TEMPLATE.exists():
        log.critical(f"Dashboard template not found: {TEMPLATE}")
        log.critical("Run setup: ensure dashboard_template.html exists in 'Dashboard Format/'")
        sys.exit(1)

    # ── Read URLs ─────────────────────────────────────────────────────────
    urls = read_urls(URL_FILE)
    if not urls:
        log.error("No URLs found in URL.txt — nothing to scrape.")
        sys.exit(1)
    log.info(f"URLs to scrape: {len(urls)}")

    # ── Scrape each URL ───────────────────────────────────────────────────
    all_listings = []
    errors = []
    sources_found = set()

    for url in urls:
        scraper = detect_scraper(url)
        log.info(f"\nScraping: {url}")
        try:
            listings = scraper.scrape()
            log.info(f"  OK: {len(listings)} listings from {scraper.site_name}")
            all_listings.extend(listings)
            if listings:
                sources_found.add(scraper.site_name)
        except Exception as e:
            log.error(f"  ✗ FAILED — {e}")
            errors.append({"url": url, "error": str(e)})

    log.info(f"\nTotal listings scraped: {len(all_listings)}")
    log.info(f"Sources with data:      {', '.join(sorted(sources_found)) or 'none'}")
    log.info(f"Errors:                 {len(errors)}")

    # ── Categorize ────────────────────────────────────────────────────────
    from classify import categorize_all
    data_by_category = categorize_all(all_listings)

    for cat, items in data_by_category.items():
        if items:
            log.info(f"  {cat:10s}: {len(items)} listings")

    # ── Save debug cache ──────────────────────────────────────────────────
    try:
        CACHE.write_text(
            json.dumps(all_listings, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning(f"Could not write cache: {e}")

    # ── Inject into template ──────────────────────────────────────────────
    from inject import build_dashboard

    scrape_meta = {
        "date":    datetime.now().strftime("%B %d, %Y"),
        "total":   len(all_listings),
        "errors":  errors,
        "sources": sorted(sources_found),
    }

    try:
        build_dashboard(
            template_path=TEMPLATE,
            output_path=OUTPUT,
            data=data_by_category,
            scrape_meta=scrape_meta,
        )
        log.info(f"\nDashboard written: {OUTPUT}")
    except Exception as e:
        log.critical(f"Failed to write dashboard: {e}")
        sys.exit(1)

    # ── Save history snapshot ─────────────────────────────────────────────
    try:
        from build_insights import save_snapshot, build_insights
        snap_path = save_snapshot(all_listings, data_by_category)
        log.info(f"History snapshot saved: {snap_path.name}")
    except Exception as e:
        log.warning(f"Could not save history snapshot: {e}")

    # ── Build insights dashboard ──────────────────────────────────────────
    try:
        build_insights(all_listings=all_listings, data_by_category=data_by_category)
        log.info(f"Insights dashboard written: {BASE_DIR / 'insights_dashboard.html'}")
    except Exception as e:
        log.warning(f"Could not build insights dashboard: {e}")

    log.info("=" * 60)
    log.info("Run complete.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
