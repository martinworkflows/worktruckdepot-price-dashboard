"""
scrape_trader.py — Scraper for the Trader Interactive network.

Covers: MachineryTrader.com, ForestryTrader.com, TreeTrader.com, CraneTrader.com
All share the same parent company and HTML structure.

Bot protection: Reese/Distil JS challenge wall.
Tier 1 — Playwright headless Chromium (recommended, handles challenge automatically)
Tier 2 — Saved cookie file (if Playwright not installed)
Tier 3 — Graceful skip with clear log message
"""

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

COOKIE_FILE = Path(__file__).parent / "trader_cookies.json"
COOKIE_MAX_AGE_HOURS = 6
MAX_PAGES = 25       # safety cap per URL
PAGE_DELAY = 2.0     # polite seconds between pages

SITE_DISPLAY_NAMES = {
    "machinerytrader.com": "MachineryTrader",
    "forestrytrader.com":  "ForestryTrader",
    "treetrader.com":      "TreeTrader",
    "cranetrader.com":     "CraneTrader",
}

# ── CSS selector fallback chains ──────────────────────────────────────────
# Try each in order; use the first that returns results.
SELECTORS = {
    "card": [
        "article.result-item",
        "div.result-item",
        "[data-listing-id]",
        "article[class*='listing']",
        "div[class*='result'][class*='item']",
        "li[class*='listing']",
    ],
    "title_link": [
        "a.result-title",
        "h2 a",
        "h3 a",
        "a[class*='title']",
        "a[href*='/listings/']",
    ],
    "price": [
        ".price-value",
        "span.price",
        "div.price",
        "[class*='price']:not([class*='call']):not([class*='contact'])",
        "span[class*='Price']",
    ],
    "price_unavailable": [
        ".price-call",
        "[class*='call-price']",
        "[class*='contact-for-price']",
        "span[class*='noPrice']",
    ],
    "condition": [
        "li.attribute-item:first-child .attribute-value",
        "[class*='condition'] [class*='value']",
        "span[class*='Condition']",
        "[data-label='Condition']",
    ],
    "location": [
        ".seller-location",
        ".result-location",
        "[class*='location']",
        "[class*='Location']",
    ],
    "hours": [
        "li[class*='hour'] .attribute-value",
        "[class*='hours'] [class*='value']",
        "[data-label='Hours']",
    ],
    "miles": [
        "li[class*='mile'] .attribute-value",
        "[class*='miles'] [class*='value']",
        "[data-label='Miles']",
    ],
    "year": [
        "li[class*='year'] .attribute-value",
        "[data-label='Year']",
        "[class*='year'] [class*='value']",
    ],
    "next_page": [
        "a[rel='next']",
        "a.pagination-next",
        "a[aria-label='Next page']",
        "a[aria-label='next']",
        "li.next a",
        "a[class*='next'][href]",
    ],
}


class TraderScraper:
    def __init__(self, start_url: str):
        self.start_url = start_url
        parsed = urlparse(start_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.hostname = parsed.hostname or ""
        self.site_name = next(
            (v for k, v in SITE_DISPLAY_NAMES.items() if k in self.hostname),
            self.hostname,
        )

    def scrape(self) -> list:
        # Tier 1: Playwright
        playwright_available = False
        try:
            import playwright  # noqa: F401
            playwright_available = True
        except ImportError:
            log.warning(
                f"Playwright not installed — trying cookie fallback for {self.site_name}.\n"
                "  Install: pip install playwright && python -m playwright install chromium"
            )

        if playwright_available:
            try:
                return self._scrape_playwright()
            except Exception as e:
                log.error(f"Playwright scrape failed for {self.site_name}: {e}")
                log.info("Falling back to cookie session...")

        # Tier 2: Cookie file
        cookies = self._load_cookies()
        if cookies:
            try:
                return self._scrape_with_cookies(cookies)
            except Exception as e:
                log.error(f"Cookie session failed for {self.site_name}: {e}")

        # Tier 3: Skip
        log.error(
            f"SKIPPED {self.site_name}: Neither Playwright nor valid cookies available.\n"
            f"  → Install Playwright: pip install playwright && "
            f"python -m playwright install chromium\n"
            f"  → OR manually export browser cookies to: {COOKIE_FILE}"
        )
        return []

    # ── Playwright path ────────────────────────────────────────────────────

    def _scrape_playwright(self) -> list:
        from playwright.sync_api import sync_playwright

        listings = []
        with sync_playwright() as p:
            # Run headed (visible browser) — headless mode is reliably detected
            # by Cloudflare/Distil/Reese and returns "Pardon Our Interruption".
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                timezone_id="America/Chicago",
            )
            page = ctx.new_page()

            # Apply stealth patches if available
            try:
                from playwright_stealth import Stealth
                Stealth().apply_stealth_sync(page)
                log.info("  Stealth mode applied")
            except ImportError:
                pass  # headed mode alone is usually sufficient

            current_url = self.start_url
            page_num = 1

            while current_url and page_num <= MAX_PAGES:
                log.info(f"  [{self.site_name}] Playwright page {page_num}: {current_url}")
                try:
                    page.goto(current_url, wait_until="domcontentloaded", timeout=60_000)
                except Exception as e:
                    log.warning(f"  Page {page_num} goto error: {e}")
                    break

                # Wait longer on first page — Cloudflare challenge can take a few seconds
                wait_secs = 8 if page_num == 1 else 3
                time.sleep(wait_secs)

                # Detect bot challenge page and abort early with clear message
                try:
                    title = page.title()
                    if "pardon" in title.lower() or "interruption" in title.lower() or "captcha" in title.lower():
                        log.error(
                            f"  [{self.site_name}] Bot challenge page detected ('{title}').\n"
                            f"  The browser window is open — if a CAPTCHA appeared, solve it manually.\n"
                            f"  Waiting 30 s for challenge to pass..."
                        )
                        time.sleep(30)
                        # Check again after waiting
                        title = page.title()
                        if "pardon" in title.lower() or "interruption" in title.lower():
                            log.error(f"  [{self.site_name}] Still blocked after wait — skipping.")
                            break
                except Exception:
                    pass

                # Wait for listing cards — try each selector individually
                found_cards = False
                for card_sel in SELECTORS["card"]:
                    try:
                        page.wait_for_selector(card_sel, timeout=10_000)
                        found_cards = True
                        log.info(f"  Cards found with selector: {card_sel}")
                        break
                    except Exception:
                        continue

                if not found_cards:
                    # Log a snippet of the page title/URL for debugging
                    try:
                        title = page.title()
                        final_url = page.url
                        log.warning(f"  No cards on page {page_num} — title: '{title}' url: {final_url}")
                    except Exception:
                        log.warning(f"  No listing cards found on page {page_num} — stopping")
                    break

                html = page.content()
                page_listings = self._parse_page_html(html, current_url)
                listings.extend(page_listings)
                log.info(f"  -> {len(page_listings)} listings on page {page_num}")

                # Next page — try CSS selectors first, then URL-based fallback
                next_url = None

                # Approach 1: CSS selector scan (broader set)
                broader_next_sels = SELECTORS["next_page"] + [
                    "a[data-page]",
                    "button[aria-label*='next' i]",
                    "a[href*='Page=']",
                    "nav a",
                    "[class*='paginat'] a",
                    "[class*='Paginat'] a",
                ]
                for sel in broader_next_sels:
                    try:
                        els = page.query_selector_all(sel)
                        for el in els:
                            href = el.get_attribute("href") or ""
                            aria = (el.get_attribute("aria-label") or "").lower()
                            text = (el.inner_text() or "").strip().lower()
                            # Accept if it looks like a forward/next link
                            if (
                                "next" in aria
                                or text in (">", "›", "next", "»")
                                or re.search(r"[Pp]age=" + str(page_num + 1), href)
                            ):
                                next_url = urljoin(self.base_url, href) if href else None
                                break
                        if next_url:
                            break
                    except Exception:
                        continue

                # Approach 2: URL-based pagination — Trader Interactive uses ?Page=N
                if not next_url:
                    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                    parsed = urlparse(current_url if page_num == 1 else self.start_url)
                    qs = parse_qs(parsed.query, keep_blank_values=True)
                    # Check if there's a next-page indicator in the HTML
                    try:
                        html_check = page.content()
                        next_page_num = page_num + 1
                        # If the page HTML references the next page number at all, go there
                        if (
                            f"Page={next_page_num}" in html_check
                            or f"page={next_page_num}" in html_check
                            or f'"page":{next_page_num}' in html_check
                            or f"page-{next_page_num}" in html_check
                        ):
                            qs["Page"] = [str(next_page_num)]
                            new_query = urlencode(qs, doseq=True)
                            next_url = urlunparse(parsed._replace(query=new_query))
                            log.info(f"  URL-based pagination → {next_url}")
                    except Exception:
                        pass

                if not next_url:
                    log.info(f"  No next page found after page {page_num} — done with this URL.")

                current_url = next_url
                page_num += 1
                if current_url:
                    time.sleep(PAGE_DELAY)

            # Save cookies for Tier 2 fallback
            storage = ctx.storage_state()
            _save_cookies(storage.get("cookies", []), self.hostname)

            browser.close()

        return listings

    # ── Cookie-session path ───────────────────────────────────────────────

    def _scrape_with_cookies(self, cookies: list) -> list:
        import requests
        from bs4 import BeautifulSoup

        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        for ck in cookies:
            session.cookies.set(ck["name"], ck["value"], domain=ck.get("domain", ""))

        listings = []
        current_url = self.start_url
        page_num = 1

        while current_url and page_num <= MAX_PAGES:
            log.info(f"  [{self.site_name}] Cookie session page {page_num}: {current_url}")
            resp = session.get(current_url, timeout=20)

            if "Pardon Our Interruption" in resp.text or "distil_r_captcha" in resp.text:
                log.error(f"  Bot challenge detected — cookies may be expired")
                break

            page_listings = self._parse_page_html(resp.text, current_url)
            listings.extend(page_listings)
            log.info(f"    → {len(page_listings)} listings")

            # Find next page from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            next_url = None
            for sel in SELECTORS["next_page"]:
                el = soup.select_one(sel)
                if el and el.get("href"):
                    next_url = urljoin(self.base_url, el["href"])
                    break

            current_url = next_url
            page_num += 1
            if current_url:
                time.sleep(PAGE_DELAY)

        return listings

    # ── HTML parsing ──────────────────────────────────────────────────────

    def _parse_page_html(self, html: str, page_url: str) -> list:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Find listing cards using fallback chain
        cards = []
        matched_sel = None
        for sel in SELECTORS["card"]:
            cards = soup.select(sel)
            if cards:
                matched_sel = sel
                break

        if not cards:
            # Log page structure hint for debugging selector drift
            classes = [
                " ".join(el.get("class", []))
                for el in soup.find_all(True, limit=60)
                if el.get("class")
            ]
            log.warning(
                f"  No listing cards found on {page_url}\n"
                f"  Selector drift? Page classes sample: {' | '.join(classes[:20])}"
            )
            return []

        log.debug(f"  Card selector '{matched_sel}' → {len(cards)} cards")

        listings = []
        for card in cards:
            try:
                listing = self._extract_listing(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                log.debug(f"  Skipped card: {e}")

        return listings

    def _extract_listing(self, card) -> dict | None:
        # ── Title + URL ──────────────────────────────────────────────────
        title_el = _first_match(card, SELECTORS["title_link"])
        if not title_el:
            return None

        raw_title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        source_url = urljoin(self.base_url, href) if href else ""

        # ── Year ─────────────────────────────────────────────────────────
        # Try dedicated selector first, then parse from title
        year = 0
        year_el = _first_match(card, SELECTORS["year"])
        if year_el:
            m = re.search(r"\b(19|20)\d{2}\b", year_el.get_text())
            if m:
                year = int(m.group())
        if not year:
            m = re.search(r"\b(19|20)\d{2}\b", raw_title)
            if m:
                year = int(m.group())

        # ── Model (title minus leading year) ─────────────────────────────
        model = re.sub(r"^\s*\d{4}\s*", "", raw_title).strip()

        # ── Price ─────────────────────────────────────────────────────────
        price = None
        price_str = "Call for Price"

        price_el = _first_match(card, SELECTORS["price"])
        if price_el:
            text = price_el.get_text(strip=True)
            # Extract digits only (handles "$124,500" → 124500)
            digits = re.sub(r"[^\d]", "", text)
            if digits and len(digits) >= 4:
                price = int(digits)
                price_str = f"${price:,}"

        # ── Status ────────────────────────────────────────────────────────
        status = "avail" if price else "call"

        # ── Mileage / Hours ───────────────────────────────────────────────
        hours = ""
        miles = ""
        hours_el = _first_match(card, SELECTORS["hours"])
        miles_el = _first_match(card, SELECTORS["miles"])
        if hours_el:
            h = re.sub(r"[^\d,]", "", hours_el.get_text(strip=True))
            if h:
                hours = h + " hrs"
        if miles_el:
            m_text = re.sub(r"[^\d,]", "", miles_el.get_text(strip=True))
            if m_text:
                miles = m_text + " mi"

        mi_parts = [p for p in [miles, hours] if p]
        mi = " / ".join(mi_parts) if mi_parts else "—"

        # ── Location ──────────────────────────────────────────────────────
        loc = ""
        loc_el = _first_match(card, SELECTORS["location"])
        if loc_el:
            loc = re.sub(r"\s+", " ", loc_el.get_text(strip=True))

        # ── Condition ─────────────────────────────────────────────────────
        cond = "Used"
        cond_el = _first_match(card, SELECTORS["condition"])
        if cond_el:
            if "new" in cond_el.get_text().lower():
                cond = "New"
        else:
            # Heuristic: if "New" appears before any "Used" in the card text
            card_text = card.get_text().lower()
            new_pos  = card_text.find("new")
            used_pos = card_text.find("used")
            if new_pos != -1 and (used_pos == -1 or new_pos < used_pos):
                cond = "New"

        return {
            "cond":        cond,
            "year":        year,
            "model":       model,
            "chassis":     "",       # Not available on results page
            "spec":        "",       # Filled by classify.py
            "subcat":      "",
            "price":       price,
            "priceStr":    price_str,
            "mi":          mi,
            "status":      status,
            "loc":         loc,
            "source_url":  source_url,
            "source_site": self.site_name,
        }

    def _load_cookies(self):
        return _load_cookies(self.hostname)


# ── Cookie helpers (module-level) ─────────────────────────────────────────

def _save_cookies(cookies: list, hostname: str) -> None:
    try:
        data = {"timestamp": time.time(), "site": hostname, "cookies": cookies}
        COOKIE_FILE.write_text(json.dumps(data), encoding="utf-8")
        log.info(f"  Saved {len(cookies)} cookies to {COOKIE_FILE.name}")
    except Exception as e:
        log.warning(f"  Could not save cookies: {e}")


def _load_cookies(hostname: str) -> list | None:
    if not COOKIE_FILE.exists():
        return None
    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        age_h = (time.time() - data.get("timestamp", 0)) / 3600
        if age_h > COOKIE_MAX_AGE_HOURS:
            log.warning(f"  Cookie file is {age_h:.1f}h old — too stale")
            return None
        if data.get("site") and hostname not in data["site"] and data["site"] not in hostname:
            log.warning(f"  Cookie file is for '{data['site']}', not '{hostname}' — skipping")
            return None
        return data.get("cookies", [])
    except Exception as e:
        log.warning(f"  Could not load cookies: {e}")
        return None


# ── Selector helper ────────────────────────────────────────────────────────

def _first_match(element, selectors: list):
    """Return the first child element matching any selector in the list."""
    for sel in selectors:
        try:
            found = element.select_one(sel)
            if found:
                return found
        except Exception:
            continue
    return None
