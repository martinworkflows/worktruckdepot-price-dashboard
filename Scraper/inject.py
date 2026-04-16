"""
inject.py — Injects scraped DATA into the dashboard HTML template.

Reads dashboard_template.html, replaces {{MARKERS}} with live data,
writes multi_source_dashboard.html.
"""

import json
from pathlib import Path
from datetime import datetime


def build_dashboard(
    template_path: Path,
    output_path: Path,
    data: dict,
    scrape_meta: dict,
) -> None:
    """
    Read template, fill all markers, write output file.

    scrape_meta keys:
      date       — formatted date string, e.g. "April 08, 2026"
      total      — int, total listings scraped
      errors     — list of {"url": ..., "error": ...} dicts
      sources    — list of source site name strings
    """
    template = template_path.read_text(encoding="utf-8")

    # ── Build the JS DATA block ──────────────────────────────────────────
    js_data = _build_js_data(data)

    # ── Meta values ─────────────────────────────────────────────────────
    date_str    = scrape_meta.get("date", datetime.now().strftime("%B %d, %Y"))
    sources     = scrape_meta.get("sources", [])
    total       = scrape_meta.get("total", 0)
    errors      = scrape_meta.get("errors", [])
    sources_str = ", ".join(sources) if sources else "—"
    kpi_sources = str(len(sources))

    # ── Error banner ─────────────────────────────────────────────────────
    if errors:
        failed_urls = ", ".join(e["url"].split("/")[2] for e in errors[:3])  # domain only
        more = f" (+{len(errors)-3} more)" if len(errors) > 3 else ""
        error_banner = (
            f'<div class="warn-banner">'
            f'<span class="warn-icon">⚠</span>'
            f'<div class="warn-text">'
            f'<strong>{len(errors)} source(s) failed this run</strong>'
            f'Sites unavailable: {failed_urls}{more}. '
            f'Results shown are from successful sources only. '
            f'See <code>Scraper/scrape.log</code> for details.'
            f'</div></div>'
        )
    else:
        error_banner = ""

    # ── Replace all markers ───────────────────────────────────────────────
    output = template
    output = output.replace("{{DATA_INJECTION}}", js_data)
    output = output.replace("{{SCRAPE_DATE}}",    date_str)
    output = output.replace("{{SOURCES_LIST}}",   sources_str)
    output = output.replace("{{TOTAL_LISTINGS}}", str(total))
    output = output.replace("{{ERROR_BANNER}}",   error_banner)
    output = output.replace("{{KPI_SOURCES}}",    kpi_sources)

    output_path.write_text(output, encoding="utf-8")


def _build_js_data(data: dict) -> str:
    """
    Convert Python data dict to the JS DATA object literal string.
    Produces: const DATA={bucket:[...], digger:[...], forest:[...], crane:[...], pull:[...]};
    """

    def listing_to_js(l: dict) -> str:
        price_val  = "null" if l.get("price") is None else str(int(l["price"]))
        model      = json.dumps(l.get("model", ""))
        chassis    = json.dumps(l.get("chassis", ""))
        spec       = json.dumps(l.get("spec", ""))
        price_str  = json.dumps(l.get("priceStr", "Call for Price"))
        mi         = json.dumps(l.get("mi", "—"))
        status     = json.dumps(l.get("status", "avail"))
        loc        = json.dumps(l.get("loc", ""))
        src_url    = json.dumps(l.get("source_url", ""))
        src_site   = json.dumps(l.get("source_site", ""))
        subcat     = json.dumps(l.get("subcat", ""))
        cond       = json.dumps(l.get("cond", "Used"))
        year       = int(l.get("year") or 0)

        return (
            f"{{cond:{cond},year:{year},model:{model},chassis:{chassis},"
            f"spec:{spec},subcat:{subcat},price:{price_val},priceStr:{price_str},"
            f"mi:{mi},status:{status},loc:{loc},"
            f"source_url:{src_url},source_site:{src_site}}}"
        )

    categories = ["bucket", "digger", "forest", "crane", "pull"]
    lines = ["const DATA={"]
    for cat in categories:
        items = data.get(cat, [])
        item_strs = ",\n  ".join(listing_to_js(l) for l in items)
        lines.append(f"{cat}:[")
        if item_strs:
            lines.append(f"  {item_strs}")
        lines.append("],")
    lines.append("};")
    return "\n".join(lines)
