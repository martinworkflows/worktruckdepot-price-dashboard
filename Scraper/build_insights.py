"""
build_insights.py — Builds insights_dashboard.html from scraped data + history.

Called automatically by scrape.py after each run, or manually:
  python build_insights.py
"""

import json
import statistics
from datetime import datetime
from pathlib import Path

THIS_DIR    = Path(__file__).parent
BASE_DIR    = THIS_DIR.parent
CACHE       = THIS_DIR / "last_scrape_data.json"
HISTORY_DIR = THIS_DIR / "history"
OUTPUT      = BASE_DIR / "insights_dashboard.html"

CATEGORIES = ["bucket", "digger", "forest", "crane", "pull", "other"]
CAT_LABELS = {
    "bucket": "Bucket Trucks",
    "digger": "Digger Derricks",
    "forest": "Forestry",
    "crane":  "Crane & Grapple",
    "pull":   "Pulling & Tensioning",
    "other":  "Other",
}
CAT_COLORS = {
    "bucket": "#122463",
    "digger": "#1A3182",
    "forest": "#2E7D32",
    "crane":  "#BF360C",
    "pull":   "#6A1B9A",
    "other":  "#546E7A",
}


# ── Stats helpers ──────────────────────────────────────────────────────────────

def price_stats(prices: list) -> dict:
    if not prices:
        return {"count": 0, "min": 0, "max": 0, "avg": 0, "median": 0, "p25": 0, "p75": 0}
    s = sorted(prices)
    n = len(s)
    return {
        "count":  n,
        "min":    s[0],
        "max":    s[-1],
        "avg":    round(statistics.mean(s)),
        "median": round(statistics.median(s)),
        "p25":    s[max(0, n // 4 - 1)],
        "p75":    s[min(n - 1, (3 * n) // 4)],
    }


def bucket_prices(prices: list, buckets: list) -> list:
    """Count prices into histogram buckets. buckets = list of upper bounds."""
    counts = [0] * len(buckets)
    for p in prices:
        for i, upper in enumerate(buckets):
            if p <= upper:
                counts[i] += 1
                break
    return counts


# ── Snapshot save ──────────────────────────────────────────────────────────────

def save_snapshot(all_listings: list, data_by_category: dict) -> Path:
    """Compute summary stats and write to history/YYYY-MM-DD_HH-MM.json."""
    HISTORY_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    fname = now.strftime("%Y-%m-%d_%H-%M") + ".json"
    path = HISTORY_DIR / fname

    priced = [l["price"] for l in all_listings if l.get("price")]

    cat_stats = {}
    for cat in CATEGORIES:
        items = data_by_category.get(cat, [])
        cat_prices = [l["price"] for l in items if l.get("price")]
        cat_stats[cat] = {
            "count": len(items),
            "price": price_stats(cat_prices),
        }

    sources = {}
    for l in all_listings:
        s = l.get("source_site", "Unknown")
        sources[s] = sources.get(s, 0) + 1

    condition = {}
    for l in all_listings:
        c = l.get("cond", "Unknown")
        condition[c] = condition.get(c, 0) + 1

    snapshot = {
        "run_at":    now.isoformat(timespec="seconds"),
        "date":      now.strftime("%Y-%m-%d"),
        "label":     now.strftime("%b %d"),
        "total":     len(all_listings),
        "priced":    len(priced),
        "sources":   sources,
        "condition": condition,
        "categories": cat_stats,
        "price_all": price_stats(priced),
    }

    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return path


# ── History loader ─────────────────────────────────────────────────────────────

def load_history() -> list:
    """Return all history snapshots sorted oldest→newest."""
    if not HISTORY_DIR.exists():
        return []
    snaps = []
    for f in sorted(HISTORY_DIR.glob("*.json")):
        try:
            snaps.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return snaps


# ── Build insights dashboard ───────────────────────────────────────────────────

def build_insights(all_listings: list = None, data_by_category: dict = None):
    """
    Build insights_dashboard.html.
    If called without args, reads from last_scrape_data.json + classify.
    """
    if all_listings is None:
        if not CACHE.exists():
            print("No scrape data found. Run the scraper first.")
            return
        all_listings = json.loads(CACHE.read_text(encoding="utf-8"))

    if data_by_category is None:
        from classify import categorize_all
        data_by_category = categorize_all(all_listings)

    history = load_history()

    # ── Compute analytics ──────────────────────────────────────────────────
    priced = [l["price"] for l in all_listings if l.get("price")]
    overall_stats = price_stats(priced)

    # Price distribution histogram (overall, buckets in $K)
    hist_buckets   = [25000, 50000, 75000, 100000, 150000, 200000, 250000, 300000, 400000, 999999999]
    hist_labels    = ["<$25K","$25-50K","$50-75K","$75-100K","$100-150K","$150-200K","$200-250K","$250-300K","$300-400K","$400K+"]
    hist_counts    = bucket_prices(priced, hist_buckets)

    # Per-category stats
    cat_data = {}
    for cat in CATEGORIES:
        items = data_by_category.get(cat, [])
        cat_prices = [l["price"] for l in items if l.get("price")]
        cat_data[cat] = {
            "count":  len(items),
            "stats":  price_stats(cat_prices),
            "hist":   bucket_prices(cat_prices, hist_buckets),
        }

    # Price by year (used units with price and year 2000+)
    year_price_map = {}
    for l in all_listings:
        yr = l.get("year", 0)
        px = l.get("price")
        if yr and yr >= 2000 and px and l.get("cond") == "Used":
            year_price_map.setdefault(yr, []).append(px)
    year_medians = {
        yr: round(statistics.median(prices))
        for yr, prices in year_price_map.items()
        if len(prices) >= 3
    }
    year_sorted = sorted(year_medians.keys())

    # Source breakdown
    sources = {}
    for l in all_listings:
        s = l.get("source_site", "Unknown")
        sources[s] = sources.get(s, 0) + 1

    # Condition breakdown
    condition = {}
    for l in all_listings:
        c = l.get("cond", "Unknown")
        condition[c] = condition.get(c, 0) + 1

    # Location top 20 (state extraction)
    loc_counts = {}
    for l in all_listings:
        loc = l.get("loc", "")
        if "," in loc:
            state = loc.split(",")[-1].strip()
            if state:
                loc_counts[state] = loc_counts.get(state, 0) + 1
    top_locs = sorted(loc_counts.items(), key=lambda x: -x[1])[:20]

    # Median price per state (for top_locs states)
    state_price_map = {}
    for l in all_listings:
        loc = l.get("loc", "")
        price = l.get("price")
        if "," in loc and price:
            state = loc.split(",")[-1].strip()
            if state:
                state_price_map.setdefault(state, []).append(price)
    loc_med_vals = [
        round(statistics.median(state_price_map[s])) if s in state_price_map else 0
        for s, _ in top_locs
    ]

    # New vs Used median price per category
    new_med  = {}
    used_med = {}
    for cat in CATEGORIES:
        items = data_by_category.get(cat, [])
        new_p  = [l["price"] for l in items if l.get("price") and l.get("cond") == "New"]
        used_p = [l["price"] for l in items if l.get("price") and l.get("cond") == "Used"]
        new_med[cat]  = round(statistics.median(new_p))  if new_p  else 0
        used_med[cat] = round(statistics.median(used_p)) if used_p else 0

    # Historical trend arrays (for charts)
    hist_dates       = [s["label"] for s in history]
    hist_totals      = [s["total"] for s in history]
    hist_avg_price   = [s["price_all"].get("avg", 0) for s in history]
    hist_cat_counts  = {
        cat: [s["categories"].get(cat, {}).get("count", 0) for s in history]
        for cat in CATEGORIES
    }
    hist_cat_medians = {
        cat: [s["categories"].get(cat, {}).get("price", {}).get("median", 0) for s in history]
        for cat in CATEGORIES
    }

    # ── Inject into HTML ──────────────────────────────────────────────────
    scrape_date = datetime.now().strftime("%B %d, %Y")
    if all_listings:
        # Try to get date from first listing's run (not available) — use now
        pass

    html = _build_html(
        scrape_date=scrape_date,
        total=len(all_listings),
        priced=len(priced),
        overall_stats=overall_stats,
        hist_labels=hist_labels,
        hist_counts=hist_counts,
        cat_data=cat_data,
        year_sorted=year_sorted,
        year_medians=year_medians,
        sources=sources,
        condition=condition,
        top_locs=top_locs,
        loc_med_vals=loc_med_vals,
        new_med=new_med,
        used_med=used_med,
        history=history,
        hist_dates=hist_dates,
        hist_totals=hist_totals,
        hist_avg_price=hist_avg_price,
        hist_cat_counts=hist_cat_counts,
        hist_cat_medians=hist_cat_medians,
    )

    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Insights dashboard written: {OUTPUT}")


# ── HTML builder ───────────────────────────────────────────────────────────────

def _j(v):
    return json.dumps(v)


def _build_html(**ctx) -> str:
    d          = ctx
    total      = d["total"]
    priced     = d["priced"]
    os         = d["overall_stats"]
    cat_data   = d["cat_data"]
    sources    = d["sources"]
    condition  = d["condition"]
    top_locs   = d["top_locs"]
    history    = d["history"]
    pct_priced = round(100 * priced / total) if total else 0
    n_runs     = len(history)

    cat_counts  = [cat_data[c]["count"] for c in CATEGORIES]
    cat_labels  = [CAT_LABELS[c] for c in CATEGORIES]
    cat_colors  = [CAT_COLORS[c] for c in CATEGORIES]
    cat_medians = [cat_data[c]["stats"]["median"] for c in CATEGORIES]
    cat_avgs    = [cat_data[c]["stats"]["avg"]    for c in CATEGORIES]

    new_med_vals  = [d["new_med"][c]  for c in CATEGORIES if c != "other"]
    used_med_vals = [d["used_med"][c] for c in CATEGORIES if c != "other"]
    nu_labels     = [CAT_LABELS[c]    for c in CATEGORIES if c != "other"]

    src_labels = list(sources.keys())
    src_counts = list(sources.values())
    loc_labels = [x[0] for x in top_locs]
    loc_counts = [x[1] for x in top_locs]

    yr_labels  = d["year_sorted"]
    yr_vals    = [d["year_medians"][y] for y in yr_labels]

    has_history = n_runs >= 2
    hist_note   = f"{n_runs} run{'s' if n_runs != 1 else ''} recorded"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Market Insights | Work Truck Depot</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-chart-geo@4.3.6/build/index.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --navy:#122463;--navy-dark:#0C1A50;--navy-mid:#1A3182;--navy-light:#233EA0;
  --navy-pale:#E8ECF7;--navy-muted:#D0D7EF;
  --grey-900:#1A1D2E;--grey-700:#3D4265;--grey-500:#6B7199;
  --grey-400:#8C91B0;--grey-200:#C8CCE0;--grey-100:#E8EAF0;--grey-50:#F4F5F9;
  --white:#FFFFFF;--border:var(--grey-200);--r:6px;--rl:10px;--touch:44px;
  --green:#2E7D32;--red:#BF360C;--amber:#F57F17;
}}
html{{-webkit-text-size-adjust:100%}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',Arial,sans-serif;background:var(--grey-50);color:var(--grey-900);font-size:13px;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:inherit;text-decoration:none}}

/* TOPBAR */
.topbar{{background:var(--navy-dark);padding:0 20px;height:52px;display:flex;align-items:center;justify-content:space-between;gap:10px;position:sticky;top:0;z-index:200;border-bottom:3px solid var(--navy-light)}}
.logo-mark{{width:34px;height:34px;min-width:34px;background:var(--white);border-radius:5px;display:flex;align-items:center;justify-content:center}}
.logo-mark span{{font-weight:900;font-size:11px;color:var(--navy);letter-spacing:-.5px}}
.topbar-brand{{display:flex;align-items:center;gap:10px;flex:1;min-width:0}}
.topbar-name{{font-size:13px;font-weight:700;color:var(--white);white-space:nowrap}}
.topbar-meta{{font-size:10px;color:var(--grey-400);display:none}}
.topbar-right{{display:flex;align-items:center;gap:6px;flex-shrink:0}}
.topbar-link{{font-size:11px;color:var(--grey-400);padding:6px 10px;border:1px solid rgba(255,255,255,.2);border-radius:4px;white-space:nowrap;min-height:var(--touch);display:flex;align-items:center}}
.topbar-tag{{font-size:10px;background:#2E7D32;color:var(--white);border-radius:3px;padding:3px 8px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}}

/* PAGE */
.page{{max-width:1440px;margin:0 auto;padding:14px 14px 60px}}

/* PAGE HEADER */
.page-header{{background:var(--navy);border-radius:var(--rl);padding:14px 16px;margin-bottom:14px}}
.page-title{{font-size:16px;font-weight:800;color:var(--white)}}
.page-sub{{font-size:10px;color:var(--grey-400);margin-top:3px}}

/* TABS */
.tabs{{display:flex;gap:0;margin-bottom:14px;border-bottom:2px solid var(--border);overflow-x:auto;scrollbar-width:none}}
.tabs::-webkit-scrollbar{{display:none}}
.tab{{padding:0 18px;height:40px;font-size:12px;font-weight:600;cursor:pointer;color:var(--grey-500);border-bottom:3px solid transparent;margin-bottom:-2px;white-space:nowrap;background:none;border-top:none;border-left:none;border-right:none}}
.tab.active{{color:var(--navy);border-bottom-color:var(--navy)}}
.tab-panel{{display:none}}.tab-panel.active{{display:block}}

/* KPI STRIP */
.kpi-strip{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px}}
.kpi{{background:var(--white);border:1px solid var(--border);border-radius:var(--rl);padding:12px 14px;position:relative;overflow:hidden}}
.kpi::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--navy)}}
.kpi.green::before{{background:var(--green)}}
.kpi.amber::before{{background:var(--amber)}}
.kpi-label{{font-size:9px;color:var(--grey-500);text-transform:uppercase;letter-spacing:.07em;margin-bottom:3px}}
.kpi-value{{font-size:22px;font-weight:800;color:var(--navy);line-height:1}}
.kpi-note{{font-size:9px;color:var(--grey-500);margin-top:3px}}

/* CARD / SECTION */
.card{{background:var(--white);border:1px solid var(--border);border-radius:var(--rl);overflow:hidden;margin-bottom:14px}}
.card-head{{background:var(--navy);padding:10px 14px;display:flex;align-items:center;justify-content:space-between}}
.card-title{{font-size:12px;font-weight:700;color:var(--white);text-transform:uppercase;letter-spacing:.05em}}
.card-sub{{font-size:10px;color:var(--grey-400)}}
.card-body{{padding:14px}}

/* GRID LAYOUTS */
.grid2{{display:grid;grid-template-columns:1fr;gap:14px}}
.grid3{{display:grid;grid-template-columns:1fr;gap:14px}}

/* CHART WRAPPER */
.chart-box{{position:relative}}
.chart-box canvas{{max-width:100%}}

/* HISTORY PLACEHOLDER */
.history-placeholder{{text-align:center;padding:40px 20px;color:var(--grey-500)}}
.history-placeholder .icon{{font-size:36px;margin-bottom:10px}}
.history-placeholder strong{{display:block;font-size:14px;color:var(--grey-700);margin-bottom:6px}}
.history-placeholder p{{font-size:12px;line-height:1.6}}

/* STAT TABLE */
.stat-table{{width:100%;border-collapse:collapse;font-size:11px}}
.stat-table th{{font-size:9px;font-weight:700;color:var(--white);background:var(--navy-mid);padding:7px 10px;text-align:left;text-transform:uppercase;letter-spacing:.05em}}
.stat-table td{{padding:7px 10px;border-bottom:1px solid var(--grey-100);vertical-align:middle}}
.stat-table tr:last-child td{{border-bottom:none}}
.stat-table tr:nth-child(even) td{{background:var(--grey-50)}}
.price-val{{font-weight:700;color:var(--navy)}}
.bar-cell{{width:120px}}
.inline-bar{{height:8px;background:var(--navy-pale);border-radius:4px;overflow:hidden}}
.inline-bar-fill{{height:100%;background:var(--navy);border-radius:4px}}

/* BADGE */
.badge{{display:inline-block;font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px}}

/* RESPONSIVE */
@media(min-width:600px){{
  .kpi-strip{{grid-template-columns:repeat(3,1fr)}}
  .topbar-meta{{display:block}}
}}
@media(min-width:900px){{
  .page{{padding:24px 28px 60px}}
  .topbar{{padding:0 32px}}
  .kpi-strip{{grid-template-columns:repeat(6,1fr);gap:10px}}
  .kpi-value{{font-size:24px}}
  .grid2{{grid-template-columns:1fr 1fr}}
  .grid3{{grid-template-columns:1fr 1fr 1fr}}
  .page-title{{font-size:18px}}
}}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-brand">
    <div class="logo-mark"><span>WTD</span></div>
    <div>
      <div class="topbar-name">Work Truck Depot</div>
      <div class="topbar-meta">Market Intelligence — Insights</div>
    </div>
  </div>
  <div class="topbar-right">
    <span class="topbar-tag">Insights</span>
    <a class="topbar-link" href="multi_source_dashboard.html">← Dashboard</a>
  </div>
</div>

<div class="page">

  <div class="page-header">
    <div class="page-title">Market Insights &amp; Analytics</div>
    <div class="page-sub">Based on {total:,} listings scraped {d["scrape_date"]} · {hist_note} · {priced:,} priced units ({pct_priced}%)</div>
  </div>

  <!-- KPI STRIP -->
  <div class="kpi-strip">
    <div class="kpi"><div class="kpi-label">Total Listings</div><div class="kpi-value">{total:,}</div><div class="kpi-note">All sources combined</div></div>
    <div class="kpi green"><div class="kpi-label">Avg Price (priced)</div><div class="kpi-value">${os["avg"]:,}</div><div class="kpi-note">All categories</div></div>
    <div class="kpi"><div class="kpi-label">Median Price</div><div class="kpi-value">${os["median"]:,}</div><div class="kpi-note">50th percentile</div></div>
    <div class="kpi"><div class="kpi-label">Price Range</div><div class="kpi-value">${os["min"]:,}</div><div class="kpi-note">to ${os["max"]:,}</div></div>
    <div class="kpi amber"><div class="kpi-label">Priced Units</div><div class="kpi-value">{pct_priced}%</div><div class="kpi-note">{priced:,} of {total:,}</div></div>
    <div class="kpi"><div class="kpi-label">History Runs</div><div class="kpi-value">{n_runs}</div><div class="kpi-note">Scrape sessions</div></div>
  </div>

  <!-- TABS -->
  <div class="tabs">
    <button class="tab active" onclick="showTab('overview',this)">Overview</button>
    <button class="tab" onclick="showTab('pricing',this)">Pricing</button>
    <button class="tab" onclick="showTab('trends',this)">Trends</button>
    <button class="tab" onclick="showTab('locations',this)">Locations</button>
  </div>

  <!-- ══════════ OVERVIEW TAB ══════════ -->
  <div class="tab-panel active" id="tab-overview">

    <div class="grid2">

      <!-- Category breakdown -->
      <div class="card">
        <div class="card-head">
          <div class="card-title">Inventory by Category</div>
          <div class="card-sub">{total:,} total listings</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:280px"><canvas id="ch-cat-pie"></canvas></div>
        </div>
      </div>

      <!-- Source breakdown -->
      <div class="card">
        <div class="card-head">
          <div class="card-title">Listings by Source</div>
          <div class="card-sub">{len(sources)} sites</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:280px"><canvas id="ch-source-pie"></canvas></div>
        </div>
      </div>

    </div>

    <!-- Category stats table -->
    <div class="card">
      <div class="card-head">
        <div class="card-title">Category Summary</div>
        <div class="card-sub">Listings, pricing, and condition per category</div>
      </div>
      <div class="card-body" style="padding:0">
        <div style="overflow-x:auto">
        <table class="stat-table">
          <thead><tr><th>Category</th><th>Listings</th><th>Priced</th><th>Min</th><th>Median</th><th>Avg</th><th>Max</th><th>Share</th></tr></thead>
          <tbody>
{_cat_table_rows(cat_data, total)}
          </tbody>
        </table>
        </div>
      </div>
    </div>

    <!-- Condition breakdown -->
    <div class="grid2">
      <div class="card">
        <div class="card-head">
          <div class="card-title">New vs. Used Split</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:220px"><canvas id="ch-condition"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-head">
          <div class="card-title">New vs. Used — Median Price by Category</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:220px"><canvas id="ch-newused-price"></canvas></div>
        </div>
      </div>
    </div>

  </div><!-- /overview -->

  <!-- ══════════ PRICING TAB ══════════ -->
  <div class="tab-panel" id="tab-pricing">

    <!-- Price distribution histogram -->
    <div class="card">
      <div class="card-head">
        <div class="card-title">Price Distribution — All Categories</div>
        <div class="card-sub">{priced:,} priced units</div>
      </div>
      <div class="card-body">
        <div class="chart-box" style="height:300px"><canvas id="ch-hist-all"></canvas></div>
      </div>
    </div>

    <div class="grid2">
      <!-- Price by year -->
      <div class="card">
        <div class="card-head">
          <div class="card-title">Median Price by Model Year</div>
          <div class="card-sub">Used units, 3+ listings per year</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:280px"><canvas id="ch-year-price"></canvas></div>
        </div>
      </div>

      <!-- Per-category median bar -->
      <div class="card">
        <div class="card-head">
          <div class="card-title">Median Price by Category</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:280px"><canvas id="ch-cat-median"></canvas></div>
        </div>
      </div>
    </div>

    <!-- Per-category histograms -->
    <div class="grid3">
{"".join(_cat_hist_card(c) for c in CATEGORIES if c != "other")}
    </div>

  </div><!-- /pricing -->

  <!-- ══════════ TRENDS TAB ══════════ -->
  <div class="tab-panel" id="tab-trends">
{"" if has_history else _history_placeholder(n_runs)}
{"" if not has_history else _trends_section()}
  </div>

  <!-- ══════════ LOCATIONS TAB ══════════ -->
  <div class="tab-panel" id="tab-locations">

    <div class="card">
      <div class="card-head">
        <div class="card-title">Listings by State — US Map</div>
        <div class="card-sub">Darker = more inventory</div>
      </div>
      <div class="card-body">
        <div id="map-wrap" style="position:relative;height:420px;display:flex;align-items:center;justify-content:center">
          <canvas id="ch-map" style="width:100%;height:100%"></canvas>
          <div id="map-loading" style="position:absolute;font-size:12px;color:var(--grey-500)">Loading map…</div>
        </div>
      </div>
    </div>

    <div class="grid2">
      <div class="card">
        <div class="card-head">
          <div class="card-title">Top States by Volume</div>
          <div class="card-sub">Listing count</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:380px"><canvas id="ch-locations"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-head">
          <div class="card-title">Median Price by State</div>
          <div class="card-sub">Priced listings only</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:380px"><canvas id="ch-loc-price"></canvas></div>
        </div>
      </div>
    </div>

  </div>

</div><!-- /page -->

<script>
// ── Tab switching ──────────────────────────────────────────────────────────
function showTab(id, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}}

// ── Chart defaults ─────────────────────────────────────────────────────────
Chart.defaults.font.family = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";
Chart.defaults.font.size   = 11;
Chart.defaults.color       = '#6B7199';
Chart.defaults.plugins.legend.labels.boxWidth = 10;
Chart.defaults.plugins.legend.labels.padding  = 12;

const fmt = v => v >= 1000 ? '$' + (v/1000).toFixed(0) + 'K' : '$' + v;

// ── DATA ───────────────────────────────────────────────────────────────────
const CAT_LABELS   = {_j(cat_labels)};
const CAT_COLORS   = {_j(cat_colors)};
const CAT_COUNTS   = {_j(cat_counts)};
const CAT_MEDIANS  = {_j(cat_medians)};
const CAT_AVGS     = {_j(cat_avgs)};
const SRC_LABELS   = {_j(src_labels)};
const SRC_COUNTS   = {_j(src_counts)};
const COND_LABELS  = {_j(list(condition.keys()))};
const COND_COUNTS  = {_j(list(condition.values()))};
const HIST_LABELS  = {_j(d["hist_labels"])};
const HIST_COUNTS  = {_j(d["hist_counts"])};
const YR_LABELS    = {_j([str(y) for y in yr_labels])};
const YR_VALS      = {_j(yr_vals)};
const LOC_LABELS   = {_j(loc_labels)};
const LOC_COUNTS   = {_j(loc_counts)};
const LOC_MEDIANS  = {_j(d["loc_med_vals"])};
const NU_LABELS    = {_j(nu_labels)};
const NEW_MED      = {_j(new_med_vals)};
const USED_MED     = {_j(used_med_vals)};

// Per-category histograms
const CAT_HISTS = {{}};
{"".join(f'CAT_HISTS["{c}"] = {_j(cat_data[c]["hist"])};' for c in CATEGORIES if c != "other")}

// History
const HAS_HISTORY   = {'true' if has_history else 'false'};
const HIST_DATES    = {_j(d["hist_dates"])};
const HIST_TOTALS   = {_j(d["hist_totals"])};
const HIST_AVG      = {_j(d["hist_avg_price"])};
const HIST_CAT_CNT  = {_j(d["hist_cat_counts"])};
const HIST_CAT_MED  = {_j(d["hist_cat_medians"])};

// ── CHART BUILDERS ────────────────────────────────────────────────────────

// Category pie
new Chart(document.getElementById('ch-cat-pie'), {{
  type: 'doughnut',
  data: {{ labels: CAT_LABELS, datasets: [{{ data: CAT_COUNTS, backgroundColor: CAT_COLORS, borderWidth: 2, borderColor: '#fff' }}] }},
  options: {{ responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ position:'right' }},
      tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{ctx.raw.toLocaleString()}} (${{Math.round(ctx.raw/CAT_COUNTS.reduce((a,b)=>a+b,0)*100)}}%)` }} }} }} }}
}});

// Source pie
new Chart(document.getElementById('ch-source-pie'), {{
  type: 'doughnut',
  data: {{ labels: SRC_LABELS, datasets: [{{ data: SRC_COUNTS, backgroundColor: ['#122463','#2E7D32','#6A1B9A','#BF360C','#F57F17','#546E7A'], borderWidth: 2, borderColor: '#fff' }}] }},
  options: {{ responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ position:'right' }},
      tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{ctx.raw.toLocaleString()}}` }} }} }} }}
}});

// Condition doughnut
new Chart(document.getElementById('ch-condition'), {{
  type: 'doughnut',
  data: {{ labels: COND_LABELS, datasets: [{{ data: COND_COUNTS, backgroundColor: ['#122463','#8C91B0'], borderWidth: 2, borderColor: '#fff' }}] }},
  options: {{ responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ position:'right' }},
      tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.label}}: ${{ctx.raw.toLocaleString()}}` }} }} }} }}
}});

// New vs Used price comparison
new Chart(document.getElementById('ch-newused-price'), {{
  type: 'bar',
  data: {{
    labels: NU_LABELS,
    datasets: [
      {{ label: 'New (median)', data: NEW_MED, backgroundColor: '#122463' }},
      {{ label: 'Used (median)', data: USED_MED, backgroundColor: '#8C91B0' }},
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ position:'top' }}, tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{fmt(ctx.raw)}}` }} }} }},
    scales: {{ y: {{ ticks: {{ callback: v => fmt(v) }} }} }}
  }}
}});

// Price histogram (all)
new Chart(document.getElementById('ch-hist-all'), {{
  type: 'bar',
  data: {{ labels: HIST_LABELS, datasets: [{{ label: 'Listings', data: HIST_COUNTS, backgroundColor: '#1A3182', borderRadius: 3 }}] }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }} }},
    scales: {{ y: {{ beginAtZero:true }} }}
  }}
}});

// Price by year
new Chart(document.getElementById('ch-year-price'), {{
  type: 'line',
  data: {{ labels: YR_LABELS, datasets: [{{ label: 'Median Price (Used)', data: YR_VALS, borderColor: '#122463', backgroundColor: 'rgba(18,36,99,.1)', fill:true, tension:0.3, pointRadius:3 }}] }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }}, tooltip: {{ callbacks: {{ label: ctx => ` ${{fmt(ctx.raw)}}` }} }} }},
    scales: {{ y: {{ ticks: {{ callback: v => fmt(v) }} }} }}
  }}
}});

// Category median bar
new Chart(document.getElementById('ch-cat-median'), {{
  type: 'bar',
  data: {{
    labels: CAT_LABELS,
    datasets: [
      {{ label: 'Median', data: CAT_MEDIANS, backgroundColor: CAT_COLORS, borderRadius: 3 }},
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false, indexAxis:'y',
    plugins: {{ legend: {{ display:false }}, tooltip: {{ callbacks: {{ label: ctx => ` ${{fmt(ctx.raw)}}` }} }} }},
    scales: {{ x: {{ ticks: {{ callback: v => fmt(v) }} }} }}
  }}
}});

// Per-category histograms
{chr(10).join(f'''new Chart(document.getElementById('ch-hist-{c}'), {{
  type: 'bar',
  data: {{ labels: HIST_LABELS, datasets: [{{ label: 'Listings', data: CAT_HISTS["{c}"], backgroundColor: '{CAT_COLORS[c]}', borderRadius: 2 }}] }},
  options: {{ responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }} }},
    scales: {{ x: {{ ticks: {{ font: {{ size:9 }}, maxRotation:45 }} }}, y: {{ beginAtZero:true }} }} }}
}});''' for c in CATEGORIES if c != "other")}

// Locations bar chart
new Chart(document.getElementById('ch-locations'), {{
  type: 'bar', indexAxis: 'y',
  data: {{ labels: LOC_LABELS, datasets: [{{ label: 'Listings', data: LOC_COUNTS, backgroundColor: '#122463', borderRadius: 3 }}] }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }} }},
    scales: {{ x: {{ beginAtZero:true }} }}
  }}
}});

// Median price by state
new Chart(document.getElementById('ch-loc-price'), {{
  type: 'bar', indexAxis: 'y',
  data: {{ labels: LOC_LABELS, datasets: [{{ label: 'Median Price', data: LOC_MEDIANS, backgroundColor: '#1A3182', borderRadius: 3 }}] }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins: {{ legend: {{ display:false }}, tooltip: {{ callbacks: {{ label: ctx => ` ${{fmt(ctx.raw)}}` }} }} }},
    scales: {{ x: {{ ticks: {{ callback: v => fmt(v) }}, beginAtZero:true }} }}
  }}
}});

// US Choropleth map
(async function() {{
  try {{
    const us = await fetch('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json').then(r => r.json());
    const nation = ChartGeo.topojson.feature(us, us.objects.nation);
    const states = ChartGeo.topojson.feature(us, us.objects.states);
    const stateData = {{}};
    LOC_LABELS.forEach((name, i) => {{ stateData[name] = LOC_COUNTS[i]; }});
    document.getElementById('map-loading').style.display = 'none';
    new Chart(document.getElementById('ch-map'), {{
      type: 'choropleth',
      data: {{
        labels: states.features.map(d => d.properties.name),
        datasets: [{{
          label: 'Listings',
          outline: nation.features[0],
          data: states.features.map(d => ({{ feature: d, value: stateData[d.properties.name] || 0 }}))
        }}]
      }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ callbacks: {{ label: ctx => `${{ctx.label}}: ${{ctx.raw.value}} listing${{ctx.raw.value !== 1 ? 's' : ''}}` }} }}
        }},
        scales: {{
          color: {{
            quantize: 6,
            legend: {{ position: 'bottom-right', align: 'bottom' }},
            interpolate: v => `rgba(18,36,99,${{(0.08 + v * 0.92).toFixed(2)}})`
          }}
        }}
      }}
    }});
  }} catch(e) {{
    document.getElementById('map-loading').textContent = 'Map unavailable (requires internet connection)';
  }}
}})();

// Trend charts (only if history available)
if (HAS_HISTORY) {{
  new Chart(document.getElementById('ch-trend-total'), {{
    type: 'line',
    data: {{ labels: HIST_DATES, datasets: [{{ label: 'Total Listings', data: HIST_TOTALS, borderColor: '#122463', backgroundColor: 'rgba(18,36,99,.1)', fill:true, tension:0.3, pointRadius:4 }}] }},
    options: {{ responsive:true, maintainAspectRatio:false, plugins: {{ legend: {{ display:false }} }} }}
  }});
  new Chart(document.getElementById('ch-trend-price'), {{
    type: 'line',
    data: {{ labels: HIST_DATES, datasets: [{{ label: 'Avg Price', data: HIST_AVG, borderColor: '#2E7D32', backgroundColor: 'rgba(46,125,50,.1)', fill:true, tension:0.3, pointRadius:4 }}] }},
    options: {{ responsive:true, maintainAspectRatio:false,
      plugins: {{ legend: {{ display:false }}, tooltip: {{ callbacks: {{ label: ctx => ` ${{fmt(ctx.raw)}}` }} }} }},
      scales: {{ y: {{ ticks: {{ callback: v => fmt(v) }} }} }}
    }}
  }});
  const trendColors = {_j(cat_colors)};
  new Chart(document.getElementById('ch-trend-cats'), {{
    type: 'line',
    data: {{
      labels: HIST_DATES,
      datasets: {_j(cat_labels)}.map((lbl, i) => ({{
        label: lbl,
        data: HIST_CAT_CNT[{_j(CATEGORIES)}[i]],
        borderColor: trendColors[i], backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 4
      }}))
    }},
    options: {{ responsive:true, maintainAspectRatio:false }}
  }});
  new Chart(document.getElementById('ch-trend-cat-price'), {{
    type: 'line',
    data: {{
      labels: HIST_DATES,
      datasets: {_j(cat_labels)}.map((lbl, i) => ({{
        label: lbl,
        data: HIST_CAT_MED[{_j(CATEGORIES)}[i]],
        borderColor: trendColors[i], backgroundColor: 'transparent',
        tension: 0.3, pointRadius: 4
      }}))
    }},
    options: {{
      responsive:true, maintainAspectRatio:false,
      plugins: {{ tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{fmt(ctx.raw)}}` }} }} }},
      scales: {{ y: {{ ticks: {{ callback: v => fmt(v) }} }} }}
    }}
  }});
}}
</script>
</body>
</html>"""


# ── Template fragment helpers ──────────────────────────────────────────────────

def _fmt_price(v):
    if not v:
        return "—"
    return f"${v:,}"


def _cat_table_rows(cat_data: dict, total: int) -> str:
    rows = []
    max_count = max((cat_data[c]["count"] for c in CATEGORIES), default=1)
    for cat in CATEGORIES:
        d = cat_data[cat]
        count  = d["count"]
        stats  = d["stats"]
        pct    = round(100 * count / total) if total else 0
        bar_w  = round(100 * count / max_count) if max_count else 0
        color  = CAT_COLORS[cat]
        rows.append(
            f'<tr>'
            f'<td><span style="display:inline-block;width:10px;height:10px;background:{color};border-radius:2px;margin-right:6px;vertical-align:middle"></span>{CAT_LABELS[cat]}</td>'
            f'<td>{count:,}</td>'
            f'<td>{stats["count"]:,}</td>'
            f'<td class="price-val">{_fmt_price(stats["min"])}</td>'
            f'<td class="price-val">{_fmt_price(stats["median"])}</td>'
            f'<td class="price-val">{_fmt_price(stats["avg"])}</td>'
            f'<td class="price-val">{_fmt_price(stats["max"])}</td>'
            f'<td class="bar-cell"><div class="inline-bar"><div class="inline-bar-fill" style="width:{bar_w}%;background:{color}"></div></div><span style="font-size:9px;color:var(--grey-500);margin-left:4px">{pct}%</span></td>'
            f'</tr>'
        )
    return "\n".join(rows)


def _cat_hist_card(cat: str) -> str:
    return f"""
      <div class="card">
        <div class="card-head">
          <div class="card-title">{CAT_LABELS[cat]}</div>
          <div class="card-sub">Price distribution</div>
        </div>
        <div class="card-body">
          <div class="chart-box" style="height:200px"><canvas id="ch-hist-{cat}"></canvas></div>
        </div>
      </div>"""


def _history_placeholder(n_runs: int) -> str:
    next_needed = 2 - n_runs
    return f"""
    <div class="card">
      <div class="card-body">
        <div class="history-placeholder">
          <div class="icon">📈</div>
          <strong>Trend charts will appear after {next_needed} more scrape run{"s" if next_needed != 1 else ""}</strong>
          <p>Each time you run the scraper, a snapshot is saved to <code>Scraper/history/</code>.<br>
          Trend charts unlock automatically once you have 2+ runs.<br>
          You currently have <strong>{n_runs}</strong> run recorded.</p>
        </div>
      </div>
    </div>"""


def _trends_section() -> str:
    return """
    <div class="grid2">
      <div class="card">
        <div class="card-head"><div class="card-title">Total Inventory Over Time</div></div>
        <div class="card-body"><div class="chart-box" style="height:260px"><canvas id="ch-trend-total"></canvas></div></div>
      </div>
      <div class="card">
        <div class="card-head"><div class="card-title">Average Price Over Time</div></div>
        <div class="card-body"><div class="chart-box" style="height:260px"><canvas id="ch-trend-price"></canvas></div></div>
      </div>
    </div>
    <div class="card">
      <div class="card-head"><div class="card-title">Inventory by Category Over Time</div></div>
      <div class="card-body"><div class="chart-box" style="height:300px"><canvas id="ch-trend-cats"></canvas></div></div>
    </div>
    <div class="card">
      <div class="card-head"><div class="card-title">Median Price by Category Over Time</div></div>
      <div class="card-body"><div class="chart-box" style="height:300px"><canvas id="ch-trend-cat-price"></canvas></div></div>
    </div>"""


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    build_insights()
