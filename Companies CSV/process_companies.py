import csv
import re
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ── helpers ──────────────────────────────────────────────────────────────────

def clean(v):
    if v is None:
        return ""
    return str(v).strip().strip('"').strip()

def norm_domain(website):
    """Return bare domain for dedup key."""
    w = clean(website).lower()
    w = re.sub(r'^https?://', '', w)
    w = re.sub(r'^www\.', '', w)
    w = w.rstrip('/')
    return w.split('/')[0]   # just the host

def norm_name(name):
    """Normalised company name for dedup key."""
    n = clean(name).lower()
    n = re.sub(r'[^a-z0-9]', '', n)
    return n

def country_full(v):
    """Convert 2-letter codes to full country names."""
    mapping = {
        'us': 'United States', 'usa': 'United States',
        'ca': 'Canada', 'can': 'Canada',
        'gb': 'United Kingdom', 'uk': 'United Kingdom',
        'au': 'Australia', 'de': 'Germany', 'fr': 'France',
        'in': 'India', 'mx': 'Mexico', 'nz': 'New Zealand',
    }
    low = clean(v).lower()
    return mapping.get(low, clean(v))

def pick(*vals):
    """Return the first non-empty value."""
    for v in vals:
        v = clean(v)
        if v and v not in ('0', 'N/A', 'n/a', '❌ 0 Records Found'):
            return v
    return ""

# ── read each file ────────────────────────────────────────────────────────────

def read_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def parse_apollo(rows):
    out = []
    for r in rows:
        name    = clean(r.get('Company Name', ''))
        website = clean(r.get('Website', ''))
        phone   = clean(r.get('Company Phone', ''))
        address = clean(r.get('Company Address', ''))
        city    = clean(r.get('Company City', ''))
        state   = clean(r.get('Company State', ''))
        country = country_full(r.get('Company Country', ''))
        zipcode = clean(r.get('Company Postal Code', ''))
        if zipcode == '0':
            zipcode = ""
        linkedin= clean(r.get('Company Linkedin Url', ''))
        industry= clean(r.get('Industry', ''))

        # address field in Apollo is often "street, city, state, country, zip"
        # extract street part only (before city)
        street = ""
        if address:
            parts = [p.strip() for p in address.split(',')]
            if parts:
                street = parts[0]

        out.append({
            'company_name': name,
            'website':      website,
            'phone':        phone,
            'street':       street,
            'city':         city,
            'state':        state,
            'country':      country,
            'zip':          zipcode,
            'linkedin':     linkedin,
            'industry':     industry,
            'source':       'Apollo',
        })
    return out


def parse_raw_address(raw_addr):
    """
    Parse Ocean raw address: 'Street, City, Zip, State, Country'
    Returns (street, city, zipcode, state, country) strings (may be empty).
    """
    if not raw_addr:
        return '', '', '', '', ''
    parts = [p.strip() for p in raw_addr.split(',')]
    # Format typically: Street, City, Zip, State, Country  (5 parts)
    # Or:               Street, City, Zip/Postal, Province, Country
    if len(parts) >= 5:
        street  = parts[0]
        city    = parts[1]
        zipcode = parts[2]
        state   = parts[3]
        country = parts[4]
    elif len(parts) == 4:
        street  = parts[0]
        city    = parts[1]
        zipcode = parts[2]
        state   = ''
        country = parts[3]
    elif len(parts) == 3:
        street  = parts[0]
        city    = parts[1]
        zipcode = ''
        state   = ''
        country = parts[2]
    else:
        street  = parts[0] if parts else ''
        city = zipcode = state = country = ''
    return street, city, zipcode, state, country


def parse_ocean(rows):
    out = []
    for r in rows:
        name    = pick(r.get('companyname',''), r.get('Company',''))
        website = pick(r.get('companywebsite',''), r.get('Domain',''))
        phone   = clean(r.get('Generic Company Phones', ''))
        raw_addr= clean(r.get('Headquarter Raw Address', ''))

        raw_street, raw_city, raw_zip, raw_state, raw_country = parse_raw_address(raw_addr)

        street  = pick(r.get('Headquarter Street Address',''), raw_street)
        city    = pick(r.get('city',''), r.get('Headquarter City',''), raw_city)
        state   = pick(r.get('state',''), r.get('Headquarter State',''), raw_state)
        country = country_full(pick(r.get('companycountry',''), r.get('Country',''), raw_country))
        zipcode = pick(r.get('zipcode',''), r.get('Headquarter Postal Code',''), raw_zip)
        linkedin= pick(r.get('linkedincompanypageurl',''), r.get('Company LinkedIn URL',''))
        industry= pick(r.get('LinkedIn Industry',''), r.get('Industries',''))

        # website: if it's a bare domain, prefix it
        if website and not website.startswith('http'):
            website = 'http://' + website

        out.append({
            'company_name': name,
            'website':      website,
            'phone':        phone,
            'street':       street,
            'city':         city,
            'state':        state,
            'country':      country,
            'zip':          zipcode,
            'linkedin':     linkedin,
            'industry':     industry,
            'source':       'Ocean',
        })
    return out


def parse_bob(rows):
    out = []
    for r in rows:
        name    = pick(r.get('Name',''))
        website = clean(r.get('Website', ''))
        phone   = ""
        address = clean(r.get('Address', ''))
        city    = clean(r.get('City', ''))
        state   = clean(r.get('State', ''))
        country = country_full(r.get('Country', ''))
        zipcode = ""
        linkedin= clean(r.get('LinkedIn Url', ''))
        industry= clean(r.get('Industry', ''))

        # address might be full; extract street
        street = ""
        if address:
            parts = [p.strip() for p in address.split(',')]
            street = parts[0] if parts else address

        out.append({
            'company_name': name,
            'website':      website,
            'phone':        phone,
            'street':       street,
            'city':         city,
            'state':        state,
            'country':      country,
            'zip':          zipcode,
            'linkedin':     linkedin,
            'industry':     industry,
            'source':       'Bob',
        })
    return out


# ── merge / dedup ─────────────────────────────────────────────────────────────

def merge_record(existing, new):
    """Fill empty fields in existing with values from new."""
    for key in ('website','phone','street','city','state','country','zip','linkedin','industry'):
        if not existing[key]:
            existing[key] = new[key]
    return existing


def dedup(records):
    # Primary key: domain; secondary: normalised name
    by_domain = {}
    by_name   = {}
    result    = []

    for rec in records:
        domain = norm_domain(rec['website']) if rec['website'] else ''
        name_k = norm_name(rec['company_name'])

        if not rec['company_name']:
            continue

        if domain and domain in by_domain:
            merge_record(by_domain[domain], rec)
            continue

        if name_k and name_k in by_name:
            merge_record(by_name[name_k], rec)
            # also index by domain if we just got it
            if domain and domain not in by_domain:
                by_domain[domain] = by_name[name_k]
            continue

        # new record
        result.append(rec)
        if domain:
            by_domain[domain] = rec
        by_name[name_k] = rec

    return result


# ── main ──────────────────────────────────────────────────────────────────────

files = {
    'Apollo-Default-view-export-1775739178623.csv':                     'apollo',
    'Ocean-1775739197869.io-Default-view-export.csv':                   'ocean',
    'ocean-export-dwvasc-2026-01-02-Default-view-export-1775739214513.csv': 'ocean',
    'Bob-Upload-1-Default-view-export-1775739254177.csv':               'bob',
    'Ocean-1775739268225.io-2-Default-view-export.csv':                 'ocean',
}

all_records = []
for fname, kind in files.items():
    path = os.path.join(BASE, fname)
    rows = read_csv(path)
    print(f"{fname}: {len(rows)} rows")
    if kind == 'apollo':
        all_records.extend(parse_apollo(rows))
    elif kind == 'ocean':
        all_records.extend(parse_ocean(rows))
    elif kind == 'bob':
        all_records.extend(parse_bob(rows))

print(f"\nTotal before dedup: {len(all_records)}")
deduped = dedup(all_records)
print(f"Total after dedup:  {len(deduped)}")

# ── fill missing states from zip lookup ─────────────────────────────────────

# Comprehensive US zip prefix → state (3-digit prefix for precision)
US_ZIP_PREFIX = {}
def _add(state, *prefixes):
    for p in prefixes:
        if '-' in str(p):
            lo, hi = p.split('-')
            for i in range(int(lo), int(hi)+1):
                US_ZIP_PREFIX[str(i).zfill(3)] = state
        else:
            US_ZIP_PREFIX[str(p).zfill(3)] = state

_add('Massachusetts',  '010-027')
_add('Rhode Island',   '028-029')
_add('New Hampshire',  '030-038')
_add('Maine',          '039-049')
_add('Vermont',        '050-059')
_add('Connecticut',    '060-069')
_add('New Jersey',     '070-089')
_add('New York',       '100-149')
_add('Pennsylvania',   '150-196')
_add('Delaware',       '197-199')
_add('District of Columbia', '200-205')
_add('Maryland',       '206-219')
_add('Virginia',       '220-246')
_add('West Virginia',  '247-268')
_add('North Carolina', '270-289')
_add('South Carolina', '290-299')
_add('Georgia',        '300-319')
_add('Florida',        '320-349')
_add('Alabama',        '350-369')
_add('Tennessee',      '370-385')
_add('Mississippi',    '386-397')
_add('Kentucky',       '400-427')
_add('Ohio',           '430-458')
_add('Indiana',        '460-479')
_add('Michigan',       '480-499')
_add('Iowa',           '500-528')
_add('Wisconsin',      '530-549')
_add('Minnesota',      '550-567')
_add('South Dakota',   '570-577')
_add('North Dakota',   '580-588')
_add('Montana',        '590-599')
_add('Illinois',       '600-629')
_add('Missouri',       '630-658')
_add('Kansas',         '660-679')
_add('Nebraska',       '680-693')
_add('Louisiana',      '700-714')
_add('Arkansas',       '716-729')
_add('Oklahoma',       '730-749')
_add('Texas',          '750-799')
_add('Colorado',       '800-816')
_add('Wyoming',        '820-831')
_add('Idaho',          '832-838')
_add('Utah',           '840-847')
_add('Arizona',        '850-865')
_add('New Mexico',     '870-885')
_add('Nevada',         '889-898')
_add('California',     '900-961')
_add('Hawaii',         '967-968')
_add('Oregon',         '970-979')
_add('Washington',     '980-994')
_add('Alaska',         '995-999')

# Canadian province from postal prefix (first letter)
CA_POSTAL_PREFIX = {
    'A': 'Newfoundland and Labrador',
    'B': 'Nova Scotia',
    'C': 'Prince Edward Island',
    'E': 'New Brunswick',
    'G': 'Quebec', 'H': 'Quebec', 'J': 'Quebec',
    'K': 'Ontario', 'L': 'Ontario', 'M': 'Ontario', 'N': 'Ontario', 'P': 'Ontario',
    'R': 'Manitoba',
    'S': 'Saskatchewan',
    'T': 'Alberta',
    'V': 'British Columbia',
    'X': 'Northwest Territories',
    'Y': 'Yukon',
}

def zip_to_state(zipcode, country):
    z = str(zipcode).strip()
    if not z:
        return ''
    if country in ('United States', ''):
        digits = re.sub(r'\D', '', z)[:5]
        prefix = digits[:3]
        return US_ZIP_PREFIX.get(prefix, '')
    if country == 'Canada':
        letter = z[0].upper()
        return CA_POSTAL_PREFIX.get(letter, '')
    return ''

# Build zip → state map from records that already have both
zip_state = {}
for rec in deduped:
    if rec['zip'] and rec['state']:
        z = str(rec['zip']).strip().zfill(5)[:5]
        zip_state[z] = rec['state']

# Build city+country → state map from existing data
city_country_state = {}
for rec in deduped:
    if rec['city'] and rec['state'] and rec['country']:
        key = (rec['city'].lower(), rec['country'])
        city_country_state[key] = rec['state']

# Apply lookups to records missing state
filled_state = 0
for rec in deduped:
    if rec['state']:
        continue
    # 1. Try zip→state from our data
    if rec['zip']:
        z = str(rec['zip']).strip().zfill(5)[:5]
        if z in zip_state:
            rec['state'] = zip_state[z]
            filled_state += 1
            continue
    # 2. Try zip→state from prefix tables
    if rec['zip']:
        s = zip_to_state(rec['zip'], rec['country'])
        if s:
            rec['state'] = s
            filled_state += 1
            continue
    # 3. Try city+country→state from our data
    if rec['city'] and rec['country']:
        key = (rec['city'].lower(), rec['country'])
        if key in city_country_state:
            rec['state'] = city_country_state[key]
            filled_state += 1

print(f"Filled {filled_state} missing states via zip/city lookup")

# Clean up streets that are just country/country-like values
bad_street_values = {'united states', 'canada', 'united kingdom', 'australia', 'n/a', ''}
for rec in deduped:
    if rec['street'].lower() in bad_street_values:
        rec['street'] = ''

# ── write output ──────────────────────────────────────────────────────────────

# ── fill missing zips from city+state lookup ─────────────────────────────────

# Build city+state → zip from records that already have all three
city_state_zip = {}
for rec in deduped:
    if rec['city'] and rec['state'] and rec['zip']:
        key = (rec['city'].lower(), rec['state'].lower())
        city_state_zip[key] = rec['zip']

filled_zip = 0
for rec in deduped:
    if not rec['zip'] and rec['city'] and rec['state']:
        key = (rec['city'].lower(), rec['state'].lower())
        if key in city_state_zip:
            rec['zip'] = city_state_zip[key]
            filled_zip += 1

print(f"Filled {filled_zip} missing zips via city+state lookup")

# ── Build full address string
for rec in deduped:
    parts = [p for p in [rec['street'], rec['city'], rec['state'], rec['zip'], rec['country']] if p]
    rec['full_address'] = ', '.join(parts)

# Sort: country → state → city → company name
deduped.sort(key=lambda r: (r['country'].lower(), r['state'].lower(), r['city'].lower(), r['company_name'].lower()))

out_path = os.path.join(BASE, 'Companies_Final.csv')

# Human-friendly column names
col_map = {
    'company_name': 'Company Name',
    'website':      'Website',
    'phone':        'Phone',
    'street':       'Street Address',
    'city':         'City',
    'state':        'State / Province',
    'country':      'Country',
    'zip':          'Zip / Postal Code',
    'full_address': 'Full Address',
    'linkedin':     'LinkedIn URL',
    'industry':     'Industry',
    'source':       'Source',
}
fieldnames = list(col_map.keys())

with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=[col_map[k] for k in fieldnames])
    writer.writeheader()
    for rec in deduped:
        writer.writerow({col_map[k]: rec[k] for k in fieldnames})

print(f"\nOutput written to: {out_path}")

# ── quick quality report ──────────────────────────────────────────────────────
missing_city    = sum(1 for r in deduped if not r['city'])
missing_state   = sum(1 for r in deduped if not r['state'])
missing_country = sum(1 for r in deduped if not r['country'])
missing_zip     = sum(1 for r in deduped if not r['zip'])
missing_street  = sum(1 for r in deduped if not r['street'])

print(f"\nQuality report ({len(deduped)} companies):")
print(f"  Missing city:    {missing_city}")
print(f"  Missing state:   {missing_state}")
print(f"  Missing country: {missing_country}")
print(f"  Missing zip:     {missing_zip}")
print(f"  Missing street:  {missing_street}")
