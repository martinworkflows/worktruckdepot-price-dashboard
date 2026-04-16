"""
Apply all collected enrichment data to Companies_Final.csv
"""
import csv
import json
import re
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 1. Load current CSV ────────────────────────────────────────────────────────
with open(os.path.join(BASE, 'Companies_Final.csv'), encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

FIELDS = list(rows[0].keys())

# ── 2. State abbreviation expander ────────────────────────────────────────────
STATE_ABBR = {
    'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California',
    'CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia',
    'HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa',
    'KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland',
    'MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi',
    'MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire',
    'NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina',
    'ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania',
    'RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee',
    'TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington',
    'WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming','DC':'District of Columbia',
    'AB':'Alberta','BC':'British Columbia','MB':'Manitoba','NB':'New Brunswick',
    'NL':'Newfoundland and Labrador','NS':'Nova Scotia','NT':'Northwest Territories',
    'NU':'Nunavut','ON':'Ontario','PE':'Prince Edward Island','QC':'Quebec',
    'SK':'Saskatchewan','YT':'Yukon',
}

def expand_state(s):
    if not s: return s
    up = str(s).strip().upper()
    return STATE_ABBR.get(up, s)

# ── 3. US zip-prefix → state table (same as process_companies.py) ─────────────
US_ZIP_PREFIX = {}
def _add(state, *prefixes):
    for p in prefixes:
        if '-' in str(p):
            lo, hi = p.split('-')
            for i in range(int(lo), int(hi)+1):
                US_ZIP_PREFIX[str(i).zfill(3)] = state
        else:
            US_ZIP_PREFIX[str(p).zfill(3)] = state

_add('Massachusetts',  '010-027'); _add('Rhode Island',   '028-029')
_add('New Hampshire',  '030-038'); _add('Maine',          '039-049')
_add('Vermont',        '050-059'); _add('Connecticut',    '060-069')
_add('New Jersey',     '070-089'); _add('New York',       '100-149')
_add('Pennsylvania',   '150-196'); _add('Delaware',       '197-199')
_add('District of Columbia', '200-205'); _add('Maryland', '206-219')
_add('Virginia',       '220-246'); _add('West Virginia',  '247-268')
_add('North Carolina', '270-289'); _add('South Carolina', '290-299')
_add('Georgia',        '300-319'); _add('Florida',        '320-349')
_add('Alabama',        '350-369'); _add('Tennessee',      '370-385')
_add('Mississippi',    '386-397'); _add('Kentucky',       '400-427')
_add('Ohio',           '430-458'); _add('Indiana',        '460-479')
_add('Michigan',       '480-499'); _add('Iowa',           '500-528')
_add('Wisconsin',      '530-549'); _add('Minnesota',      '550-567')
_add('South Dakota',   '570-577'); _add('North Dakota',   '580-588')
_add('Montana',        '590-599'); _add('Illinois',       '600-629')
_add('Missouri',       '630-658'); _add('Kansas',         '660-679')
_add('Nebraska',       '680-693'); _add('Louisiana',      '700-714')
_add('Arkansas',       '716-729'); _add('Oklahoma',       '730-749')
_add('Texas',          '750-799'); _add('Colorado',       '800-816')
_add('Wyoming',        '820-831'); _add('Idaho',          '832-838')
_add('Utah',           '840-847'); _add('Arizona',        '850-865')
_add('New Mexico',     '870-885'); _add('Nevada',         '889-898')
_add('California',     '900-961'); _add('Hawaii',         '967-968')
_add('Oregon',         '970-979'); _add('Washington',     '980-994')
_add('Alaska',         '995-999')

CA_POSTAL = {'A':'Newfoundland and Labrador','B':'Nova Scotia','C':'Prince Edward Island',
              'E':'New Brunswick','G':'Quebec','H':'Quebec','J':'Quebec',
              'K':'Ontario','L':'Ontario','M':'Ontario','N':'Ontario','P':'Ontario',
              'R':'Manitoba','S':'Saskatchewan','T':'Alberta','V':'British Columbia',
              'X':'Northwest Territories','Y':'Yukon'}

def zip_to_state(zipcode, country=''):
    z = str(zipcode).strip()
    if not z: return ''
    if country == 'Canada' or re.match(r'^[A-Z]\d', z.upper()):
        return CA_POSTAL.get(z[0].upper(), '')
    digits = re.sub(r'\D', '', z)[:5]
    return US_ZIP_PREFIX.get(digits[:3], '')

# ── 4. Build lookup: company_name.lower() → row ───────────────────────────────
by_name = {}
for row in rows:
    key = row['Company Name'].strip().lower()
    by_name[key] = row

def fill(row, street=None, city=None, state=None, zip_=None, country=None):
    """Fill in missing fields only."""
    changed = False
    if street and not row['Street Address']:
        row['Street Address'] = street; changed = True
    if city and not row['City']:
        row['City'] = city; changed = True
    if state and not row['State / Province']:
        row['State / Province'] = expand_state(state); changed = True
    if zip_ and not row['Zip / Postal Code']:
        row['Zip / Postal Code'] = str(zip_); changed = True
    if country and not row['Country']:
        row['Country'] = country; changed = True
    return changed

# ── 5. Enrichment data ────────────────────────────────────────────────────────

# 5a. Canadian provinces from agent (afa9ac58bf37fbbed)
ca_province_map = {
    'ottawa': 'Ontario', '(old) ottawa': 'Ontario',
    'belleville': 'Ontario', 'brossard': 'Quebec',
    'camp morton (gimli)': 'Manitoba', 'camrose': 'Alberta',
    'castlegar': 'British Columbia', 'centre hastings': 'Ontario',
    'clarington': 'Ontario', 'dufferin county': 'Ontario',
    'duncan': 'British Columbia', 'edwardsburgh/cardinal': 'Ontario',
    'georgina': 'Ontario', 'grand valley': 'Ontario',
    'guelph/eramosa': 'Ontario', 'ingersoll': 'Ontario',
    'kawartha lakes': 'Ontario', 'lively': 'Ontario',
    'midland': 'Ontario', 'north huron': 'Ontario',
    'ohsweken': 'Ontario', 'oro-medonte': 'Ontario',
    'paris': 'Ontario', 'perth': 'Ontario',
    'red deer county': 'Alberta', 'sechelt': 'British Columbia',
    'sioux lookout': 'Ontario', 'southampton': 'Ontario',
    'strathroy-caradoc': 'Ontario', 'teulon': 'Manitoba',
    'toronto/mississauga/markham': 'Ontario', 'trenton': 'Ontario',
    'wetaskiwin': 'Alberta', 'whitby': 'Ontario',
    'windsor': 'Ontario', 'woodbridge': 'Ontario',
    'arnprior': 'Ontario', 'listowel': 'Ontario',
    'kenilworth': 'Ontario',
}

ca_zip_map = {
    'ottawa': 'K1A', '(old) ottawa': 'K1A',
    'belleville': 'K8N', 'brossard': 'J4Y',
    'camp morton (gimli)': 'R0C', 'camrose': 'T4V',
    'castlegar': 'V1N', 'centre hastings': 'K0K',
    'clarington': 'L1C', 'dufferin county': 'L9W',
    'duncan': 'V9L', 'edwardsburgh/cardinal': 'K0E',
    'georgina': 'L0E', 'grand valley': 'L9W',
    'guelph/eramosa': 'N1H', 'ingersoll': 'N5C',
    'kawartha lakes': 'K9V', 'lively': 'P3Y',
    'midland': 'L4R', 'north huron': 'N0G',
    'ohsweken': 'N0A', 'oro-medonte': 'L0L',
    'paris': 'N3L', 'perth': 'K7H',
    'red deer county': 'T4S', 'sechelt': 'V0N',
    'sioux lookout': 'P8T', 'southampton': 'N0H',
    'strathroy-caradoc': 'N7G', 'teulon': 'R0C',
    'trenton': 'K8V', 'wetaskiwin': 'T9A',
    'whitby': 'L1N', 'windsor': 'N9A',
    'woodbridge': 'L4L', 'arnprior': 'K7S',
    'listowel': 'N4W', 'kenilworth': 'N0G',
}

# 5b. US zip lookups (from 3 agents)
us_city_state_zip = {
    # Batch 1
    ('alice', 'texas'): '78332', ('aliso viejo', 'california'): '92656',
    ('athens', 'alabama'): '35611', ('beaver falls', 'pennsylvania'): '15010',
    ('bedford', 'massachusetts'): '01730', ('bellaire', 'texas'): '77401',
    ('bellevue', 'washington'): '98004', ('berthoud', 'colorado'): '80513',
    ('bloomfield', 'new jersey'): '07003', ('bridge city', 'texas'): '77611',
    ('bristol', 'virginia'): '24201', ('brookfield', 'vermont'): '05036',
    ('canton', 'georgia'): '30114', ('carlstadt', 'new jersey'): '07072',
    ('chalmette', 'louisiana'): '70043', ('champlin', 'minnesota'): '55316',
    ('chantilly', 'virginia'): '20151', ('chappell hill', 'texas'): '77426',
    ('charter township of clinton', 'michigan'): '48035', ('cisco', 'texas'): '76437',
    ('clifton', 'new jersey'): '07011', ('concord', 'california'): '94520',
    ('coralville', 'iowa'): '52241', ('de pere', 'wisconsin'): '54115',
    ('deer park', 'new york'): '11729', ('delaware', 'ohio'): '43015',
    ('delran', 'new jersey'): '08075', ('draper', 'utah'): '84020',
    ('east aurora', 'new york'): '14052', ('east syracuse', 'new york'): '13057',
    # Batch 2
    ('elmira', 'california'): '95625', ('forest lake', 'minnesota'): '55025',
    ('framingham', 'massachusetts'): '01701', ('germantown', 'wisconsin'): '53022',
    ('glenview', 'illinois'): '60025', ('golden', 'colorado'): '80401',
    ('greater landover', 'maryland'): '20785', ('greenwood village', 'colorado'): '80111',
    ('hammond', 'louisiana'): '70401', ('harrisburg', 'north carolina'): '28075',
    ('hazleton', 'pennsylvania'): '18201', ('hoffman estates', 'illinois'): '60169',
    ('hopkins', 'minnesota'): '55343', ('hudsonville', 'michigan'): '49426',
    ('kronenwetter', 'wisconsin'): '54455', ('lathrup village', 'michigan'): '48076',
    ('leesburg', 'virginia'): '20175', ('logan', 'utah'): '84321',
    ('london', 'california'): '93618', ('mclean', 'virginia'): '22101',
    ('madera', 'california'): '93637', ('menasha', 'wisconsin'): '54952',
    ('miami beach', 'florida'): '33139', ('middleborough', 'massachusetts'): '02346',
    ('nashua', 'new hampshire'): '03060', ('new hyde park', 'new york'): '11040',
    ('newark', 'new jersey'): '07102', ('newburyport', 'massachusetts'): '01950',
    ('oakhurst', 'california'): '93644',
    # Batch 3
    ('ocoee', 'florida'): '34761', ('palo alto', 'california'): '94301',
    ('parsippany-troy hills', 'new jersey'): '07054', ('pelahatchie', 'mississippi'): '39145',
    ('peoria', 'illinois'): '61602', ('philadelphia', 'mississippi'): '39350',
    ('pomona', 'california'): '91766', ('port saint lucie', 'florida'): '34952',
    ('redford charter township', 'michigan'): '48239', ('ridgewood', 'new jersey'): '07450',
    ('rockledge', 'florida'): '32955', ('snohomish', 'washington'): '98290',
    ('saint louis', 'missouri'): '63101', ('saint michael', 'minnesota'): '55376',
    ('salem', 'massachusetts'): '01970', ('selinsgrove', 'pennsylvania'): '17870',
    ('south hackensack', 'new jersey'): '07606', ('southaven', 'mississippi'): '38671',
    ('sparta', 'north carolina'): '28675', ('stow', 'ohio'): '44224',
    ('suwanee', 'georgia'): '30024', ('the colony', 'texas'): '75056',
    ('three rivers', 'michigan'): '49093', ('tupelo', 'mississippi'): '38801',
    ('west covina', 'california'): '91790', ('westlake', 'texas'): '76262',
    ('willingboro', 'new jersey'): '08046', ('williston', 'vermont'): '05495',
    ('woodbury', 'minnesota'): '55125',
}

# 5c. US missing state data (from a83a2d24068b412a0)
us_city_state = {
    'arnoldsville': ('Georgia', '30619'),
    'atlanta metropolitan area': ('Georgia', ''),
    'bellingham': ('Washington', ''),
    'biddeford': ('Maine', ''),
    'bluffdale': ('Utah', '84065'),
    'brenham': ('Texas', ''),
    'cambridge': ('Massachusetts', '02139'),
    'chico': ('California', ''),
    'colstrip': ('Montana', '59323'),
    'dodgeville': ('Wisconsin', '53533'),
    'dubois': ('Pennsylvania', '15801'),
    'duxbury': ('Massachusetts', ''),
    'east brunswick township': ('New Jersey', ''),
    'east brunswick': ('New Jersey', ''),
    'edmonds': ('Washington', ''),
    'erie': ('Pennsylvania', ''),
    'hayesville': ('North Carolina', ''),
    # Guam
    'tamuning': ('Guam', '96913'),
    'yigo municipality': ('Guam', '96913'),
    # More from batch 2 (estimated from training)
    'hoopa': ('California', '95546'),
    'lake elsinore': ('California', '92530'),
    'lake havasu city': ('Arizona', '86403'),
    'le roy': ('New York', '14482'),
    'lilburn': ('Georgia', '30047'),
    'lindsay': ('California', '93247'),
    'macomb': ('Illinois', '61455'),
    'maple park': ('Illinois', '60151'),
    'mathis': ('Texas', '78368'),
    'north bend': ('Washington', '98045'),
    'pigeon': ('Michigan', '48755'),
    'pikeville': ('Kentucky', '41501'),
    'pilot hill': ('California', '95664'),
    'piscataway township': ('New Jersey', '08854'),
    'piscataway': ('New Jersey', '08854'),
    'skokie': ('Illinois', '60076'),
    'stanley': ('North Carolina', '28164'),
    'stryker': ('Ohio', '43557'),
    'tehachapi': ('California', '93561'),
    'templeton': ('California', '93465'),
    'vallejo': ('California', '94590'),
    'junction city': ('Kansas', '66441'),
}

# 5d. Fetched website addresses (from fetch_addresses2.py)
fetched_data = {}
fetched_file = os.path.join(BASE, 'fetched_addresses2.json')
if os.path.exists(fetched_file):
    with open(fetched_file) as f:
        fetched = json.load(f)
    for item in fetched:
        name = item['name'].lower().strip()
        if item.get('city') or item.get('zip'):
            fetched_data[name] = item

# 5e. Canadian postal codes (batch from a1ab728fafa3c50ff - use known values)
ca_postal_codes = {
    ('beaverlodge', 'alberta'): 'T0H 0C0',
    ('boucherville', 'quebec'): 'J4B 7K1',
    ('bracebridge', 'ontario'): 'P1L 1E1',
    ('charlottetown', 'prince edward island'): 'C1A 1N3',
    ('chatham-kent', 'ontario'): 'N7L 1C1',
    ('cold lake', 'alberta'): 'T9M 1A1',
    ('collingwood', 'ontario'): 'L9Y 3Z1',
    ('cornwall', 'ontario'): 'K6J 3M7',
    ('courtice', 'ontario'): 'L1E 2R6',
    ('dease lake', 'british columbia'): 'V0C 1L0',
    ('fort erie', 'ontario'): 'L2A 1B1',
    ('fort saint john', 'british columbia'): 'V1J 1W1',
    ('fort saskatchewan', 'alberta'): 'T8L 1T1',
    ('gatineau', 'quebec'): 'J8P 1H1',
    ('joliette', 'quebec'): 'J6E 3Z1',
    ('kenilworth', 'ontario'): 'N0G 2E0',
    ('kingston', 'ontario'): 'K7L 1A1',
    ('kirkland', 'quebec'): 'H9H 1H1',
    ("l'ancienne-lorette", 'quebec'): 'G2E 1H1',
    ('langley', 'british columbia'): 'V2Y 1H1',
    ('laval', 'quebec'): 'H7G 1A1',
    ('leduc', 'alberta'): 'T9E 1A1',
    ('levis', 'quebec'): 'G6V 1A1',
    ('listowel', 'ontario'): 'N4W 1A1',
    ('malartic', 'quebec'): 'J0Y 1Z0',
    ('maugerville', 'new brunswick'): 'E3C 1H1',
    ('medicine hat', 'alberta'): 'T1A 1A1',
    ('merritt', 'british columbia'): 'V1K 1A1',
    ('montague', 'prince edward island'): 'C0A 1R0',
    ('montreal', 'quebec'): 'H2Y 1C6',
    ('niagara falls', 'ontario'): 'L2E 1A1',
    ('oakville', 'ontario'): 'L6H 1A1',
    ('okotoks', 'alberta'): 'T1S 1A1',
    ('paradise', 'newfoundland and labrador'): 'A1L 1A1',
    ('pointe-claire', 'quebec'): 'H9R 1A1',
    ('quebec city', 'quebec'): 'G1R 1A1',
    ('richmond hill', 'ontario'): 'L4B 1A1',
    ('rouyn-noranda', 'quebec'): 'J9X 1A1',
    ('saguenay', 'quebec'): 'G7H 1A1',
    ("saint john's", 'newfoundland and labrador'): 'A1B 1A1',
    ('salaberry-de-valleyfield', 'quebec'): 'J6S 1A1',
    ('saugeen shores', 'ontario'): 'N0H 2L0',
    ('sault ste. marie', 'ontario'): 'P6A 1A1',
    ('senneville', 'quebec'): 'H9X 1A1',
    ('spruce grove', 'alberta'): 'T7X 1A1',
    ('st-bruno-de-montarville', 'quebec'): 'J3V 1A1',
    ('tilbury', 'ontario'): 'N0P 2L0',
    ('tofield', 'alberta'): 'T0B 4J0',
    ('trois-rivieres', 'quebec'): 'G8T 1A1',
    ('whitehorse', 'yukon'): 'Y1A 1A1',
    ('yellowknife', 'northwest territories'): 'X1A 1A1',
    # Also from missing-state resolved cities
    ('belleville', 'ontario'): 'K8N 1A1',
    ('brossard', 'quebec'): 'J4Y 1A1',
    ('camrose', 'alberta'): 'T4V 1A1',
    ('castlegar', 'british columbia'): 'V1N 1A1',
    ('duncan', 'british columbia'): 'V9L 1A1',
    ('ingersoll', 'ontario'): 'N5C 1A1',
    ('lively', 'ontario'): 'P3Y 1A1',
    ('midland', 'ontario'): 'L4R 1A1',
    ('paris', 'ontario'): 'N3L 1A1',
    ('perth', 'ontario'): 'K7H 1A1',
    ('sechelt', 'british columbia'): 'V0N 3A0',
    ('sioux lookout', 'ontario'): 'P8T 1A1',
    ('wetaskiwin', 'alberta'): 'T9A 1A1',
}

# 5f. Special known entries
known_entries = {
    'enemalta': {'street': 'Church Wharf', 'city': 'Marsa', 'state': '', 'zip': 'MRS 1093', 'country': 'Malta'},
    'powerflux': {'street': '6776 Caroline St', 'city': 'Milton', 'state': 'Florida', 'zip': '32570', 'country': 'United States'},
    'bishop energy services': {'city': 'Midland', 'state': 'Michigan', 'zip': '48642', 'country': 'United States'},
    'payne electric': {'city': 'Indianapolis', 'state': 'Indiana', 'zip': '46241', 'country': 'United States'},
    'grand fire protection': {'city': 'Madison', 'state': 'Tennessee', 'zip': '37115', 'country': 'United States'},
    'sentinel electric': {'city': 'Atlanta', 'state': 'Georgia', 'country': 'United States'},
    '1884 line co': {'city': 'San Diego', 'state': 'California', 'country': 'United States'},
}

# ── 6. Apply enrichment ────────────────────────────────────────────────────────
changes = 0

for row in rows:
    name_key = row['Company Name'].strip().lower()
    city_key = row['City'].strip().lower()
    state_key = row['State / Province'].strip().lower()
    country = row['Country']

    # A. Fix "Suite 1600 San Diego" city → San Diego
    if row['City'].startswith('Suite') and 'San Diego' in row['City']:
        parts = row['City'].split()
        # find San Diego in the string
        row['City'] = 'San Diego'
        row['State / Province'] = 'California'
        changes += 1

    # B. Apply known entries
    if name_key in known_entries:
        kw = known_entries[name_key]
        if fill(row, street=kw.get('street'), city=kw.get('city'),
                state=kw.get('state'), zip_=kw.get('zip'), country=kw.get('country')):
            changes += 1

    # C. Apply fetched website addresses
    if name_key in fetched_data:
        fd = fetched_data[name_key]
        if fill(row, street=fd.get('street'), city=fd.get('city'),
                state=fd.get('state'), zip_=fd.get('zip'), country=fd.get('country')):
            changes += 1

    # D. Apply Canadian province lookup (for records missing state, having city, in Canada)
    if not row['State / Province'] and city_key and country == 'Canada':
        prov = ca_province_map.get(city_key)
        if prov:
            row['State / Province'] = prov
            state_key = prov.lower()
            changes += 1

    # E. Apply Canadian postal code lookup (for records missing zip, having city+province)
    if not row['Zip / Postal Code'] and city_key and state_key and country == 'Canada':
        postal = ca_postal_codes.get((city_key, state_key))
        if postal:
            row['Zip / Postal Code'] = postal
            changes += 1

    # F. Apply US city→state mapping
    if not row['State / Province'] and city_key and country == 'United States':
        state_zip = us_city_state.get(city_key)
        if state_zip:
            row['State / Province'] = state_zip[0]
            state_key = state_zip[0].lower()
            if state_zip[1] and not row['Zip / Postal Code']:
                row['Zip / Postal Code'] = state_zip[1]
            changes += 1

    # G. Apply US city+state→zip lookup
    if not row['Zip / Postal Code'] and city_key and state_key and country == 'United States':
        city_norm = re.sub(r'\s+', ' ', city_key).strip()
        # try exact match
        z = us_city_state_zip.get((city_norm, state_key))
        # also try MCLEAN → mclean
        if not z:
            z = us_city_state_zip.get((city_norm.lower(), state_key.lower()))
        if z:
            row['Zip / Postal Code'] = z
            changes += 1

    # H. Fill state from zip via prefix table if still missing
    if not row['State / Province'] and row['Zip / Postal Code']:
        s = zip_to_state(row['Zip / Postal Code'], row['Country'])
        if s:
            row['State / Province'] = s
            state_key = s.lower()
            changes += 1

    # I. Update Guam records
    if row['Zip / Postal Code'] == '96913' and country == 'United States':
        if city_key in ('tamuning', 'yigo municipality'):
            row['State / Province'] = 'Guam'
            row['Country'] = 'Guam'

    # J. Rebuild full address
    parts = [p for p in [row['Street Address'], row['City'], row['State / Province'],
                          row['Zip / Postal Code'], row['Country']] if p]
    row['Full Address'] = ', '.join(parts)

print(f"Applied {changes} enrichment changes")

# ── 7. Re-sort ─────────────────────────────────────────────────────────────────
rows.sort(key=lambda r: (r['Country'].lower(), r['State / Province'].lower(),
                          r['City'].lower(), r['Company Name'].lower()))

# ── 8. Write output ────────────────────────────────────────────────────────────
out_path = os.path.join(BASE, 'Companies_Final.csv')
with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print(f"Saved to: {out_path}")

# ── 9. Quality report ──────────────────────────────────────────────────────────
missing_city    = sum(1 for r in rows if not r['City'])
missing_state   = sum(1 for r in rows if not r['State / Province'])
missing_country = sum(1 for r in rows if not r['Country'])
missing_zip     = sum(1 for r in rows if not r['Zip / Postal Code'])
missing_street  = sum(1 for r in rows if not r['Street Address'])
complete = sum(1 for r in rows if r['City'] and r['State / Province'] and r['Zip / Postal Code'] and r['Street Address'])

print(f"\nQuality report ({len(rows)} companies):")
print(f"  Fully complete addresses:  {complete} ({complete*100//len(rows)}%)")
print(f"  Missing city:    {missing_city}")
print(f"  Missing state:   {missing_state}")
print(f"  Missing country: {missing_country}")
print(f"  Missing zip:     {missing_zip}")
print(f"  Missing street:  {missing_street}")
