"""
Enhanced address fetcher — tries schema.org JSON-LD first, then text patterns.
"""
import urllib.request
import urllib.error
import re
import json
import time

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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
}

def fetch(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(200000)
            charset = r.headers.get_content_charset() or 'utf-8'
            return data.decode(charset, errors='replace')
    except:
        return None

def try_pages(base):
    base = base.rstrip('/')
    for path in ['/contact', '/contact-us', '/about', '/about-us', '']:
        html = fetch(base + path)
        if html:
            return html
    return None

def extract_jsonld(html):
    """Extract address from schema.org JSON-LD."""
    blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                        html, re.DOTALL | re.IGNORECASE)
    for block in blocks:
        try:
            data = json.loads(block)
            # Handle list
            if isinstance(data, list):
                data = data[0]
            # Could be nested in @graph
            if '@graph' in data:
                for item in data['@graph']:
                    addr = _parse_schema_addr(item)
                    if addr:
                        return addr
            return _parse_schema_addr(data)
        except:
            continue
    return None

def _parse_schema_addr(data):
    addr_obj = data.get('address') or data.get('location', {})
    if isinstance(addr_obj, dict):
        street  = addr_obj.get('streetAddress', '')
        city    = addr_obj.get('addressLocality', '')
        region  = addr_obj.get('addressRegion', '')
        postal  = addr_obj.get('postalCode', '')
        country = addr_obj.get('addressCountry', '')
        if city or postal or street:
            state = STATE_ABBR.get(str(region).upper(), region)
            if isinstance(country, dict):
                country = country.get('name', '')
            if country in ('US', 'USA'):
                country = 'United States'
            elif country in ('CA', 'CAN'):
                country = 'Canada'
            return {'street': street, 'city': city, 'state': state,
                    'zip': postal, 'country': country}
    return None

def strip_html(html):
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;', ' ', html)
    html = re.sub(r'&amp;', '&', html)
    html = re.sub(r'&#\d+;', ' ', html)
    html = re.sub(r'&[a-z]+;', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()

def extract_text_addr(text):
    result = {'street': '', 'city': '', 'state': '', 'zip': '', 'country': ''}

    # US: "123 Main St[., ]City[, ]ST 12345"
    m = re.search(
        r'(\d+\s+[A-Za-z0-9 \.#\-]+(?:St|Ave|Blvd|Rd|Dr|Ln|Way|Ct|Pl|Hwy|Pkwy|Suite|Ste|Floor|Fl)[A-Za-z0-9 \.#\-]*)'
        r'[,\s]+([A-Za-z][A-Za-z\s\-\.\']{1,30}?)'
        r'[,\s]+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)',
        text
    )
    if m:
        state = STATE_ABBR.get(m.group(3).upper(), m.group(3))
        country = 'United States' if m.group(3) in STATE_ABBR and m.group(3) not in ('AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT') else (
            'Canada' if m.group(3) in ('AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT') else '')
        return {'street': m.group(1).strip(), 'city': m.group(2).strip(),
                'state': state, 'zip': m.group(4).strip(), 'country': country}

    # Canadian: "123 Street, City, AB A1A 1A1"
    m = re.search(
        r'(\d+\s+[A-Za-z0-9 \.#\-]+)'
        r'[,\s]+([A-Za-z][A-Za-z\s\-\.\']{1,30}?)'
        r'[,\s]+([A-Z]{2})\s+([A-Z]\d[A-Z]\s*\d[A-Z]\d)',
        text
    )
    if m:
        prov = m.group(3).upper()
        state = STATE_ABBR.get(prov, prov)
        return {'street': m.group(1).strip(), 'city': m.group(2).strip(),
                'state': state, 'zip': m.group(4).strip(), 'country': 'Canada'}

    # Fallback: just find a zip
    postal = re.search(r'\b([A-Z]\d[A-Z]\s*\d[A-Z]\d)\b', text)
    if postal:
        result['zip'] = postal.group(1)
        result['country'] = 'Canada'

    zip5 = re.search(r'\b(\d{5})\b', text)
    if zip5 and zip5.group(1) not in ('00000','99999'):
        result['zip'] = zip5.group(1)

    return result

results = []
for name, website in companies:
    print(f"Fetching: {name[:45]}", end=' ... ', flush=True)
    html = try_pages(website)
    addr = {'name': name, 'street': '', 'city': '', 'state': '', 'zip': '', 'country': ''}

    if html:
        # Try JSON-LD first
        jld = extract_jsonld(html)
        if jld and (jld.get('city') or jld.get('zip') or jld.get('street')):
            addr.update(jld)
            print(f"JSON-LD: {jld.get('city','')}, {jld.get('state','')}, {jld.get('zip','')}")
        else:
            # Try text patterns
            text = strip_html(html)
            ta = extract_text_addr(text)
            if ta.get('city') or ta.get('zip'):
                addr.update(ta)
                print(f"TEXT: {ta.get('city','')}, {ta.get('state','')}, {ta.get('zip','')}")
            else:
                print("no address found")
    else:
        print("fetch failed")

    results.append(addr)
    time.sleep(0.4)

with open('fetched_addresses2.json', 'w') as f:
    json.dump(results, f, indent=2)

found = sum(1 for r in results if r.get('city') or r.get('zip'))
print(f"\nDone. Address data found: {found}/{len(results)}")
