"""
scrape_generic.py — Scraper for open/non-protected sites.

Uses standard requests + BeautifulSoup (no headless browser needed).
Supports per-site profiles. Falls back to a heuristic parser.
"""

import logging
import re
import time
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

PAGE_DELAY = 1.5
MAX_PAGES  = 10

# ── Per-site selector profiles ────────────────────────────────────────────
# Add a new entry here when adding a new open site to URL.txt.
SITE_PROFILES = {
    "schmidysmachinery.com": {
        "site_name": "SchmidysMachinery",
        "card":     [".inventory-item", "article.vehicle", ".unit-listing",
                     ".listing-item", "div[class*='inventory']", "li[class*='unit']"],
        "title":    ["h2.title a", "h3.title a", ".vehicle-title a",
                     ".unit-name a", "h2 a", "h3 a"],
        "price":    [".asking-price", ".price", "span[class*='price']",
                     "div[class*='price']"],
        "location": [".location", ".city-state", "span[class*='location']"],
        "condition":["span[class*='condition']", ".condition",
                     "li[class*='condition']"],
        "miles":    [".mileage", ".miles", "span[class*='mile']"],
        "hours":    [".hours", "span[class*='hour']"],
        "next_page":["a[rel='next']", "a.next", "a[class*='next'][href]",
                     ".pagination a:last-child"],
    },
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class GenericScraper:
    def __init__(self, start_url: str):
        self.start_url = start_url
        parsed = urlparse(start_url)
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.hostname = parsed.hostname or ""
        self.profile = next(
            (v for k, v in SITE_PROFILES.items() if k in self.hostname),
            None,
        )
        self.site_name = (self.profile or {}).get("site_name", self.hostname)

    def scrape(self) -> list:
        session = requests.Session()
        session.headers["User-Agent"] = UA

        listings = []
        current_url = self.start_url
        page_num = 1

        while current_url and page_num <= MAX_PAGES:
            log.info(f"  [{self.site_name}] Page {page_num}: {current_url}")
            try:
                resp = session.get(current_url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                log.error(f"  Request failed: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")

            if self.profile:
                page_listings = self._profile_parse(soup, current_url)
            else:
                log.warning(
                    f"  No profile for '{self.hostname}' — "
                    "using heuristic parser (results may be incomplete)"
                )
                page_listings = self._heuristic_parse(soup, current_url)

            listings.extend(page_listings)
            log.info(f"    → {len(page_listings)} listings")

            # Next page
            next_url = None
            for sel in (self.profile or {}).get("next_page", ["a[rel='next']"]):
                el = soup.select_one(sel)
                if el and el.get("href"):
                    next_url = urljoin(self.base_url, el["href"])
                    break

            current_url = next_url
            page_num += 1
            if current_url:
                time.sleep(PAGE_DELAY)

        return listings

    # ── Profile-based parse ────────────────────────────────────────────────

    def _profile_parse(self, soup, page_url: str) -> list:
        cards = []
        for sel in self.profile["card"]:
            cards = soup.select(sel)
            if cards:
                break

        if not cards:
            log.warning(f"  No cards found at {page_url} with profile selectors")
            return []

        listings = []
        for card in cards:
            listing = self._extract_profile(card)
            if listing:
                listings.append(listing)
        return listings

    def _extract_profile(self, card) -> dict | None:
        p = self.profile

        # Title + URL
        title_el = _first(card, p["title"])
        if not title_el:
            return None
        raw_title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        source_url = urljoin(self.base_url, href) if href else ""

        # Year from title
        year = 0
        m = re.search(r"\b(19|20)\d{2}\b", raw_title)
        if m:
            year = int(m.group())
        model = re.sub(r"^\s*\d{4}\s*", "", raw_title).strip()

        # Price
        price = None
        price_str = "Call for Price"
        price_el = _first(card, p["price"])
        if price_el:
            digits = re.sub(r"[^\d]", "", price_el.get_text(strip=True))
            if digits and len(digits) >= 4:
                price = int(digits)
                price_str = f"${price:,}"

        # Mileage / hours
        miles = ""
        hours = ""
        miles_el = _first(card, p.get("miles", []))
        hours_el = _first(card, p.get("hours", []))
        if miles_el:
            d = re.sub(r"[^\d,]", "", miles_el.get_text(strip=True))
            if d:
                miles = d + " mi"
        if hours_el:
            d = re.sub(r"[^\d,]", "", hours_el.get_text(strip=True))
            if d:
                hours = d + " hrs"
        mi = " / ".join(x for x in [miles, hours] if x) or "—"

        # Location
        loc = ""
        loc_el = _first(card, p.get("location", []))
        if loc_el:
            loc = re.sub(r"\s+", " ", loc_el.get_text(strip=True))

        # Condition
        cond = "Used"
        cond_el = _first(card, p.get("condition", []))
        if cond_el and "new" in cond_el.get_text().lower():
            cond = "New"

        return {
            "cond":        cond,
            "year":        year,
            "model":       model,
            "chassis":     "",
            "spec":        "",
            "subcat":      "",
            "price":       price,
            "priceStr":    price_str,
            "mi":          mi,
            "status":      "avail" if price else "call",
            "loc":         loc,
            "source_url":  source_url,
            "source_site": self.site_name,
        }

    # ── Heuristic parse (unknown sites) ───────────────────────────────────

    def _heuristic_parse(self, soup, page_url: str) -> list:
        """
        Best-effort extraction for sites with no defined profile.
        Looks for price patterns ($XX,XXX) and nearby title/year text.
        Returns minimal listing objects.
        """
        listings = []
        price_pattern = re.compile(r"\$[\d,]{4,}")

        for el in soup.find_all(string=price_pattern):
            parent = el.parent
            if not parent:
                continue
            container = parent
            for _ in range(4):   # Walk up to find a container with a title link
                if container.find("a"):
                    break
                container = container.parent
                if not container:
                    break

            if not container:
                continue

            link = container.find("a", href=True)
            if not link:
                continue

            text = link.get_text(strip=True)
            href = urljoin(self.base_url, link["href"])
            year_m = re.search(r"\b(19|20)\d{2}\b", text)
            year = int(year_m.group()) if year_m else 0
            model = re.sub(r"^\s*\d{4}\s*", "", text).strip()

            price_m = price_pattern.search(el)
            price_str = price_m.group() if price_m else "—"
            digits = re.sub(r"[^\d]", "", price_str)
            price = int(digits) if digits else None

            listings.append({
                "cond":        "Used",
                "year":        year,
                "model":       model or text,
                "chassis":     "",
                "spec":        "",
                "subcat":      "",
                "price":       price,
                "priceStr":    price_str if price else "Call for Price",
                "mi":          "—",
                "status":      "avail" if price else "call",
                "loc":         "",
                "source_url":  href,
                "source_site": self.site_name,
            })

        return listings


def _first(element, selectors: list):
    for sel in selectors:
        try:
            found = element.select_one(sel)
            if found:
                return found
        except Exception:
            continue
    return None
