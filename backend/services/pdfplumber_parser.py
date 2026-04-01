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
    # Strip common prefixes
    if full_name.lower().startswith('all-new '):
        full_name = full_name[8:].strip()
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
            # Ensure we match at a word boundary (not "Grand Cherokee L" eating "Laredo")
            after_model = full_name[len(model):]
            if after_model and after_model[0].isalpha():
                continue  # Not a real match - next char is a letter
            trim = after_model.strip().lstrip('/').strip()
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

def _detect_rate_columns(table: list) -> Tuple[Optional[int], Optional[int]]:
    """
    Find the first column index for Option 1 and Option 2 rate headers.
    Looks for '36M' or 'Up to 36M' in header rows.
    Returns (opt1_start_col, opt2_start_col) or (None, None).
    """
    for row in table[:8]:
        opt1_col = None
        opt2_col = None
        for ci, cell in enumerate(row):
            if not cell:
                continue
            cs = str(cell).upper().replace('\n', ' ')
            if '36M' in cs:
                if opt1_col is None:
                    opt1_col = ci
                else:
                    opt2_col = ci
                    return (opt1_col, opt2_col)
    return (None, None)


def _find_names_table(tables: list) -> Optional[list]:
    """
    Find the separate names table (used in March-style PDFs).
    It's the table where col[0] has reversed brand codes (RELSYRHC, PEEJ, etc.)
    or col[1] has vehicle names.
    """
    brand_codes = set(BRAND_REVERSED_MAP.keys())
    for t in tables[1:]:  # Skip table 0 (rates)
        if not t or len(t) < 5 or len(t[0]) < 2:
            continue
        for ri in range(min(10, len(t))):
            c0 = str(t[ri][0]).strip() if t[ri][0] else ''
            if c0 in brand_codes:
                return t
    return None


def _find_bonus_table(tables: list) -> Optional[list]:
    """Find the separate Bonus Cash table (used in March-style PDFs)."""
    for t in tables[1:]:
        if not t or len(t) < 3 or len(t[0]) < 2:
            continue
        for ri in range(min(3, len(t))):
            c1 = str(t[ri][1]).strip() if len(t[ri]) > 1 and t[ri][1] else ''
            if 'Bonus Cash' in c1:
                return t
    return None


def _has_rate_data(row: list, start_col: int) -> bool:
    """Check if a row has rate data (% or -) in the rate columns."""
    for ci in range(start_col, min(start_col + 6, len(row))):
        v = str(row[ci]).strip() if row[ci] else ''
        if '%' in v or v == '-':
            return True
    return False


def parse_retail_programs(pdf_content: bytes, start_page: int, end_page: int) -> List[Dict]:
    """
    Parse retail financing programs from PDF using pdfplumber.
    Handles two layouts:
      - Layout A (Jan/Feb): vehicle names + rates in the same table (25+ cols)
      - Layout B (March): names in a separate table, rates in main table (24 cols)
    Returns list of program dicts matching the existing data schema.
    """
    programs = []
    rate_keys = ['rate_36', 'rate_48', 'rate_60', 'rate_72', 'rate_84', 'rate_96']

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

            # Detect rate column positions
            opt1_start, opt2_start = _detect_rate_columns(main_table)
            if opt1_start is None:
                logger.info(f"[RetailParser] Page {page_idx+1}: no rate headers found")
                continue

            # Consumer cash column is 2 before opt1_start (or 1 before)
            cc_col = opt1_start - 2 if opt1_start >= 2 else 0
            alt_cc_col = opt2_start - 2 if opt2_start and opt2_start >= 2 else None

            logger.info(
                f"[RetailParser] Page {page_idx+1}: {len(main_table)} rows, {num_cols} cols, "
                f"opt1@{opt1_start}, opt2@{opt2_start}, cc@{cc_col}"
            )

            # Detect layout: check if main table has brand codes
            names_table = _find_names_table(tables)
            bonus_table = _find_bonus_table(tables)
            layout = 'B' if names_table is not None else 'A'

            if layout == 'A':
                # ── Layout A: names + rates in same table (Jan/Feb) ──
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

                    inferred = detect_brand_from_model(vehicle_name)
                    if inferred:
                        if not current_brand or inferred != current_brand:
                            current_brand = inferred

                    if not current_brand:
                        continue

                    model, trim = split_model_trim(current_brand, vehicle_name)

                    consumer_cash = parse_dollar(row[cc_col] if cc_col < len(row) else None)
                    if not consumer_cash and cc_col + 1 < len(row):
                        consumer_cash = parse_dollar(row[cc_col + 1])

                    opt1 = {}
                    opt1_ok = False
                    for key, offset in zip(rate_keys, range(6)):
                        idx = opt1_start + offset
                        if idx < len(row):
                            r = parse_rate(row[idx])
                            opt1[key] = r
                            if r is not None:
                                opt1_ok = True
                    if not opt1_ok:
                        opt1 = None

                    alt_consumer_cash = parse_dollar(row[alt_cc_col] if alt_cc_col and alt_cc_col < len(row) else None)

                    opt2 = {}
                    opt2_ok = False
                    if opt2_start:
                        for key, offset in zip(rate_keys, range(6)):
                            idx = opt2_start + offset
                            if idx < len(row):
                                r = parse_rate(row[idx])
                                opt2[key] = r
                                if r is not None:
                                    opt2_ok = True
                    if not opt2_ok:
                        opt2 = None

                    # Bonus Cash: last col or second-to-last
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

            else:
                # ── Layout B: names in separate table (March) ──
                # Detect model year from all tables
                model_year = None
                for t in tables:
                    for row in t[:5]:
                        for cell in row:
                            if cell:
                                cs = str(cell)
                                if '2026' in cs and ('MODEL' in cs.upper() or 'MODELS' in cs.upper()):
                                    model_year = 2026
                                elif '2025' in cs and ('MODEL' in cs.upper() or 'MODELS' in cs.upper()):
                                    model_year = 2025
                                elif '2024' in cs and ('MODEL' in cs.upper() or 'MODELS' in cs.upper()):
                                    model_year = 2024
                    if model_year:
                        break

                if not model_year:
                    logger.info(f"[RetailParser] Page {page_idx+1}: no model year detected")
                    continue

                # Extract vehicle names from names_table
                vehicles = []
                current_brand = None
                for row in names_table:
                    c0 = str(row[0]).strip() if row[0] else ''
                    c1 = str(row[1]).replace('\n', ' ').strip() if len(row) > 1 and row[1] else ''

                    brand = detect_brand_reversed(c0)
                    if brand:
                        current_brand = brand

                    if not c1 or c1.lower().startswith('discount type'):
                        continue

                    inferred = detect_brand_from_model(c1)
                    if inferred:
                        current_brand = inferred

                    if not current_brand:
                        continue

                    vehicles.append((current_brand, c1))

                # Extract rate rows from main table (skip headers)
                rate_rows = []
                for row in main_table:
                    if _has_rate_data(row, opt1_start):
                        rate_rows.append(row)

                # Extract bonus cash rows
                bonus_rows = []
                if bonus_table:
                    for row in bonus_table:
                        c1 = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                        if '$' in c1 or c1 == '' or c1 == '-':
                            bonus_rows.append(parse_dollar(c1))

                logger.info(
                    f"[RetailParser] Layout B: {len(vehicles)} vehicles, "
                    f"{len(rate_rows)} rate rows, {len(bonus_rows)} bonus rows"
                )

                # Zip vehicles with rate rows
                for vi, (brand, vehicle_name) in enumerate(vehicles):
                    if vi >= len(rate_rows):
                        break

                    rr = rate_rows[vi]
                    model, trim = split_model_trim(brand, vehicle_name)

                    consumer_cash = parse_dollar(rr[cc_col] if cc_col < len(rr) else None)

                    opt1 = {}
                    opt1_ok = False
                    for key, offset in zip(rate_keys, range(6)):
                        idx = opt1_start + offset
                        if idx < len(rr):
                            r = parse_rate(rr[idx])
                            opt1[key] = r
                            if r is not None:
                                opt1_ok = True
                    if not opt1_ok:
                        opt1 = None

                    alt_consumer_cash = parse_dollar(rr[alt_cc_col] if alt_cc_col and alt_cc_col < len(rr) else None)

                    opt2 = {}
                    opt2_ok = False
                    if opt2_start:
                        for key, offset in zip(rate_keys, range(6)):
                            idx = opt2_start + offset
                            if idx < len(rr):
                                r = parse_rate(rr[idx])
                                opt2[key] = r
                                if r is not None:
                                    opt2_ok = True
                    if not opt2_ok:
                        opt2 = None

                    bonus_cash = bonus_rows[vi] if vi < len(bonus_rows) else 0

                    programs.append({
                        'brand': brand,
                        'model': model,
                        'trim': trim,
                        'year': model_year,
                        'consumer_cash': consumer_cash,
                        'alt_consumer_cash': alt_consumer_cash,
                        'bonus_cash': bonus_cash,
                        'option1_rates': opt1,
                        'option2_rates': opt2,
                    })

            logger.info(f"[RetailParser] Page {page_idx+1}: {len(programs)} programmes cumulés")

    logger.info(f"[RetailParser] Total programmes extraits: {len(programs)}")
    return programs


# ═══════════════════════════════════════════════════════════════
# SCI LEASE PARSER
# ═══════════════════════════════════════════════════════════════

def parse_sci_lease(pdf_content: bytes, start_page: int, end_page: int) -> Dict:
    """
    Parse SCI Lease rates. Returns {vehicles_2026: [...], vehicles_2025: [...]}.

    PDF structure per page:
    - Table 0 (6-7 cols): Vehicle names in col 1
    - Table 1 (30-31 cols): Rate data
      col 2 = Lease Cash, cols 4-12 = Standard rates, cols 19-27 = Alt rates
    - Table 2 (optional): Bonus Cash (separate on some pages)

    IMPORTANT: The names table and rates table have different numbers of header
    rows, causing a row offset. We build separate filtered lists and zip them.
    """
    vehicles_2026 = []
    vehicles_2025 = []
    term_keys = ['24', '27', '36', '39', '42', '48', '51', '54', '60']
    std_indices = list(range(4, 13))
    alt_indices = list(range(19, 28))

    # Patterns to skip in the names table (headers, footers)
    _skip_patterns = [
        'discount type', 'stackability', 'type of sale',
        'before tax', 'after tax', 'program period',
        'model year', 'fca canada', 'fca qbc', 'program incentiv',
        'color key', '262ql3', 'program rules',
    ]

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        total_pages = len(pdf.pages)
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages, end_page)

        for page_idx in range(start_idx, end_idx):
            page = pdf.pages[page_idx]

            # Quick text pre-filter
            quick_text = (page.extract_text() or '')[:500].upper()
            if 'MODEL YEAR' not in quick_text and 'MODEL\nYEAR' not in quick_text:
                logger.info(f"[SCIParser] Page {page_idx+1}: skipped (no MODEL YEAR)")
                continue

            tables = page.extract_tables()
            if len(tables) < 2:
                continue

            names_t = tables[0]
            rates_t = tables[1]
            bonus_t = tables[2] if len(tables) > 2 else None

            # Detect year
            model_year = None
            for row in names_t[:5]:
                for cell in row:
                    if cell:
                        cs = str(cell)
                        ym = re.match(r'(\d{4})\s+Model\s+Year', cs)
                        if ym:
                            model_year = int(ym.group(1))
                            break
                        ym2 = re.match(r'(\d{4})\n', cs)
                        if ym2 and 'MODEL' in cs.upper():
                            model_year = int(ym2.group(1))
                            break
                if model_year:
                    break
            if not model_year:
                continue

            # ── Build vehicle name list (filtered) ──
            vehicle_names = []
            for row in names_t:
                c1 = str(row[1]).replace('\n', ' ').strip() if len(row) > 1 and row[1] else ''
                if not c1 or '*See' in c1:
                    continue
                if any(p in c1.lower() for p in _skip_patterns):
                    continue
                vehicle_names.append(c1)

            # ── Build rate data rows (filtered) ──
            rate_rows = []
            for row in rates_t:
                has_data = False
                for idx in std_indices + alt_indices:
                    if idx < len(row):
                        v = str(row[idx]).strip() if row[idx] else ''
                        if '%' in v or v == '-':
                            has_data = True
                            break
                if has_data:
                    rate_rows.append(row)

            # ── Build bonus list from separate table ──
            bonus_values = []
            if bonus_t:
                for row in bonus_t:
                    c1 = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    if '$' in c1 or c1 == '' or c1 == '-':
                        bonus_values.append(parse_dollar(c1))

            # Detect bonus column in rates table (last column with "Bonus Cash" header)
            rates_cols = len(rates_t[0]) if rates_t else 0
            bonus_col = None
            for row in rates_t[:8]:
                for ci in range(rates_cols - 1, max(rates_cols - 3, 0), -1):
                    if ci < len(row) and row[ci] and 'Bonus Cash' in str(row[ci]):
                        bonus_col = ci
                        break
                if bonus_col is not None:
                    break

            logger.info(
                f"[SCIParser] Page {page_idx+1}: {model_year}, "
                f"{len(vehicle_names)} vehicles, {len(rate_rows)} rate rows, "
                f"bonus_col={bonus_col}, bonus_t={len(bonus_values) if bonus_values else 0}"
            )

            # ── Zip vehicle names with rate rows ──
            for i, vname in enumerate(vehicle_names):
                if i >= len(rate_rows):
                    break

                rr = rate_rows[i]

                lease_cash = parse_dollar(rr[2] if len(rr) > 2 else None)

                std = {}
                std_ok = False
                for k, idx in zip(term_keys, std_indices):
                    if idx < len(rr):
                        r = parse_rate(rr[idx])
                        std[k] = r
                        if r is not None:
                            std_ok = True
                if not std_ok:
                    std = None

                alt = {}
                alt_ok = False
                for k, idx in zip(term_keys, alt_indices):
                    if idx < len(rr):
                        r = parse_rate(rr[idx])
                        alt[k] = r
                        if r is not None:
                            alt_ok = True
                if not alt_ok:
                    alt = None

                bonus = 0
                if bonus_col is not None and bonus_col < len(rr):
                    bonus = parse_dollar(rr[bonus_col])
                elif i < len(bonus_values):
                    bonus = bonus_values[i]

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
# BONUS CASH PARSER (Page "Bonus Cash Program")
# ═══════════════════════════════════════════════════════════════

def parse_bonus_cash_page(pdf_content: bytes) -> List[Dict]:
    """
    Parse the 'Bonus Cash Program' page (typically page 8) to extract
    bonus cash amounts per vehicle/year. The TOC entry is
    'Bonus Cash Program – 2618'.

    Returns list of dicts:
      [{'year': 2025, 'model': 'FIAT 500e', 'amount': 5000, 'tax_type': 'After Tax'}, ...]
    """
    toc = _parse_toc(pdf_content)
    bonus_page = None
    for name, page_num in toc:
        if 'Bonus Cash' in name:
            bonus_page = page_num
            break

    if not bonus_page:
        logger.info("[BonusCash] No 'Bonus Cash' section found in TOC")
        return []

    results = []
    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        if bonus_page - 1 >= len(pdf.pages):
            return []
        page = pdf.pages[bonus_page - 1]
        tables = page.extract_tables()

        for t in tables:
            if not t or len(t) < 3:
                continue
            # Look for the table with "Bonus Cash" and "Amount" headers
            has_bonus_header = False
            for row in t[:2]:
                for cell in row:
                    if cell and 'Bonus Cash' in str(cell):
                        has_bonus_header = True
                        break
            if not has_bonus_header:
                continue

            # Parse data rows (skip header rows 0 and 1)
            for ri in range(2, len(t)):
                row = t[ri]
                year_str = str(row[0]).strip() if row[0] else ''
                model_str = str(row[3]).strip() if len(row) > 3 and row[3] else ''
                amount_str = str(row[10]).strip() if len(row) > 10 and row[10] else ''
                tax_type = str(row[13]).strip() if len(row) > 13 and row[13] else ''

                if not model_str or not amount_str:
                    continue

                year = None
                if '2026' in year_str:
                    year = 2026
                elif '2025' in year_str:
                    year = 2025
                elif '2024' in year_str:
                    year = 2024

                amount = parse_dollar(amount_str)
                if amount and amount > 0:
                    results.append({
                        'year': year,
                        'model': model_str,
                        'amount': amount,
                        'tax_type': tax_type,
                    })
                    logger.info(f"[BonusCash] {model_str} ({year}): ${amount} {tax_type}")

    logger.info(f"[BonusCash] Extracted {len(results)} bonus cash entries")
    return results


def apply_bonus_cash(programs: List[Dict], bonus_entries: List[Dict]) -> List[Dict]:
    """Apply bonus cash from page 8 to matching retail programs."""
    if not bonus_entries:
        return programs

    for entry in bonus_entries:
        model_lower = entry['model'].lower().replace('fiat ', '').strip()
        for prog in programs:
            # Match by year
            if entry.get('year') and prog.get('year') != entry['year']:
                continue
            # Match by model name: compare against brand+model+trim and model+trim
            full_name = f"{prog.get('brand', '')} {prog.get('model', '')} {prog.get('trim', '')}".lower()
            model_trim = f"{prog.get('model', '')} {prog.get('trim', '')}".lower()
            if (model_lower in full_name or model_lower in model_trim
                    or full_name.startswith(model_lower) or model_trim.startswith(model_lower)):
                prog['bonus_cash'] = entry['amount']
                logger.info(f"[BonusCash] Applied ${entry['amount']} to {prog['brand']} {prog['model']} {prog.get('trim', '')} ({prog['year']})")

    return programs


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
# GENERAL RULES PARSER (km adjustments)
# ═══════════════════════════════════════════════════════════════

# Default km adjustments (fallback if extraction fails)
DEFAULT_KM_ADJUSTMENTS = {
    "18000": {"24": 1, "27": 1, "36": 2, "39": 2, "42": 2, "48": 3, "51": 3, "54": 3, "60": 4},
    "12000": {"24": 2, "27": 2, "36": 3, "39": 3, "42": 3, "48": 4, "51": 4, "54": 4, "60": 5},
}

# Term range expansion: "24 – 27" → [24, 27], "36 – 42" → [36, 39, 42], "60" → [60]
_TERM_RANGE_MAP = {
    (24, 27): ["24", "27"],
    (36, 42): ["36", "39", "42"],
    (48, 54): ["48", "51", "54"],
    (60, 60): ["60"],
}


def _expand_term_range(term_text: str) -> List[str]:
    """Convert a term range string like '24 – 27 months' into a list of term keys."""
    term_text = term_text.replace('months', '').replace('month', '').strip()
    m = re.match(r'(\d+)\s*[–\-]\s*(\d+)', term_text)
    if m:
        low, high = int(m.group(1)), int(m.group(2))
        for (rng_low, rng_high), keys in _TERM_RANGE_MAP.items():
            if rng_low == low and rng_high == high:
                return keys
        # Fallback: generate intermediate terms (multiples of 3 within range)
        return [str(t) for t in range(low, high + 1, 3)]
    m_single = re.match(r'(\d+)', term_text)
    if m_single:
        val = int(m_single.group(1))
        return [str(val)]
    return []


def parse_general_rules(pdf_content: bytes) -> Dict:
    """
    Parse the 'General Rules' section to extract the Low/Super Low Kilometre
    residual enhancements table.

    Returns:
    {
        "standard_km": 24000,
        "max_km_per_year": 36000,
        "adjustments": {
            "18000": {"24": 1, "27": 1, "36": 2, ...},
            "12000": {"24": 2, "27": 2, "36": 3, ...}
        },
        "source": "extracted"
    }
    """
    toc = _parse_toc(pdf_content)

    # Find General Rules pages from TOC
    gr_start = None
    gr_end = None
    for idx, (name, page_num) in enumerate(toc):
        if 'general rules' in name.lower():
            gr_start = page_num
            if idx + 1 < len(toc):
                gr_end = toc[idx + 1][1] - 1
            else:
                gr_end = page_num + 2
            break

    if not gr_start:
        logger.warning("[GeneralRules] Section not found in TOC, using defaults")
        return {"standard_km": 24000, "max_km_per_year": 36000,
                "adjustments": DEFAULT_KM_ADJUSTMENTS, "source": "default"}

    logger.info(f"[GeneralRules] Found in TOC: pages {gr_start}-{gr_end}")

    low_km = {}   # 18,000 km/year
    super_low = {}  # 12,000 km/year

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        total_pages = len(pdf.pages)
        start_idx = max(0, gr_start - 1)
        end_idx = min(total_pages, (gr_end or gr_start + 2))

        for page_idx in range(start_idx, end_idx):
            page = pdf.pages[page_idx]
            tables = page.extract_tables()

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Look for the km enhancement table by checking headers
                has_low_km_header = False
                header_row_idx = None
                for ri, row in enumerate(table[:4]):
                    row_text = ' '.join(str(c or '') for c in row).lower()
                    if 'low km' in row_text or 'low kilomet' in row_text or '18,000' in row_text or '18000' in row_text:
                        has_low_km_header = True
                        header_row_idx = ri
                        break

                if not has_low_km_header:
                    continue

                logger.info(f"[GeneralRules] Found km enhancement table on page {page_idx+1}, header at row {header_row_idx}")

                # Parse data rows - find values by scanning for numeric content
                # Table structure varies (merged cells), so we find data positionally:
                # Col 0 = Term text, first numeric col = Low KM, last numeric col = Super Low KM
                for ri in range(header_row_idx + 1, len(table)):
                    row = table[ri]
                    if not row:
                        continue

                    # Find term text (first non-empty cell with month/number info)
                    term_text = None
                    for ci, cell in enumerate(row):
                        cell_str = str(cell or '').strip()
                        if cell_str and re.search(r'\d', cell_str) and ('month' in cell_str.lower() or re.match(r'^\d+\s*[–\-]?\s*\d*', cell_str)):
                            term_text = cell_str
                            break

                    if not term_text:
                        # Try first column directly
                        c0 = str(row[0] or '').strip()
                        if c0 and re.search(r'\d', c0):
                            term_text = c0

                    if not term_text:
                        continue

                    # Find all numeric enhancement values in the row
                    values = []
                    for ci, cell in enumerate(row):
                        val = _parse_enhancement_value(str(cell or ''))
                        if val is not None and ci > 0:  # Skip col 0 (term)
                            values.append((ci, val))

                    if len(values) < 2:
                        continue

                    # First value = Low KM (18k), last value = Super Low KM (12k)
                    low_val = values[0][1]
                    super_val = values[-1][1]

                    term_keys = _expand_term_range(term_text)
                    if not term_keys:
                        continue

                    logger.info(f"[GeneralRules] Term={term_text} → keys={term_keys}, Low={low_val}, Super={super_val}")

                    for tk in term_keys:
                        low_km[tk] = low_val
                        super_low[tk] = super_val

    if low_km and super_low:
        result = {
            "standard_km": 24000,
            "max_km_per_year": 36000,
            "adjustments": {
                "18000": low_km,
                "12000": super_low,
            },
            "source": "extracted",
        }
        logger.info(f"[GeneralRules] Extracted km adjustments: 18k={low_km}, 12k={super_low}")
        return result

    logger.warning("[GeneralRules] Could not extract km table, using defaults")
    return {"standard_km": 24000, "max_km_per_year": 36000,
            "adjustments": DEFAULT_KM_ADJUSTMENTS, "source": "default"}


def _parse_enhancement_value(text: str) -> Optional[int]:
    """Parse enhancement value like '+1', '+2', '1', '2'."""
    if not text:
        return None
    m = re.search(r'[+]?\s*(\d+)', text)
    if m:
        return int(m.group(1))
    return None


# ═══════════════════════════════════════════════════════════════
# AUTO-DETECTION DES PAGES (TOC-first strategy)
# ═══════════════════════════════════════════════════════════════

def _parse_toc(pdf_content: bytes) -> List[Tuple[str, int]]:
    """
    Parse the Table of Contents on page 2 of the PDF.
    Returns ordered list of (section_name, page_number).

    TOC format example:
        Finance Prime Rate Landscapes ..... - 19 -
        Lease Landscapes ..................... - 27 -
        General Rules ......................... 5
    """
    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        if len(pdf.pages) < 2:
            return []
        toc_text = pdf.pages[1].extract_text() or ''

    entries = []
    for line in toc_text.split('\n'):
        # Match: "Section Name ..... - 19 -" or "Section Name ..... 19"
        m = re.match(r'^(.+?)\s*[\.…]+\s*-?\s*(\d+)\s*-?\s*$', line.strip())
        if m:
            name = m.group(1).strip()
            page = int(m.group(2))
            entries.append((name, page))

    logger.info(f"[TOC] Parsed {len(entries)} entries: {[(n, p) for n, p in entries]}")
    return entries


def auto_detect_pages(pdf_content: bytes) -> Dict:
    """
    Détecte les sections du PDF en parsant la Table des Matières (page 2).

    Chaque numéro de page dans la TOC pointe vers une PAGE TITRE.
    Les données réelles commencent à toc_page + 1 et se terminent
    à la page avant la section suivante (next_toc_page - 1).

    Returns dict with page ranges (1-indexed):
    {
        'retail_start': 20, 'retail_end': 22,
        'lease_start': 28, 'lease_end': 29,
        'non_prime_start': 24, 'non_prime_end': 26,
        'key_incentive_pages': [3, 4],
        'total_pages': 29,
        'detected_sections': [...]
    }
    """
    result = {
        'retail_start': None, 'retail_end': None,
        'lease_start': None, 'lease_end': None,
        'non_prime_start': None, 'non_prime_end': None,
        'key_incentive_pages': [3, 4],
        'total_pages': 0,
        'detected_sections': [],
    }

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        total_pages = len(pdf.pages)
        result['total_pages'] = total_pages

    toc = _parse_toc(pdf_content)
    if not toc:
        logger.warning("[AutoDetect] No TOC entries found, cannot detect pages")
        return result

    # Build an ordered list of TOC page numbers for boundary calculation

    def _find_section_range(keyword: str, exclude_keywords: List[str] = None) -> Optional[Tuple[int, int]]:
        """Find a section by keyword in TOC and compute data page range."""
        exclude_keywords = exclude_keywords or []
        for idx, (name, toc_page) in enumerate(toc):
            name_upper = name.upper()
            if keyword.upper() not in name_upper:
                continue
            if any(ek.upper() in name_upper for ek in exclude_keywords):
                continue
            # Data starts after the title page
            data_start = toc_page + 1
            # Data ends before the next TOC section's title page
            if idx + 1 < len(toc):
                data_end = toc[idx + 1][1] - 1
            else:
                data_end = total_pages
            if data_start > data_end:
                data_end = data_start
            return (data_start, data_end)
        return None

    # Finance Prime Rate Landscapes (exclude "Non-Prime" and "Loyalty")
    retail = _find_section_range('Finance Prime Rate Landscape', exclude_keywords=['Non', 'Loyalty'])
    if retail:
        result['retail_start'], result['retail_end'] = retail
        result['detected_sections'].append({
            'type': 'retail_prime', 'pages': f"{retail[0]}-{retail[1]}", 'source': 'TOC'
        })

    # Finance Non-Prime Rate Landscapes (exclude "Loyalty")
    non_prime = _find_section_range('Non- Prime Rate Landscape', exclude_keywords=['Loyalty'])
    if not non_prime:
        non_prime = _find_section_range('Non-Prime Rate Landscape', exclude_keywords=['Loyalty'])
    if non_prime:
        result['non_prime_start'], result['non_prime_end'] = non_prime
        result['detected_sections'].append({
            'type': 'non_prime', 'pages': f"{non_prime[0]}-{non_prime[1]}", 'source': 'TOC'
        })

    # Lease Landscapes (exclude "Loyalty")
    lease = _find_section_range('Lease Landscape', exclude_keywords=['Loyalty'])
    if lease:
        result['lease_start'], result['lease_end'] = lease
        result['detected_sections'].append({
            'type': 'lease', 'pages': f"{lease[0]}-{lease[1]}", 'source': 'TOC'
        })

    logger.info(
        f"[AutoDetect] TOC-based: Retail={result['retail_start']}-{result['retail_end']}, "
        f"Lease={result['lease_start']}-{result['lease_end']}, "
        f"NonPrime={result['non_prime_start']}-{result['non_prime_end']}, "
        f"KeyIncentives={result['key_incentive_pages']}"
    )
    return result



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
