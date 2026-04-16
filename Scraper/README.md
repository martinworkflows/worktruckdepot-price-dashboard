# Work Truck Depot — Market Intelligence Scraper

Weekly scraper that pulls equipment listings from competitor/marketplace sites and builds a self-contained HTML dashboard.

---

## Folder structure

```
Work Truck Depot/
├── Pricing URL/
│   └── URL.txt                  ← one URL per line to scrape
├── Dashboard Format/
│   └── dashboard_template.html  ← HTML template with {{MARKERS}}
├── Scraper/
│   ├── scrape.py                ← main orchestrator (run this)
│   ├── scrape_trader.py         ← Playwright handler for Trader Interactive sites
│   ├── scrape_generic.py        ← requests+BS4 handler for open sites
│   ├── classify.py              ← maps listings to categories (bucket/digger/crane/etc.)
│   ├── inject.py                ← injects scraped data into the template
│   ├── requirements.txt         ← Python dependencies
│   ├── trader_cookies.json      ← saved browser cookies (auto-created, max 6h old)
│   ├── last_scrape_data.json    ← raw listing cache from last run
│   └── scrape.log               ← run log (auto-rotates at 5 MB)
├── multi_source_dashboard.html  ← OUTPUT — overwritten on every run
└── run_scraper.bat              ← double-click to run manually
```

---

## One-time setup (already done)

```
pip install -r Scraper\requirements.txt
python -m playwright install chromium
```

---

## Running the scraper

**Option A — Double-click:**
`run_scraper.bat` (opens dashboard automatically when done)

**Option B — Terminal:**
```
cd "C:\Users\marti\Desktop\Work\Work Truck Depot\Scraper"
python scrape.py
```

Output: `multi_source_dashboard.html` in the root Work Truck Depot folder.

---

## Current status / known issue

**MachineryTrader, ForestryTrader, TreeTrader, CraneTrader** are all Trader Interactive sites protected by **Reese/Distil bot detection**. Automated headless browsers are blocked with a "Pardon Our Interruption" page.

### Workaround: manual cookie handoff

1. Open Chrome and visit machinerytrader.com — browse normally until listings load
2. Install the **Cookie-Editor** Chrome extension (free)
3. On machinerytrader.com: click Cookie-Editor → Export → Copy All (JSON format)
4. Create/overwrite the file `Scraper\trader_cookies.json` with this content:
   ```json
   {
     "timestamp": <paste a Unix timestamp here — use https://www.unixtimestamp.com>,
     "site": "machinerytrader.com",
     "cookies": [ ...paste the exported cookie array here... ]
   }
   ```
5. Run the scraper within 6 hours — it will use your real browser session

### Alternative: switch to sites without bot protection

The next planned step is to replace the 5 blocked URLs in `Pricing URL/URL.txt` with accessible alternatives such as:
- TruckPaper.com
- CommercialTruckTrader.com
- IronPlanet.com

Ask Claude to "test and replace the blocked URLs with working alternatives" to continue from here.

---

## Adding new sites

1. Add the URL to `Pricing URL/URL.txt` (one per line, `#` for comments)
2. If it's a Trader Interactive site → handled automatically by `scrape_trader.py`
3. If it's a new open site → add a selector profile to `SITE_PROFILES` in `scrape_generic.py`
4. If needed, update keyword lists in `classify.py` to map new equipment types to categories

---

## Weekly scheduling (optional)

Run once as Administrator in cmd:
```
schtasks /create /tn "WTD Market Scraper" /tr "C:\Users\marti\Desktop\Work\Work Truck Depot\run_scraper.bat" /sc WEEKLY /d MON /st 06:00 /ru SYSTEM /rl HIGHEST /f
```
Or configure manually in Task Scheduler (`taskschd.msc`): Weekly, Monday 6 AM.

---

## Dashboard categories

| Tab | Keywords matched |
|-----|-----------------|
| Bucket | bucket truck, aerial lift, boom truck, articulating |
| Digger | digger derrick, auger, pole setter |
| Forest | forestry, chipper, mulcher, log, stump |
| Crane | crane, picker, boom crane |
| Pull | pull truck, wrecker, rotator, rollback |
| Other | anything not matched above |
