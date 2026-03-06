"""
Parser déterministe pour PDFs Stellantis/FCA Canada QBC Retail.
Utilise pdfplumber pour extraction directe des tables — ZERO IA.

Trois parsers:
1. parse_retail_programs()  — Finance Prime/Non-Prime (pages ~20-21)
2. parse_sci_lease()        — SCI Lease rates (pages ~28-29)
3. parse_key_incentives()   — Go-to-Market summary (pages 3-4)
"""

import pdfplumber
import re
import logging
from typing import List, Dict, Optional, Tuple
from io import BytesIO

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# BRAND DETECTION
# ═══════════════════════════════════════════════════════════════

BRAND_REVERSED_MAP = {
    'RELSYRHC': 'Chrysler',
    'PEEJ': 'Jeep',
    'EGDOD': 'Dodge',
    'MAR': 'Ram',
    'TAIF': 'Fiat',
}

MODEL_TO_BRAND = [
    ('Grand Wagoneer', 'Jeep'),
    ('Grand Cherokee', 'Jeep'),
    ('Wagoneer S', 'Jeep'),
    ('Wagoneer', 'Jeep'),
    ('Gladiator', 'Jeep'),
    ('Wrangler', 'Jeep'),
    ('Compass', 'Jeep'),
    ('Cherokee', 'Jeep'),
    ('Grand Caravan', 'Chrysler'),
    ('Pacifica', 'Chrysler'),
    ('Durango', 'Dodge'),
    ('Charger', 'Dodge'),
    ('Hornet', 'Dodge'),
    ('Ram ProMaster', 'Ram'),
    ('Ram Promaster', 'Ram'),
    ('ProMaster', 'Ram'),
    ('Promaster', 'Ram'),
    ('Ram Chassis', 'Ram'),
    ('Chassis Cab', 'Ram'),
    ('Ram 1500', 'Ram'),
    ('Ram 2500', 'Ram'),
    ('Ram 3500', 'Ram'),
    ('Ram 4500', 'Ram'),
    ('Ram 5500', 'Ram'),
    ('New Ram', 'Ram'),
    ('Ram', 'Ram'),
    ('FIAT 500e', 'Fiat'),
    ('FIAT', 'Fiat'),
    ('500e', 'Fiat'),
]

MODELS_BY_BRAND = {
    'Chrysler': ['Grand Caravan', 'Pacifica'],
    'Jeep': [
        'Grand Wagoneer', 'Grand Cherokee L', 'Grand Cherokee',
        'Wagoneer S', 'Wagoneer', 'Gladiator', 'Wrangler', 'Compass', 'Cherokee',
    ],
    'Dodge': ['Durango', 'Charger', 'Hornet'],
    'Ram': ['ProMaster', 'Promaster', 'Chassis Cab', '2500/3500', '1500', '2500', '3500', '4500', '5500'],
    'Fiat': ['500e'],
}


def detect_brand_reversed(cell_value: str) -> Optional[str]:
    if not cell_value or not cell_value.strip():
        return None
    return BRAND_REVERSED_MAP.get(cell_value.strip())


def detect_brand_from_model(vehicle_name: str) -> Optional[str]:
    if not vehicle_name:
        return None
    name = vehicle_name.strip()
    for prefix, brand in MODEL_TO_BRAND:
        if name.lower().startswith(prefix.lower()):
            return brand
    return None


def split_model_trim(brand: str, full_name: str) -> Tuple[str, str]:
    full_name = full_name.replace('\n', ' ').strip()
    if full_name.lower().startswith('new '):
        full_name = full_name[4:].strip()
    if brand == 'Ram':
        if full_name.lower().startswith('ram '):
            full_name = full_name[4:].strip()
        m = re.match(r'^(\d+/\d+)\s*(.*)', full_name)
        if m:
            return m.group(1), m.group(2).strip()
        m = re.match(r'^(\d+)\s*(.*)', full_name)
        if m:
            return m.group(1), m.group(2).strip()
    models = MODELS_BY_BRAND.get(brand, [])
    for model in sorted(models, key=len, reverse=True):
        if full_name.lower().startswith(model.lower()):
            trim = full_name[len(model):].strip().lstrip('/').strip()
            return model, trim
    parts = full_name.split(maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ''


# ═══════════════════════════════════════════════════════════════
# VALUE PARSING
# ═══════════════════════════════════════════════════════════════

def parse_dollar(value) -> int:
    if value is None:
        return 0
    s = str(value).strip()
    if not s:
        return 0
    s = re.sub(r'^P\s*', '', s)
    match = re.search(r'\$?([\d,]+)', s)
    if match:
        return int(match.group(1).replace(',', ''))
    return 0


def parse_rate(value) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == '-' or s.lower() in ('n/a', 'none'):
        return None
    match = re.search(r'([\d.]+)\s*%?', s)
    if match:
        return float(match.group(1))
    return None


def _is_retail_data_row(row: list) -> bool:
    if not row or len(row) < 12:
        return False
    col1 = str(row[1]).strip() if row[1] else ''
    if not col1:
        return False
    col1_lower = col1.lower()
    # Exact header/footer patterns (avoid matching vehicle names containing "models")
    if any(p in col1_lower for p in [
        'stackability', 'discount type', 'type of sale',
        '*see', '*consumer', '*note', 'before tax', 'after tax',
        'up to\n', 'sci lease', 'scotiabank',
        'important', '^note', 'non-prime core',
    ]):
        return False
    # Year-model headers like "2026 MODELS" or "2025 MODEL YEAR"
    if re.match(r'^\d{4}\s+(models|model)', col1_lower):
        return False
    # "PROGRAM STACKABILITY" lines
    if col1_lower.startswith('program'):
        return False
    has_data = False
    for cell in row[4:]:
        s = str(cell).strip() if cell else ''
        if '%' in s or '$' in s or s == '-':
            has_data = True
            break
    return has_data


# ═══════════════════════════════════════════════════════════════
# RETAIL FINANCE PARSER
# ═══════════════════════════════════════════════════════════════

def parse_retail_programs(pdf_content: bytes, start_page: int, end_page: int) -> List[Dict]:
    """
    Parse retail financing programs from PDF using pdfplumber.
    Returns list of program dicts matching the existing data schema.
    """
    programs = []

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        total_pages = len(pdf.pages)
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)

        for page_idx in range(start_idx, end_idx):
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if not tables:
                logger.info(f"[RetailParser] Page {page_idx+1}: aucune table")
                continue

            main_table = tables[0]
            num_cols = len(main_table[0]) if main_table else 0
            logger.info(f"[RetailParser] Page {page_idx+1}: {len(main_table)} lignes, {num_cols} cols")

            current_brand = None
            model_year = None

            for row in main_table:
                if not row or len(row) < 12:
                    continue

                # Detect model year
                for cell in row:
                    if cell:
                        cs = str(cell)
                        if '2026' in cs and ('MODEL' in cs.upper() or 'MODELS' in cs.upper()):
                            model_year = 2026
                        elif '2025' in cs and ('MODEL' in cs.upper() or 'MODELS' in cs.upper()):
                            model_year = 2025
                        elif '2024' in cs and ('MODEL' in cs.upper() or 'MODELS' in cs.upper()):
                            model_year = 2024

                # Detect brand from col 0
                brand = detect_brand_reversed(str(row[0]) if row[0] else '')
                if brand:
                    current_brand = brand

                if not _is_retail_data_row(row):
                    continue
                if not model_year:
                    continue

                vehicle_name = str(row[1]).replace('\n', ' ').strip() if row[1] else ''
                if not vehicle_name:
                    continue

                # Fiat 500e appears without brand marker
                inferred = detect_brand_from_model(vehicle_name)
                if inferred:
                    if not current_brand or inferred != current_brand:
                        current_brand = inferred

                if not current_brand:
                    logger.warning(f"[RetailParser] Marque inconnue pour: {vehicle_name}")
                    continue

                model, trim = split_model_trim(current_brand, vehicle_name)

                # Consumer Cash (col 4, sometimes P prefix in col 3)
                consumer_cash = parse_dollar(row[4] if len(row) > 4 else None)
                if not consumer_cash and len(row) > 3:
                    c3 = str(row[3]).strip() if row[3] else ''
                    if '$' in c3:
                        consumer_cash = parse_dollar(c3)

                # Option 1 rates (cols 6-11: 36M, 48M, 60M, 72M, 84M, 96M)
                rate_keys = ['rate_36', 'rate_48', 'rate_60', 'rate_72', 'rate_84', 'rate_96']
                opt1 = {}
                opt1_ok = False
                for key, idx in zip(rate_keys, [6, 7, 8, 9, 10, 11]):
                    if idx < len(row):
                        r = parse_rate(row[idx])
                        opt1[key] = r
                        if r is not None:
                            opt1_ok = True
                if not opt1_ok:
                    opt1 = None

                # Alt Consumer Cash (col 16)
                alt_consumer_cash = parse_dollar(row[16] if len(row) > 16 else None)

                # Option 2 rates (cols 18-23)
                opt2 = {}
                opt2_ok = False
                for key, idx in zip(rate_keys, [18, 19, 20, 21, 22, 23]):
                    if idx < len(row):
                        r = parse_rate(row[idx])
                        opt2[key] = r
                        if r is not None:
                            opt2_ok = True
                if not opt2_ok:
                    opt2 = None

                # Bonus Cash (col 26 for 27-col tables)
                bonus_cash = 0
                if num_cols >= 27 and len(row) > 26:
                    bonus_cash = parse_dollar(row[26])

                programs.append({
                    'brand': current_brand,
                    'model': model,
                    'trim': trim,
                    'year': model_year,
                    'consumer_cash': consumer_cash,
                    'alt_consumer_cash': alt_consumer_cash,
                    'bonus_cash': bonus_cash,
                    'option1_rates': opt1,
                    'option2_rates': opt2,
                })
                logger.info(
                    f"[RetailParser] {current_brand} {model} {trim} ({model_year}) "
                    f"cc=${consumer_cash} alt=${alt_consumer_cash} bonus=${bonus_cash}"
                )

    logger.info(f"[RetailParser] Total programmes extraits: {len(programs)}")
    return programs


# ═══════════════════════════════════════════════════════════════
# SCI LEASE PARSER
# ═══════════════════════════════════════════════════════════════

def parse_sci_lease(pdf_content: bytes, start_page: int, end_page: int) -> Dict:
    """
    Parse SCI Lease rates. Returns {vehicles_2026: [...], vehicles_2025: [...]}.

    PDF structure per page:
    - Table 0 (6 cols): Vehicle names in col 1
    - Table 1 (30 cols): Rate data
      col 2 = Lease Cash, cols 4-12 = Standard rates, cols 19-27 = Alt rates
    - Table 2 (optional): Bonus Cash in col 1 (separate on 2026 pages)
    """
    vehicles_2026 = []
    vehicles_2025 = []
    term_keys = ['24', '27', '36', '39', '42', '48', '51', '54', '60']
    std_indices = list(range(4, 13))
    alt_indices = list(range(19, 28))

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        total_pages = len(pdf.pages)
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)

        for page_idx in range(start_idx, end_idx):
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if len(tables) < 2:
                continue

            names_t = tables[0]
            rates_t = tables[1]
            bonus_t = tables[2] if len(tables) > 2 else None

            # Detect year — check for "YYYY Model Year" at the START of the cell
            model_year = None
            for row in names_t[:5]:
                for cell in row:
                    if cell:
                        cs = str(cell)
                        # Match "2025 Model Year" or "2026 Model Year" at start
                        ym = re.match(r'(\d{4})\s+Model\s+Year', cs)
                        if ym:
                            model_year = int(ym.group(1))
                            break
                        # Fallback: "YYYY\nMODEL YEAR"
                        ym2 = re.match(r'(\d{4})\n', cs)
                        if ym2 and 'MODEL' in cs.upper():
                            model_year = int(ym2.group(1))
                            break
                if model_year:
                    break
            if not model_year:
                continue

            logger.info(f"[SCIParser] Page {page_idx+1}: {model_year}, names={len(names_t)}, rates={len(rates_t)}")

            # Find first data row in rates table
            data_start = None
            for ri, row in enumerate(rates_t):
                for idx in std_indices + alt_indices:
                    if idx < len(row):
                        v = str(row[idx]).strip() if row[idx] else ''
                        if '%' in v or v == '-':
                            data_start = ri
                            break
                if data_start is not None:
                    break
            if data_start is None:
                continue

            rates_cols = len(rates_t[0]) if rates_t else 0
            has_bonus_col = rates_cols >= 30

            for ri in range(data_start, min(len(names_t), len(rates_t))):
                vname = ''
                if ri < len(names_t) and len(names_t[ri]) > 1:
                    vname = str(names_t[ri][1]).replace('\n', ' ').strip() if names_t[ri][1] else ''
                if not vname or '*See' in vname or 'Program Rules' in vname:
                    continue
                # Skip header rows that leak into data range
                vname_lower = vname.lower()
                if any(s in vname_lower for s in [
                    'discount type', 'stackability', 'type of sale',
                    'before tax', 'after tax', 'program period',
                ]):
                    continue

                rr = rates_t[ri]

                lease_cash = parse_dollar(rr[2] if len(rr) > 2 else None)

                std = {}
                std_ok = False
                for k, i in zip(term_keys, std_indices):
                    if i < len(rr):
                        r = parse_rate(rr[i])
                        std[k] = r
                        if r is not None:
                            std_ok = True
                if not std_ok:
                    std = None

                alt = {}
                alt_ok = False
                for k, i in zip(term_keys, alt_indices):
                    if i < len(rr):
                        r = parse_rate(rr[i])
                        alt[k] = r
                        if r is not None:
                            alt_ok = True
                if not alt_ok:
                    alt = None

                bonus = 0
                if has_bonus_col and len(rr) > 29:
                    bonus = parse_dollar(rr[29])
                elif bonus_t and ri < len(bonus_t) and len(bonus_t[ri]) > 1:
                    bonus = parse_dollar(bonus_t[ri][1])

                brand = detect_brand_from_model(vname)
                if not brand:
                    brand = "Unknown"

                vehicle = {
                    'model': vname,
                    'brand': brand,
                    'lease_cash': lease_cash,
                    'standard_rates': std,
                    'alternative_rates': alt,
                }
                if bonus > 0:
                    vehicle['bonus_cash'] = bonus

                target = vehicles_2026 if model_year == 2026 else vehicles_2025
                target.append(vehicle)

    logger.info(f"[SCIParser] Total: {len(vehicles_2026)} v2026 + {len(vehicles_2025)} v2025")
    return {'vehicles_2026': vehicles_2026, 'vehicles_2025': vehicles_2025}


# ═══════════════════════════════════════════════════════════════
# KEY INCENTIVES SUMMARY PARSER
# ═══════════════════════════════════════════════════════════════

def parse_key_incentives(pdf_content: bytes) -> List[Dict]:
    """Parse 'Go to Market - Key Incentives' summary table (pages 3-4)."""
    incentives = []

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        for page_idx in [2, 3]:
            if page_idx >= len(pdf.pages):
                break
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if not tables:
                continue

            main_table = None
            for t in tables:
                if len(t) < 3 or len(t[0]) < 4:
                    continue
                for row in t[:2]:
                    for cell in row:
                        if cell and 'Key Incentives' in str(cell):
                            main_table = t
                            break
                    if main_table:
                        break
                if main_table:
                    break
            if not main_table:
                continue

            num_cols = len(main_table[0])

            # Map columns from header
            inc_col = msg_col = chg_col = None
            for row in main_table[:2]:
                for ci, cell in enumerate(row):
                    if cell:
                        cs = str(cell)
                        if 'Key Incentives' in cs and inc_col is None:
                            inc_col = ci
                        if 'Noted Changes' in cs:
                            chg_col = ci
            if inc_col is None:
                continue
            msg_col = inc_col + 1 if num_cols <= 7 else inc_col + 2

            i = 1
            while i < len(main_table) - 1:
                data_row = main_table[i]
                name_row = main_table[i + 1] if i + 1 < len(main_table) else None
                vname = ''
                if name_row and len(name_row) > 1:
                    vname = str(name_row[1]).strip() if name_row[1] else ''
                if not vname:
                    i += 1
                    continue

                ki = str(data_row[inc_col]).strip() if inc_col < len(data_row) and data_row[inc_col] else ''
                km = str(data_row[msg_col]).strip() if msg_col and msg_col < len(data_row) and data_row[msg_col] else ''
                nc = str(data_row[chg_col]).strip() if chg_col and chg_col < len(data_row) and data_row[chg_col] else ''

                parsed = _parse_incentive_text(ki)
                loyalty = _detect_loyalty(nc)

                ym = re.match(r'(\d{4})\s+(.+)', vname)
                year = int(ym.group(1)) if ym else None
                model_part = ym.group(2) if ym else vname
                brand = detect_brand_from_model(model_part)

                incentives.append({
                    'vehicle': vname,
                    'brand': brand,
                    'year': year,
                    'model': model_part,
                    'key_incentives': ki,
                    'key_messages': km,
                    'noted_changes': nc,
                    'parsed': parsed,
                    'loyalty_reduction': loyalty,
                })
                i += 2

    logger.info(f"[KeyIncentives] {len(incentives)} entrees parsees")
    return incentives


def _parse_incentive_text(text: str) -> Dict:
    if not text:
        return {}
    result = {}
    rm = re.search(r'(\d+\.?\d*)%\s+Financing\s+for\s+(\d+)\s+Months', text, re.IGNORECASE)
    if rm:
        result['rate'] = float(rm.group(1))
        result['term'] = int(rm.group(2))
    cm = re.search(r'Up\s+to\s+\$([\d,]+)\s+Consumer\s+Cash', text, re.IGNORECASE)
    if cm:
        result['consumer_cash'] = int(cm.group(1).replace(',', ''))
    result['has_alternative'] = bool(re.search(r'\bOr\b', text))
    result['as_low_as'] = bool(re.search(r'As\s+low\s+as', text, re.IGNORECASE))
    return result


def _detect_loyalty(text: str) -> float:
    if not text:
        return 0.0
    m = re.search(r'(\d+\.?\d*)%\s+Loyalty\s+Rate\s+Reduction', text, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0



# ═══════════════════════════════════════════════════════════════
# AUTO-DETECTION DES PAGES
# ═══════════════════════════════════════════════════════════════

def auto_detect_pages(pdf_content: bytes) -> Dict:
    """
    Scan le PDF et identifie automatiquement les sections:
    - Finance Prime: pages avec tables de taux retail (25-27 cols, pas NON-PRIME)
    - Non-Prime: pages avec tables retail + keyword NON-PRIME
    - SCI Lease: pages avec tables de taux lease (30 cols)
    - Key Incentives: pages 'Go to Market'

    Returns dict with page ranges (1-indexed):
    {
        'retail_start': 20, 'retail_end': 21,
        'lease_start': 28, 'lease_end': 29,
        'non_prime_start': 24, 'non_prime_end': 25,
        'key_incentive_pages': [3, 4],
        'total_pages': 29,
        'detected_sections': [...]
    }
    """
    result = {
        'retail_start': None, 'retail_end': None,
        'lease_start': None, 'lease_end': None,
        'non_prime_start': None, 'non_prime_end': None,
        'key_incentive_pages': [],
        'total_pages': 0,
        'detected_sections': [],
    }

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        result['total_pages'] = len(pdf.pages)
        retail_pages = []
        non_prime_pages = []
        lease_pages = []
        ki_pages = []

        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = (page.extract_text() or '')[:1000]
            text_upper = text.upper()

            # Key Incentives: "Go to Market" or "Key Incentives" with table
            if 'KEY INCENTIVES' in text_upper and page_num <= 10:
                tables = page.extract_tables()
                if tables and len(tables[0]) >= 3:
                    ki_pages.append(page_num)
                    continue

            # Skip non-data pages (overviews, rules, etc.)
            if 'MODEL YEAR' not in text_upper and 'MODEL\nYEAR' not in text_upper:
                continue

            tables = page.extract_tables()
            if not tables:
                continue

            main_table = tables[0]
            num_cols = len(main_table[0]) if main_table else 0

            is_lease = 'LEASE INCENTIVE PROGRAM' in text_upper
            is_non_prime = 'NON-PRIME' in text_upper or 'NON PRIME' in text_upper

            if is_lease:
                # SCI Lease pages have multi-table structure (names + rates)
                if len(tables) >= 2:
                    lease_pages.append(page_num)
                    result['detected_sections'].append({
                        'page': page_num,
                        'type': 'lease',
                        'year': _detect_year_from_text(text),
                        'tables': len(tables),
                    })
            elif is_non_prime:
                if num_cols >= 20:
                    non_prime_pages.append(page_num)
                    result['detected_sections'].append({
                        'page': page_num,
                        'type': 'non_prime',
                        'year': _detect_year_from_text(text),
                        'cols': num_cols,
                    })
            else:
                # Retail Finance Prime: large table with 25+ cols
                if num_cols >= 20:
                    retail_pages.append(page_num)
                    result['detected_sections'].append({
                        'page': page_num,
                        'type': 'retail_prime',
                        'year': _detect_year_from_text(text),
                        'cols': num_cols,
                    })

        # Set page ranges
        if retail_pages:
            result['retail_start'] = min(retail_pages)
            result['retail_end'] = max(retail_pages)
        if lease_pages:
            result['lease_start'] = min(lease_pages)
            result['lease_end'] = max(lease_pages)
        if non_prime_pages:
            result['non_prime_start'] = min(non_prime_pages)
            result['non_prime_end'] = max(non_prime_pages)
        result['key_incentive_pages'] = ki_pages

    logger.info(
        f"[AutoDetect] Retail={result['retail_start']}-{result['retail_end']}, "
        f"Lease={result['lease_start']}-{result['lease_end']}, "
        f"NonPrime={result['non_prime_start']}-{result['non_prime_end']}, "
        f"KeyIncentives={ki_pages}"
    )
    return result


def _detect_year_from_text(text: str) -> Optional[int]:
    m = re.search(r'(20\d{2})\s+Model\s+Year', text, re.IGNORECASE)
    return int(m.group(1)) if m else None



# ═══════════════════════════════════════════════════════════════
# COVER PAGE PARSER (page 1)
# ═══════════════════════════════════════════════════════════════

def parse_cover_page(pdf_content: bytes) -> Dict:
    """
    Parse la page de couverture (p.1) du PDF pour extraire:
    - Nom(s) d'événement (ex: '4X4 Winter Event', 'Month of Ram')
    - Période du programme
    - Taux loyauté si mentionné
    - Offre No-Payments si mentionnée
    - Message clé du mois
    - Taux vedette (ex: "0% for 72 months")
    """
    result = {
        'event_names': [],
        'program_period': '',
        'program_month': '',
        'program_year': None,
        'loyalty_rate': 0.0,
        'no_payments_days': 0,
        'featured_rate': None,
        'featured_term': None,
        'key_message': '',
        'raw_intro': '',
    }

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        if not pdf.pages:
            return result
        text = pdf.pages[0].extract_text() or ''
        result['raw_intro'] = text

    # Event names: text between single quotes
    events = re.findall(r"['\u2018\u2019]([^'\u2018\u2019]+)['\u2018\u2019]", text)
    result['event_names'] = [e.strip() for e in events if len(e.strip()) > 3]

    # Program period: "February 3, 2026 – March 2, 2026"
    period_m = re.search(
        r'Program Period:\s*\n?\s*(.+?\d{4})\s*[–\-]\s*(.+?\d{4})',
        text, re.IGNORECASE
    )
    if period_m:
        result['program_period'] = f"{period_m.group(1).strip()} - {period_m.group(2).strip()}"

    # Program month/year: "incentive programs for February 2026"
    month_m = re.search(
        r'incentive programs for (\w+)\s+(\d{4})',
        text, re.IGNORECASE
    )
    if month_m:
        result['program_month'] = month_m.group(1)
        result['program_year'] = int(month_m.group(2))

    # Loyalty rate: "up to a 0.5% loyalty rate reduction"
    loyalty_m = re.search(r'(\d+\.?\d*)%\s+loyalty\s+rate\s+reduction', text, re.IGNORECASE)
    if loyalty_m:
        result['loyalty_rate'] = float(loyalty_m.group(1))

    # No payments: "No Finance Payments for 90 Days"
    # Handle newlines in PDF text
    text_flat = ' '.join(text.split())
    payments_m = re.search(r'No Finance Payments\s+for\s+(\d+)\s+Days', text_flat, re.IGNORECASE)
    if payments_m:
        result['no_payments_days'] = int(payments_m.group(1))

    # Featured rate: "as low as 0% for 72 months"
    rate_m = re.search(r'as low as (\d+\.?\d*)%\s+for\s+(\d+)\s+months', text, re.IGNORECASE)
    if rate_m:
        result['featured_rate'] = float(rate_m.group(1))
        result['featured_term'] = int(rate_m.group(2))

    # Key message: paragraph starting with "For January/February/March..."
    msg_m = re.search(r'(For \w+,\s+the .+?)(?:Get your plan|$)', text, re.DOTALL | re.IGNORECASE)
    if msg_m:
        result['key_message'] = ' '.join(msg_m.group(1).split())

    # Brands mentioned on cover page
    all_brands = ['Chrysler', 'Dodge', 'Fiat', 'Jeep', 'Ram']
    result['brands'] = sorted(set(b for b in all_brands if b.lower() in text.lower()))

    logger.info(
        f"[CoverPage] Events={result['event_names']}, "
        f"Month={result['program_month']} {result['program_year']}, "
        f"Loyalty={result['loyalty_rate']}%, NoPayments={result['no_payments_days']}d, "
        f"Brands={result['brands']}"
    )
    return result
