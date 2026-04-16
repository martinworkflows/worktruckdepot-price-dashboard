"""
Fetch company websites and extract address data from contact/about pages.
"""
import urllib.request
import urllib.error
import re
import json
import time

# Companies with no address data
companies = [
    ("Acec", "http://ac-ec.ca"),
    ("AY Electrical", "http://ayelectrical.ca"),
    ("Boring Solutions", "http://boringsolutions.ca"),
    ("Conrad Refrigerated Trucking CRT", "http://crtinc.net"),
    ("El-Con Construction", "http://el-con.ca"),
    ("Kaion Energy Solutions", "http://kaionenergy.com"),
    ("KCI Kraft Consulting", "http://kraftconsulting.ca"),
    ("Lakewood Electric", "http://lakewoodelectric.ca"),
    ("Nixon Projects", "http://nixonprojects.ca"),
    ("Premier Electrical Technician Inc", "http://premierelectrical.ca"),
    ("Septic Service", "http://randyhovland.com"),
    ("Tressling", "http://tressling.com"),
    ("Western Municipal Contracting", "http://wmcltd.ca"),
    ("ABIS Construction Data Southeast", "http://constructiondatasoutheast.com"),
    ("ABM Energy", "http://abmenergytech.com"),
    ("Apex Underground Supply", "http://apexundergroundsupply.com"),
    ("Ashlind Contracting", "http://ashlindcontracting.com"),
    ("Bishop Energy Services", "http://bishopenergy.com"),
    ("Copia Power", "http://copiapower.com"),
    ("Delta Utilities", "http://www.deltautilities.com"),
    ("Divergent Management Services", "http://divemanages.com"),
    ("Duprey Electric", "http://dupreyelectric.com"),
    ("Energy Best Rates", "http://energybestrates.com"),
    ("Energy Justice Law and Policy Center", "http://ejlpc.org"),
    ("Frontline Global Services", "http://frontlineglobal.com"),
    ("GRAND Fire Protection", "http://grandfire.net"),
    ("Heberly Engineering", "http://heberlyeng.com"),
    ("ICM PROYECTOS 2001 C.A", "http://www.icmproyectos.com"),
    ("Independent Power Generation", "http://ipg.solar"),
    ("Intelligent Network Sales", "http://intelligentnetworksales.com"),
    ("IOTA", "http://iotainc.com"),
    ("Join Solar", "http://joinsolar.org"),
    ("Lamos Electric", "http://lamoselectric.com"),
    ("Lighting mechanical", "http://lightingmechanical.com"),
    ("Median Energy", "http://medianenergy.com"),
    ("NuGen Electric", "http://nugenelectric.com"),
    ("Payne Electric", "http://payne-electric.com"),
    ("PowerFlux", "http://thepowerflux.com"),
    ("R.A.P. Electric", "http://rapelectric.com"),
    ("ROBERT W YOUNG AND ASSOCIATES", "http://houstonelectricalengineers.com"),
    ("Royalty Renewables", "http://royaltyrenewables.com"),
    ("Saeco Electric AND Utility", "http://saecoelectric.com"),
    ("SAGE Right of Way Management", "http://thesageco.com"),
    ("Salazar Electric", "http://salazar-electric.com"),
    ("Sentinel Electric", "http://sentinelelectricinc.com"),
    ("Solar Ready", "http://gosolarready.com"),
    ("Sustainable Roofing AND Restoration", "http://sustainable-roofing.com"),
    ("TMNG MEMBER OF TAHAL GROUP", "http://tmng.co.il"),
    ("TRC SQUARED CONSULTING", "http://trcsquared.com"),
    ("Unitech Power Transmission", "http://unitech-power.com"),
    ("Universal Clean Energy", "http://universalcleanenergy.com"),
    ("Utility Drones", "http://utilitydronesllc.com"),
    ("Enemalta", "http://www.enemalta.com.mt"),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Common US state abbreviations → full name
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

def strip_html(html):
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;', ' ', html)
    html = re.sub(r'&amp;', '&', html)
    html = re.sub(r'&#\d+;', ' ', html)
    html = re.sub(r'&[a-z]+;', ' ', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()

def fetch_page(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read(100000)  # max 100KB
            charset = r.headers.get_content_charset() or 'utf-8'
            return content.decode(charset, errors='replace')
    except Exception as e:
        return None

def try_contact_urls(base_url):
    """Try base URL and common contact page paths."""
    base = base_url.rstrip('/')
    urls = [
        base + '/contact',
        base + '/contact-us',
        base + '/about',
        base + '/about-us',
        base,
    ]
    for url in urls:
        html = fetch_page(url)
        if html:
            return html
    return None

def extract_address(text):
    """Extract address components from plain text."""
    result = {'street': '', 'city': '', 'state': '', 'zip': '', 'country': ''}

    # US address pattern: "123 Main St, City, ST 12345" or "123 Main St, City, State 12345"
    us_pattern = re.search(
        r'(\d+[^,\n]{3,50}),\s*([A-Za-z][^,\n]{2,30}),\s*([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)',
        text
    )
    if us_pattern:
        result['street']  = us_pattern.group(1).strip()
        result['city']    = us_pattern.group(2).strip()
        state_abbr = us_pattern.group(3).strip().upper()
        result['state']   = STATE_ABBR.get(state_abbr, state_abbr)
        result['zip']     = us_pattern.group(4).strip()
        result['country'] = 'United States'
        return result

    # Canadian address: "123 Main St, City, Province A1A 1A1"
    ca_pattern = re.search(
        r'(\d+[^,\n]{3,50}),\s*([A-Za-z][^,\n]{2,30}),\s*([A-Za-z]{2})\s+([A-Z]\d[A-Z]\s*\d[A-Z]\d)',
        text
    )
    if ca_pattern:
        result['street']  = ca_pattern.group(1).strip()
        result['city']    = ca_pattern.group(2).strip()
        state_abbr = ca_pattern.group(3).strip().upper()
        result['state']   = STATE_ABBR.get(state_abbr, state_abbr)
        result['zip']     = ca_pattern.group(4).strip()
        result['country'] = 'Canada'
        return result

    # Loose US zip pattern: look for 5-digit zip
    zip_match = re.search(r'\b(\d{5})\b', text)
    if zip_match:
        result['zip'] = zip_match.group(1)

    # Loose Canadian postal: A1A 1A1
    postal_match = re.search(r'\b([A-Z]\d[A-Z]\s*\d[A-Z]\d)\b', text)
    if postal_match:
        result['zip'] = postal_match.group(1)
        result['country'] = 'Canada'

    return result

results = []
for name, website in companies:
    print(f"Fetching: {name} ({website})")
    html = try_contact_urls(website)
    if html:
        text = strip_html(html)
        addr = extract_address(text)
        addr['name'] = name
        # If we got something useful, show it
        if any(v for k, v in addr.items() if k != 'name'):
            print(f"  Found: {addr}")
        else:
            print(f"  No address extracted")
    else:
        addr = {'name': name, 'street': '', 'city': '', 'state': '', 'zip': '', 'country': ''}
        print(f"  Could not fetch website")
    results.append(addr)
    time.sleep(0.3)

with open('fetched_addresses.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nDone. Saved {len(results)} results to fetched_addresses.json")
found = sum(1 for r in results if r.get('city') or r.get('zip'))
print(f"Found address data for {found}/{len(results)} companies")
