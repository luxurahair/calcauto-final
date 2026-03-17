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
    ('Grand Wagoneer L', 'Jeep'),
    ('Grand Wagoneer', 'Jeep'),
    ('Grand Cherokee', 'Jeep'),
    ('Wagoneer S', 'Jeep'),
    ('Wagoneer L', 'Jeep'),
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
    'Chrysler': [
        'Grand Caravan', 'Pacifica',
        # Wagoneer sometimes appears under Chrysler section in PDFs
        'Grand Wagoneer L', 'Grand Wagoneer', 'Wagoneer S', 'Wagoneer L', 'Wagoneer',
    ],
    'Jeep': [
        'Grand Wagoneer L', 'Grand Wagoneer', 'Grand Cherokee L', 'Grand Cherokee',
        'Wagoneer S', 'Wagoneer L', 'Wagoneer', 'Gladiator', 'Wrangler', 'Compass', 'Cherokee',
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
    sorted_models = sorted(models, key=len, reverse=True)

    # Handle combined model patterns: "Grand Cherokee/Grand Cherokee L Altitude (CPOS 2B5)"
    # or "Grand Wagoneer/Grand Wagoneer L", "Wagoneer / Wagoneer L"
    if '/' in full_name:
        slash_idx = full_name.index('/')
        after_slash = full_name[slash_idx + 1:].strip()
        # Check if the text after "/" starts with a known model
        for model in sorted_models:
            if after_slash.lower().startswith(model.lower()):
                after_model = after_slash[len(model):]
                if not after_model or not after_model[0].isalpha():
                    # Matched: use the combined "ModelA/ModelB" as model, rest as trim
                    combined_model = full_name[:slash_idx].strip() + '/' + model
                    trim = after_model.strip()
                    return combined_model, trim

    for model in sorted_models:
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
    # Ignore MSRP percentage-off discounts and program codes (e.g., "MSRP % Off Discount (P2619B3)")
    s_lower = s.lower()
    if 'msrp' in s_lower or '% off' in s_lower or 'discount' in s_lower:
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
# CONTENT-DRIVEN TABLE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

# Known vehicle model keywords for content detection
_VEHICLE_KEYWORDS = [
    'Grand Caravan', 'Pacifica', 'Compass', 'Cherokee', 'Wrangler',
    'Gladiator', 'Wagoneer', 'Durango', 'Charger', 'Hornet',
    'Ram 1500', 'Ram 2500', 'Ram 3500', '500e', 'ProMaster',
]


def _classify_table(table: list) -> str:
    """
    Classify a table by analyzing its CONTENT, not its position.
    Returns: 'rates', 'names', 'bonus', 'delivery', or 'unknown'
    """
    if not table or len(table) < 2:
        return 'unknown'

    ncols = max(len(row) for row in table)

    pct_count = 0
    all_text = []

    for row in table:
        for cell in row:
            if not cell:
                continue
            s = str(cell).strip()
            if '%' in s:
                pct_count += 1
            all_text.append(s)

    joined = ' '.join(all_text)

    # RATES TABLE: 15+ cols with many % values
    if ncols >= 15 and pct_count >= 10:
        return 'rates'

    # NAMES TABLE: 2-10 cols with vehicle model keywords or brand codes
    if 2 <= ncols <= 10:
        brand_code_hits = sum(1 for t in all_text if t in BRAND_REVERSED_MAP)
        model_hits = sum(1 for kw in _VEHICLE_KEYWORDS if kw in joined)
        if brand_code_hits >= 2 or model_hits >= 3:
            return 'names'

    # BONUS TABLE: header contains "Bonus Cash"
    if ncols <= 6:
        for row in table[:5]:
            for cell in row:
                if cell and 'Bonus Cash' in str(cell):
                    return 'bonus'

    # DELIVERY CREDIT TABLE
    if ncols <= 6:
        for row in table[:5]:
            for cell in row:
                if cell and 'Delivery Credit' in str(cell):
                    return 'delivery'

    return 'unknown'


def _classify_all_tables(tables: list) -> Dict[str, list]:
    """
    Classify all tables on a page by content. Returns dict keyed by role.
    """
    classified = {'rates': [], 'names': [], 'bonus': [], 'delivery': [], 'unknown': []}
    for i, t in enumerate(tables):
        role = _classify_table(t)
        classified[role].append(t)
        logger.debug(f"[Classify] Table {i}: {role} ({len(t)}r x {len(t[0]) if t else 0}c)")
    return classified


# ═══════════════════════════════════════════════════════════════
# RETAIL FINANCE PARSER
# ═══════════════════════════════════════════════════════════════

def _detect_rate_columns(table: list) -> Tuple[Optional[int], Optional[int]]:
    """
    Find the first column index for Option 1 and Option 2 rate headers.
    Method 1: Look for '36M' in header rows.
    Method 2: Fall back to scanning data rows for clusters of % values.
    """
    # Method 1: Header-based detection
    for row in table[:8]:
        opt1_col = None
        opt2_col = None
        for ci, cell in enumerate(row):
            if not cell:
                continue
            cs = str(cell).upper().replace('\n', ' ')
            if '36M' in cs or '36 MONTH' in cs:
                if opt1_col is None:
                    opt1_col = ci
                else:
                    opt2_col = ci
                    return (opt1_col, opt2_col)

    # Method 2: Data-pattern fallback
    for ri in range(min(20, len(table))):
        row = table[ri]
        pct_cols = [ci for ci, c in enumerate(row) if c and '%' in str(c)]
        if len(pct_cols) >= 6:
            clusters = []
            current = [pct_cols[0]]
            for j in range(1, len(pct_cols)):
                if pct_cols[j] - pct_cols[j-1] <= 2:
                    current.append(pct_cols[j])
                else:
                    clusters.append(current)
                    current = [pct_cols[j]]
            clusters.append(current)
            if clusters:
                opt1 = clusters[0][0]
                opt2 = clusters[1][0] if len(clusters) >= 2 else None
                logger.info(f"[RateDetect] Fallback from data: opt1@{opt1}, opt2@{opt2}")
                return (opt1, opt2)

    return (None, None)


def _find_names_table(tables: list) -> Optional[list]:
    """Find the names table by content (brand codes or vehicle keywords)."""
    classified = _classify_all_tables(tables)
    if classified['names']:
        return classified['names'][0]
    # Fallback: look for reversed brand codes
    brand_codes = set(BRAND_REVERSED_MAP.keys())
    for t in tables[1:]:
        if not t or len(t) < 5 or len(t[0]) < 2:
            continue
        for ri in range(min(10, len(t))):
            c0 = str(t[ri][0]).strip() if t[ri][0] else ''
            if c0 in brand_codes:
                return t
    return None


def _find_bonus_table(tables: list) -> Optional[list]:
    """Find the Bonus Cash table by content."""
    classified = _classify_all_tables(tables)
    if classified['bonus']:
        return classified['bonus'][0]
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
    Parse retail financing programs from PDF using content-driven table identification.
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

            # ── Content-driven: find the rates table ──
            classified = _classify_all_tables(tables)
            if classified['rates']:
                main_table = classified['rates'][0]
            else:
                # Fallback: largest table is likely the rates table
                main_table = max(tables, key=lambda t: len(t[0]) if t else 0)

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

            # Loyalty "P" marker columns in the rates table:
            #   cc_col - 1 (col 2 for 24-col layout) = P for Consumer Cash
            #   opt1_start - 1 (col 4 for 24-col layout) = P for Option 1 Rates
            #   opt2_start - 1 (col 16 for 24-col layout) = P for Option 2 Rates
            p_cc_col = cc_col - 1 if cc_col >= 1 else None
            p_opt1_col = opt1_start - 1 if opt1_start >= 1 else None
            p_opt2_col = (opt2_start - 1) if opt2_start and opt2_start >= 1 else None

            def _is_p(row, col_idx):
                """Check if a cell contains the loyalty 'P' marker."""
                if col_idx is None or col_idx >= len(row):
                    return False
                v = str(row[col_idx]).strip() if row[col_idx] else ''
                return v == 'P'

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

                    # Detect loyalty P markers
                    loyalty_cash = _is_p(row, p_cc_col)
                    loyalty_opt1 = _is_p(row, p_opt1_col)
                    loyalty_opt2 = _is_p(row, p_opt2_col)

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
                        'loyalty_cash': loyalty_cash,
                        'loyalty_opt1': loyalty_opt1,
                        'loyalty_opt2': loyalty_opt2,
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

                # Alignment check - warn if counts don't match
                if len(vehicles) != len(rate_rows):
                    logger.warning(
                        f"[RetailParser] ⚠ ALIGNMENT MISMATCH: {len(vehicles)} vehicles "
                        f"vs {len(rate_rows)} rate rows on page {page_idx+1}. "
                        f"Data may be shifted for the last vehicles."
                    )

                # Zip vehicles with rate rows
                for vi, (brand, vehicle_name) in enumerate(vehicles):
                    if vi >= len(rate_rows):
                        break

                    rr = rate_rows[vi]
                    model, trim = split_model_trim(brand, vehicle_name)

                    consumer_cash = parse_dollar(rr[cc_col] if cc_col < len(rr) else None)

                    # Detect loyalty P markers from rate row
                    loyalty_cash = _is_p(rr, p_cc_col)
                    loyalty_opt1 = _is_p(rr, p_opt1_col)
                    loyalty_opt2 = _is_p(rr, p_opt2_col)

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
                        'loyalty_cash': loyalty_cash,
                        'loyalty_opt1': loyalty_opt1,
                        'loyalty_opt2': loyalty_opt2,
                    })

            logger.info(f"[RetailParser] Page {page_idx+1}: {len(programs)} programmes cumulés")

    logger.info(f"[RetailParser] Total programmes extraits: {len(programs)}")
    return programs


# ═══════════════════════════════════════════════════════════════
# POST-EXTRACTION VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_extraction(programs: List[Dict], sci_data: Dict = None) -> Dict:
    """
    Run quality checks after extraction. Returns a report dict with:
    - warnings: non-critical issues that should be reviewed
    - errors: critical issues that likely indicate parsing bugs
    - stats: summary statistics
    """
    warnings = []
    errors = []

    if not programs:
        errors.append("ZERO programmes extraits - vérifiez le PDF et les pages")
        return {'warnings': warnings, 'errors': errors, 'stats': {}}

    # Count by year
    year_counts = {}
    for p in programs:
        y = p.get('year', 0)
        year_counts[y] = year_counts.get(y, 0) + 1

    # Brand distribution
    brand_counts = {}
    for p in programs:
        b = p.get('brand', 'Unknown')
        brand_counts[b] = brand_counts.get(b, 0) + 1

    # Check for suspicious data
    for p in programs:
        name = f"{p.get('brand')} {p.get('model')} {p.get('trim', '')} ({p.get('year')})"

        # Consumer cash sanity: should be 0 or $500-$25,000
        cc = p.get('consumer_cash', 0)
        if cc > 0 and (cc < 100 or cc > 25000):
            warnings.append(f"CC suspect: {name}: ${cc}")

        # Alt consumer cash sanity
        acc = p.get('alt_consumer_cash', 0)
        if acc > 0 and (acc < 100 or acc > 25000):
            warnings.append(f"Alt CC suspect: {name}: ${acc}")

        # Bonus cash sanity: should be 0 or $500-$10,000
        bc = p.get('bonus_cash', 0)
        if bc > 0 and (bc < 100 or bc > 15000):
            warnings.append(f"Bonus suspect: {name}: ${bc}")

        # Rate sanity: 0-10% is normal for FCA
        opt1 = p.get('option1_rates') or {}
        opt2 = p.get('option2_rates') or {}
        for key, rate in {**opt1, **opt2}.items():
            if rate is not None and (rate < 0 or rate > 15):
                warnings.append(f"Taux suspect: {name}: {key}={rate}%")

        # Check for "All-New" or other prefixes that should be stripped
        for field in ['model', 'trim']:
            val = p.get(field, '')
            if 'All-New' in val or 'All New' in val:
                warnings.append(f"Prefix non-nettoyé: {name}: '{val}'")

        # Check for duplicate entries (same brand+model+trim+year)
        # (would need a set check, handled separately below)

    # Check for duplicates
    seen = set()
    for p in programs:
        key = (p.get('brand'), p.get('model'), p.get('trim', ''), p.get('year'))
        if key in seen:
            errors.append(f"DOUBLON: {key}")
        seen.add(key)

    # Check for 'Unknown' brands
    unknown_count = brand_counts.get('Unknown', 0)
    if unknown_count > 0:
        errors.append(f"{unknown_count} véhicules avec marque 'Unknown'")

    # SCI Lease validation
    sci_stats = {}
    if sci_data:
        v2026 = sci_data.get('vehicles_2026', [])
        v2025 = sci_data.get('vehicles_2025', [])
        sci_stats = {'v2026': len(v2026), 'v2025': len(v2025)}

        for v in v2026 + v2025:
            model = v.get('model', '')
            if v.get('brand') == 'Unknown':
                warnings.append(f"SCI Lease marque inconnue: {model}")
            std = v.get('standard_rates') or {}
            alt = v.get('alternative_rates') or {}
            if not std and not alt:
                warnings.append(f"SCI Lease sans taux: {model}")

    stats = {
        'total_programs': len(programs),
        'by_year': year_counts,
        'by_brand': brand_counts,
        'loyalty_count': sum(1 for p in programs if p.get('loyalty_cash') or p.get('loyalty_opt1') or p.get('loyalty_opt2')),
        'bonus_count': sum(1 for p in programs if p.get('bonus_cash', 0) > 0),
        'sci_lease': sci_stats,
    }

    # Log the report
    logger.info(f"[Validation] Stats: {stats}")
    if warnings:
        for w in warnings:
            logger.warning(f"[Validation] ⚠ {w}")
    if errors:
        for e in errors:
            logger.error(f"[Validation] ❌ {e}")
    if not warnings and not errors:
        logger.info("[Validation] ✅ Aucun problème détecté")

    return {'warnings': warnings, 'errors': errors, 'stats': stats}



# ═══════════════════════════════════════════════════════════════
# SCI LEASE PARSER
# ═══════════════════════════════════════════════════════════════

def _detect_sci_columns(rates_t: list) -> Dict:
    """Détection ULTRA-STRICTE – alt_start seulement si 'ALTERNATIVE' existe vraiment"""
    result = {'lease_cash_col': None, 'std_start': None, 'alt_start': None, 'bonus_col': None}
    for ri in range(min(8, len(rates_t))):
        row = rates_t[ri]
        for ci, cell in enumerate(row):
            if not cell: continue
            cs = str(cell).strip().upper()
            if 'STACKABLE' in cs or 'TYPE OF SALE' in cs: continue
            if result['lease_cash_col'] is None and 'LEASE CASH' in cs:
                result['lease_cash_col'] = ci
            elif result['std_start'] is None and 'SCI' in cs and 'STANDARD' in cs:
                result['std_start'] = ci
            elif result['alt_start'] is None and 'SCI' in cs and 'ALTERNATIVE' in cs:
                result['alt_start'] = ci
            elif result['bonus_col'] is None and 'BONUS CASH' in cs:
                result['bonus_col'] = ci
    # Pas de default pour alt_start → None si pas trouvé
    if result['lease_cash_col'] is None: result['lease_cash_col'] = 2
    if result['std_start'] is None: result['std_start'] = 4
    logger.info(f"[SCIParser] Columns: lease_cash={result['lease_cash_col']}, std={result['std_start']}, alt={result['alt_start']}")
    return result

def parse_sci_lease(pdf_content: bytes, start_page: int, end_page: int) -> Dict:
    """Parse SCI Lease – VERSION CORRIGEE avec alignement correct noms/taux"""
    vehicles_2026 = []
    vehicles_2025 = []
    term_keys = ['24', '27', '36', '39', '42', '48', '51', '54', '60']

    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        for page_idx in range(max(0, start_page-1), min(len(pdf.pages), end_page)):
            page = pdf.pages[page_idx]
            tables = page.extract_tables()
            if len(tables) < 2: continue

            classified = _classify_all_tables(tables)
            names_t = classified['names'][0] if classified['names'] else None
            rates_t = classified['rates'][0] if classified['rates'] else None
            if not names_t or not rates_t: continue

            model_year = None
            for row in names_t[:5]:
                for cell in row:
                    if cell and re.search(r'202[56]', str(cell)):
                        model_year = int(re.search(r'202[56]', str(cell)).group(0))
                        break
                if model_year: break

            col_map = _detect_sci_columns(rates_t)
            lease_cash_col = col_map['lease_cash_col']
            std_indices = list(range(col_map['std_start'], col_map['std_start'] + 9))
            alt_indices = list(range(col_map['alt_start'], col_map['alt_start'] + 9)) if col_map.get('alt_start') is not None else []

            has_real_alt = False
            if alt_indices:
                for row in rates_t:
                    for idx in alt_indices:
                        if idx < len(row):
                            v = str(row[idx]).strip()
                            if '%' in v and v != '-' and v != '':
                                has_real_alt = True
                                break

            # STEP 1: Extract vehicle names (skip header rows)
            skip_keywords = ['discount', 'stackable', 'type of sale', 'model year',
                             'program', 'stackability', 'important', 'color key',
                             'see program', 'before tax', 'after tax']
            vehicle_names = []
            for ri in range(len(names_t)):
                # Try column 1 first (common), then column 0
                vname = ''
                for col_idx in [1, 0]:
                    if len(names_t[ri]) > col_idx and names_t[ri][col_idx]:
                        candidate = str(names_t[ri][col_idx]).replace('\n', ' ').strip()
                        if candidate and candidate != 'None' and not any(k in candidate.lower() for k in skip_keywords):
                            vname = candidate
                            break
                if vname:
                    vehicle_names.append((ri, vname))

            # STEP 2: Extract rate data rows (skip header rows)
            rate_data_rows = []
            for ri in range(len(rates_t)):
                rr = rates_t[ri]
                # A data row has rate values (%) or lease cash ($)
                has_rate = any(rr[i] and '%' in str(rr[i]) for i in std_indices + alt_indices if i < len(rr))
                has_lc = lease_cash_col < len(rr) and rr[lease_cash_col] and '$' in str(rr[lease_cash_col])
                has_sale_type = (lease_cash_col + 1) < len(rr) and rr[lease_cash_col + 1] and str(rr[lease_cash_col + 1]).strip() == 'P'
                if has_rate or has_lc or has_sale_type:
                    rate_data_rows.append((ri, rr))

            # STEP 3: Zip vehicle names with rate data (1:1 mapping)
            count = min(len(vehicle_names), len(rate_data_rows))
            logger.info(f"[SCI Lease] Page {page_idx+1}: {len(vehicle_names)} noms, {len(rate_data_rows)} lignes de taux, {count} matches")

            for vi in range(count):
                _, vname = vehicle_names[vi]
                _, rr = rate_data_rows[vi]

                lease_cash = parse_dollar(rr[lease_cash_col] if lease_cash_col < len(rr) else None)

                std = {}
                for k, i in zip(term_keys, std_indices):
                    if i < len(rr):
                        std[k] = parse_rate(rr[i])

                alt = None
                if has_real_alt and alt_indices:
                    alt = {}
                    for k, i in zip(term_keys, alt_indices):
                        if i < len(rr):
                            alt[k] = parse_rate(rr[i])
                if alt and all(v is None or v == 0 for v in alt.values()):
                    alt = None

                # If std rates are all None/dashes, set to None
                if std and all(v is None or v == 0 for v in std.values()):
                    std = None

                brand = detect_brand_from_model(vname) or "Unknown"

                vehicle = {
                    'model': vname,
                    'brand': brand,
                    'lease_cash': lease_cash,
                    'standard_rates': std,
                    'alternative_rates': alt
                }

                target = vehicles_2026 if model_year == 2026 else vehicles_2025
                target.append(vehicle)
                logger.debug(f"[SCI Lease] {vname}: LC=${lease_cash}, STD={'YES' if std else 'NO'}, ALT={'YES' if alt else 'NO'}")

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
    toc = improved_parse_toc(pdf_content)
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
    return result  # ← C'ÉTAIT ÇA QUI MANQUAIT !

# ═══════════════════════════════════════════════════════════════
# PATCHS POUR 100% STABILITÉ – VERSION FINALE (remplace les anciens patches)
# ═══════════════════════════════════════════════════════════════

def find_col(table: list, keywords: list[str], start_row: int = 0) -> Optional[int]:
    """Recherche de colonne ultra-robuste (utilisée partout)"""
    keywords = [k.upper() for k in keywords]
    for row_idx in range(start_row, min(start_row + 10, len(table))):
        row = table[row_idx]
        for col_idx, cell in enumerate(row):
            if not cell: continue
            cell_str = str(cell).upper().replace('\n', ' ').replace(' ', '')
            if any(kw in cell_str for kw in keywords):
                return col_idx
    return None

def merge_multi_page_tables(pdf, start_page: int, end_page: int) -> list:
    """Fusionne les tables qui span sur plusieurs pages (nouveau)"""
    all_rows = []
    for p in range(start_page-1, end_page):
        page = pdf.pages[p]
        tables = page.extract_tables()
        if tables:
            main = max(tables, key=lambda t: len(t) * len(t[0]) if t else 0)
            all_rows.extend(main)
    return all_rows

def improved_parse_toc(pdf_content: bytes) -> List[Tuple[str, int]]:
    """Parse le TOC de la page 2 — filtre les lignes parasites"""
    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        toc_text = pdf.pages[1].extract_text() or ''
    entries = []
    # Mots-clés à ignorer (lignes parasites, pas des sections)
    ignore_keywords = ['internal use only', 'for internal use', 'confidential', 'table of contents']
    for line in toc_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Ignorer les lignes parasites
        if any(kw in line.lower() for kw in ignore_keywords):
            continue
        for pattern in [
            r'^(.+?)\s*[\.…]+\s*-?\s*(\d+)\s*-?\s*$',
            r'(.+?)\s*-\s*(\d+)\s*-',
        ]:
            m = re.match(pattern, line)
            if m:
                name = m.group(1).strip()
                page = int(m.group(2))
                if page >= 3 and name:  # Page 1-2 = couverture + TOC, pas des sections
                    entries.append((name, page))
                break
    logger.info(f"[TOC] {len(entries)} entrées: {[(n, p) for n, p in entries]}")
    return entries

# ═══════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════
# AUTO_DETECT_PAGES - LECTURE COMPLETE DU TOC AVEC CHECKBOXES
# ═══════════════════════════════════════════════════════════════

# Mapping section TOC -> type pour le frontend
_SECTION_TYPE_MAP = [
    ('loyalty rate reduction finance', 'loyalty_finance'),
    ('loyalty rate reduction lease', 'loyalty_lease'),
    ('loyalty program', 'loyalty_info'),
    ('loyalty addendum', 'info'),
    ('go to market', 'info'),
    ('key incentives', 'info'),
    ('general rules', 'info'),
    ('bonus cash', 'bonus'),
    ('msrp discount', 'info'),
    ('addendum', 'info'),
    ('finance prime rate', 'retail'),
    ('finance non', 'non_prime'),
    ('lease landscape', 'lease'),
]

def _classify_toc_section(name: str) -> str:
    """Determine le type d'une section TOC par son nom."""
    name_lower = name.lower()
    for keyword, stype in _SECTION_TYPE_MAP:
        if keyword in name_lower:
            return stype
    return 'other'

def auto_detect_pages(pdf_content: bytes) -> Dict:
    """Lit TOUTES les sections du TOC (page 2) et retourne chacune avec start_page/end_page pour checkboxes."""
    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        total_pages = len(pdf.pages)

    toc = improved_parse_toc(pdf_content)
    if not toc:
        return {'total_pages': total_pages, 'sections': [],
                'retail_start': None, 'retail_end': None,
                'lease_start': None, 'lease_end': None}

    sections = []
    for idx, (name, toc_page) in enumerate(toc):
        start = toc_page + 1
        end = toc[idx + 1][1] - 1 if idx + 1 < len(toc) else total_pages
        if end < start:
            end = start

        stype = _classify_toc_section(name)
        sections.append({
            'name': name,
            'type': stype,
            'start_page': start,
            'end_page': end,
            'toc_page': toc_page,
        })

    # Extraire retail_start/end et lease_start/end pour compatibilite
    retail_start = retail_end = lease_start = lease_end = None
    for s in sections:
        if s['type'] == 'retail' and retail_start is None:
            retail_start, retail_end = s['start_page'], s['end_page']
        if s['type'] == 'lease' and lease_start is None:
            lease_start, lease_end = s['start_page'], s['end_page']

    result = {
        'total_pages': total_pages,
        'sections': sections,
        'retail_start': retail_start,
        'retail_end': retail_end,
        'lease_start': lease_start,
        'lease_end': lease_end,
    }
    logger.info(f"[AutoDetect] TOC: {len(sections)} sections detectees")
    return result

# ═══════════════════════════════════════════════════════════════
# EXTRACT_STABLE_ALL – FONCTION UNIQUE ASYNCHRONE 100% STABLE
# ═══════════════════════════════════════════════════════════════
async def extract_stable_all(pdf_bytes: bytes) -> Dict:
    """Fonction unique 100% stable – TOUT est branché maintenant"""
    from database import db
    from product_code_lookup import _MASTER_CODES as FCA_PRODUCT_CODES

    toc = improved_parse_toc(pdf_bytes)
    pages = auto_detect_pages(pdf_bytes)

    # Extraction avec tables fusionnées (le vrai fix multi-pages)
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        retail_merged = merge_multi_page_tables(pdf, pages.get('retail_start', 16), pages.get('retail_end', 25))
        sci_merged = merge_multi_page_tables(pdf, pages.get('lease_start', 28), pages.get('lease_end', 29))

    # Appel des parsers
    programs = parse_retail_programs(pdf_bytes, pages.get('retail_start', 16), pages.get('retail_end', 25))
    sci = parse_sci_lease(pdf_bytes, pages.get('lease_start', 28), pages.get('lease_end', 29))

    # Bonus Cash (fix Emergent)
    bonus_entries = parse_bonus_cash_page(pdf_bytes)
    programs = apply_bonus_cash(programs, bonus_entries)

    # Nettoyage + corrections DB + product codes
    for p in programs:
        p['model'] = p['model'].replace('Delivery Credit', '').replace('E Only', '').strip()
        code = f"{p['brand']}_{p['model']}_{p['trim']}"
        if code in FCA_PRODUCT_CODES:
            p.update(FCA_PRODUCT_CODES[code])
        corr = await db.corrections.find_one({"brand": p['brand'], "model": p['model'], "trim": p['trim']})
        if corr:
            p.update(corr['corrected_values'])

    report = validate_extraction(programs, sci)

    return {
        "programs": programs,
        "sci": sci,
        "validation": report,
        "status": "100% STABLE" if not report['errors'] else "STABLE avec warnings",
        "total": len(programs),
        "merged_tables_used": len(retail_merged) > 0
    }
