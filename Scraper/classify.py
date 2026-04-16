"""
classify.py — Category detection and spec inference for scraped listings.

Maps raw text from model/title/URL to one of the dashboard's 5 categories:
  bucket  — bucket trucks, aerial lifts
  digger  — digger derricks, track diggers
  forest  — forestry equipment, chip trucks, grapple loaders
  crane   — crane trucks, boom trucks
  pull    — pulling & tensioning equipment
  other   — anything unclassified
"""

# ── Category keyword rules ─────────────────────────────────────────────────
# Checked in order; first match wins.
CATEGORY_RULES = [
    ("pull", [
        "puller", "tensioner", "reel trailer", "bullwheel", "line puller",
        "drum puller", "conductor", "clp", "odp", "bwt", "mrst",
        "sherman", "reilly", "condux", "tse ", "stringing",
    ]),
    ("digger", [
        "digger derrick", "derrick", "c4047", "c6060", "a650",
        "tmd-", "pressure digger", "pole setter", "track digger",
        "db37", "dm47", "dc47", "ezh",
    ]),
    ("forest", [
        "forestry", "tree trimm", "chip truck", "chipper", "grapple loader",
        "arbortech", "xt pro", "fassi", "palfinger epsilon",
        "load king chip", "chip box", "log truck", "mulch",
    ]),
    ("crane", [
        "crane truck", "boom truck", "national crane", "manitowoc",
        "grove crane", "link-belt", "ac35", "ac38", "ac40", "ac-40",
        "knuckle crane", "picker truck", "palfinger pk",
    ]),
    ("bucket", [
        "bucket truck", "aerial lift", "man lift", "aerial device",
        "sst-", "vst-", "vtp-", "terex lt", "terex 5tc",
        "dur-a-lift", "duralift", "elliott l", "hi-ranger",
        "versalift", "terex tc", "terex xt", "altec lt", "altec at",
        "altec an", "altec aa", "altec am", "altec lr", "altec ta",
        "insulated boom", "overcenter", "non-overcenter",
    ]),
]

# ── Spec inference from title text ────────────────────────────────────────
SPEC_PATTERNS = [
    ("105ft Elevator",     ["an67", "105ft", "105'"]),
    ("75ft Elevator",      ["lr760", "lr7-60", "75ft elev", "75' elev"]),
    ("70ft Forestry OC",   ["60/70", "70ft fore"]),
    ("60ft Forestry OC",   ["xt pro 60", "xt-pro-60", "60ft fore"]),
    ("55ft OC",            ["tc55", "terex 55", "hrx-55", "5tc-55", "55ft", "55'"]),
    ("47ft OC",            ["vst-47", "vtp-47", "47ft oc"]),
    ("40ft Non-OC",        ["sst-40", "vst-40", "lt-40", "terex lt40", "40ft non", "40' non"]),
    ("40ft OC",            ["vst-40", "40ft oc", "40' oc"]),
    ("40ft",               ["40ft", "40'", "-40"]),
    ("47ft Derrick",       ["c4047", "dm47", "dc47", "tmd-2047", "47ft derrick"]),
    ("60ft Derrick",       ["c6060", "60ft derrick"]),
    ("37ft Track Derrick", ["db37", "37ft"]),
    ("40-Ton Crane",       ["ac-40", "ac40", "40-ton", "40 ton"]),
    ("38-Ton Crane",       ["ac38", "38-ton", "38 ton"]),
    ("35-Ton Crane",       ["ac35", "35-ton", "35 ton"]),
    ("Grapple Loader",     ["fassi", "palfinger epsilon", "grapple loader", "epsilon m"]),
    ("Chip Truck",         ["chip truck", "chip box", "arbortech", "load king chip"]),
]


def categorize_all(listings: list) -> dict:
    """
    Assign a category to each listing and fill empty spec fields.
    Returns a dict with keys: bucket, digger, forest, crane, pull, other.
    Each value is a list of listing dicts.
    """
    result = {
        "bucket": [], "digger": [], "forest": [],
        "crane": [], "pull": [], "other": [],
    }
    for listing in listings:
        listing = _fill_spec(listing)
        cat = _detect_category(listing)
        listing["category"] = cat
        result.get(cat, result["other"]).append(listing)
    return result


def _detect_category(listing: dict) -> str:
    # Build a single lowercase search string from all relevant fields
    search_text = " ".join([
        listing.get("model", ""),
        listing.get("spec", ""),
        listing.get("subcat", ""),
        listing.get("source_url", ""),
        listing.get("chassis", ""),
    ]).lower()

    for cat, keywords in CATEGORY_RULES:
        if any(kw in search_text for kw in keywords):
            return cat
    return "other"


def _fill_spec(listing: dict) -> dict:
    """Infer a spec label from the model text if spec is empty."""
    if listing.get("spec"):
        return listing
    text = " ".join([
        listing.get("model", ""),
        listing.get("source_url", ""),
    ]).lower()
    for spec_label, triggers in SPEC_PATTERNS:
        if any(t in text for t in triggers):
            listing["spec"] = spec_label
            break
    return listing
