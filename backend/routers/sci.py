from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from database import db, ROOT_DIR, logger
import json
import io

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

router = APIRouter()

# ============ SCI LEASE ENDPOINTS ============

@router.get("/sci/residuals")
async def get_sci_residuals():
    """Retourne les valeurs résiduelles SCI pour tous les véhicules"""
    residuals_path = ROOT_DIR / "data" / "sci_residuals_feb2026.json"
    if not residuals_path.exists():
        raise HTTPException(status_code=404, detail="Residual data not found")
    with open(residuals_path, 'r') as f:
        data = json.load(f)
    return data

@router.get("/sci/lease-rates")
async def get_sci_lease_rates():
    """Retourne les taux de location SCI et lease cash"""
    rates_path = ROOT_DIR / "data" / "sci_lease_rates_feb2026.json"
    if not rates_path.exists():
        raise HTTPException(status_code=404, detail="Lease rates data not found")
    with open(rates_path, 'r') as f:
        data = json.load(f)
    return data

@router.get("/sci/vehicle-hierarchy")
async def get_sci_vehicle_hierarchy():
    """Retourne la hiérarchie des véhicules SCI: marque -> modèle -> trim -> body_style"""
    residuals_path = ROOT_DIR / "data" / "sci_residuals_feb2026.json"
    if not residuals_path.exists():
        raise HTTPException(status_code=404, detail="Residual data not found")
    with open(residuals_path, 'r') as f:
        data = json.load(f)
    
    hierarchy = {}
    for v in data.get("vehicles", []):
        brand = v["brand"]
        model = v["model_name"]
        trim = v.get("trim", "")
        body = v.get("body_style", "")
        year = v.get("model_year", 2026)
        
        if brand not in hierarchy:
            hierarchy[brand] = {}
        if model not in hierarchy[brand]:
            hierarchy[brand][model] = {"years": set(), "trims": {}}
        hierarchy[brand][model]["years"].add(year)
        if trim not in hierarchy[brand][model]["trims"]:
            hierarchy[brand][model]["trims"][trim] = []
        if body and body not in hierarchy[brand][model]["trims"][trim]:
            hierarchy[brand][model]["trims"][trim].append(body)
    
    # Convert sets to sorted lists
    result = {}
    for brand, models in hierarchy.items():
        result[brand] = {}
        for model, info in models.items():
            result[brand][model] = {
                "years": sorted(list(info["years"]), reverse=True),
                "trims": info["trims"]
            }
    
    return result

@router.post("/sci/calculate-lease")
async def calculate_lease(payload: dict):
    """
    Calcule le paiement de location SCI.
    
    Formule location:
    - depreciation = (selling_price - residual_value) / term_months
    - finance_charge = (selling_price + residual_value) * (annual_rate / 2400)
    - monthly_payment = depreciation + finance_charge
    - Taxes QC (14.975%) appliquées sur le paiement mensuel
    """
    try:
        msrp = float(payload.get("msrp", 0))
        selling_price = float(payload.get("selling_price", 0))
        term = int(payload.get("term", 36))
        annual_rate = float(payload.get("annual_rate", 0))
        residual_pct = float(payload.get("residual_pct", 0))
        km_per_year = int(payload.get("km_per_year", 24000))
        lease_cash = float(payload.get("lease_cash", 0))
        bonus_cash = float(payload.get("bonus_cash", 0))
        cash_down = float(payload.get("cash_down", 0))
        trade_value = float(payload.get("trade_value", 0))
        trade_owed = float(payload.get("trade_owed", 0))
        frais_dossier = float(payload.get("frais_dossier", 259.95))
        taxe_pneus = float(payload.get("taxe_pneus", 15))
        frais_rdprm = float(payload.get("frais_rdprm", 100))
        
        if msrp <= 0 or selling_price <= 0 or term <= 0:
            raise HTTPException(status_code=400, detail="Invalid input values")
        
        # Load km adjustments
        residuals_path = ROOT_DIR / "data" / "sci_residuals_feb2026.json"
        km_adj = 0
        if residuals_path.exists():
            with open(residuals_path, 'r') as f:
                res_data = json.load(f)
            adjustments = res_data.get("km_adjustments", {}).get("adjustments", {})
            km_key = str(km_per_year)
            term_key = str(term)
            if km_key in adjustments and term_key in adjustments[km_key]:
                km_adj = adjustments[km_key][term_key]
        
        # Adjusted residual
        adjusted_residual_pct = residual_pct + km_adj
        residual_value = msrp * (adjusted_residual_pct / 100)
        
        # Net cap cost: selling_price - lease_cash - trade_net + fees
        trade_net = trade_value - trade_owed
        frais_taxables = frais_dossier + taxe_pneus + frais_rdprm
        
        # Cap cost = selling price + fees - lease cash - trade value
        cap_cost = selling_price + frais_taxables - lease_cash - trade_value
        
        # Taxes on the capitalized cost (before tax items)
        taux_taxe = 0.14975
        taxes_on_cap = (selling_price + frais_taxables - lease_cash - trade_value) * taux_taxe
        
        # Net cap cost after cash down and bonus cash
        net_cap_cost = cap_cost + taxes_on_cap + trade_owed - cash_down - bonus_cash
        
        # Lease payment calculation
        # Depreciation = (Net Cap Cost - Residual Value) / term
        depreciation = (net_cap_cost - residual_value) / term
        
        # Finance charge = (Net Cap Cost + Residual Value) * money factor
        # Money factor = annual_rate / 2400
        money_factor = annual_rate / 2400
        finance_charge = (net_cap_cost + residual_value) * money_factor
        
        # Monthly payment (taxes already included in cap cost for QC)
        monthly_before_tax = depreciation + finance_charge
        
        # In Quebec, taxes are on the monthly payment for leases
        # But since we already taxed the cap cost, we use the simpler model
        monthly_payment = monthly_before_tax
        
        biweekly_payment = monthly_payment * 12 / 26
        weekly_payment = monthly_payment * 12 / 52
        total_cost = monthly_payment * term + residual_value
        
        return {
            "success": True,
            "msrp": msrp,
            "selling_price": selling_price,
            "lease_cash": lease_cash,
            "bonus_cash": bonus_cash,
            "residual_pct": adjusted_residual_pct,
            "residual_value": round(residual_value, 2),
            "km_adjustment": km_adj,
            "annual_rate": annual_rate,
            "term": term,
            "net_cap_cost": round(net_cap_cost, 2),
            "depreciation": round(depreciation, 2),
            "finance_charge": round(finance_charge, 2),
            "monthly_payment": round(monthly_payment, 2),
            "biweekly_payment": round(biweekly_payment, 2),
            "weekly_payment": round(weekly_payment, 2),
            "total_lease_cost": round(total_cost, 2),
            "cash_down": cash_down,
            "trade_value": trade_value,
            "trade_owed": trade_owed,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lease calculation error: {str(e)}")



# ============ LEASE SCI EXCEL EXPORT/IMPORT ============

@router.get("/sci/export-excel")
async def export_sci_lease_excel():
    """Exporte les taux de location SCI en Excel"""
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="openpyxl non disponible")

    rates_path = ROOT_DIR / "data" / "sci_lease_rates_feb2026.json"
    if not rates_path.exists():
        raise HTTPException(status_code=404, detail="Fichier de taux SCI introuvable")

    with open(rates_path, 'r') as f:
        data = json.load(f)

    terms = data.get("terms", [24, 27, 36, 39, 42, 48, 51, 54, 60])
    wb = openpyxl.Workbook()

    hfont = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center")
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    std_fill = PatternFill(start_color="FFF0F0", end_color="FFF0F0", fill_type="solid")
    alt_fill = PatternFill(start_color="F0F4FF", end_color="F0F4FF", fill_type="solid")
    cash_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")

    for year_key, sheet_title in [("vehicles_2026", "Lease 2026"), ("vehicles_2025", "Lease 2025")]:
        vehicles = data.get(year_key, [])
        if not vehicles:
            continue

        ws = wb.create_sheet(title=sheet_title) if wb.sheetnames != ["Sheet"] else wb.active
        if ws.title == "Sheet":
            ws.title = sheet_title

        headers = ["Marque", "Modele", "Lease Cash ($)"]
        for t in terms:
            headers.append(f"Std {t}M")
        headers.append("Alt Lease Cash ($)")
        for t in terms:
            headers.append(f"Alt {t}M")

        for ci, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=ci, value=h)
            c.font = hfont
            c.fill = hfill
            c.alignment = center
            c.border = border

        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 55

        # Figer colonnes A-B et ligne 1
        ws.freeze_panes = 'C2'

        for ri, v in enumerate(vehicles, 2):
            std = v.get("standard_rates") or {}
            alt = v.get("alternative_rates") or {}

            row = [v.get("brand", ""), v.get("model", ""), v.get("lease_cash", 0) or 0]
            for t in terms:
                row.append(std.get(str(t)))
            row.append(v.get("alternative_lease_cash", 0) or 0)
            for t in terms:
                row.append(alt.get(str(t)))

            for ci, val in enumerate(row, 1):
                c = ws.cell(row=ri, column=ci, value=val)
                c.border = border
                if ci >= 3:
                    c.alignment = center
                if ci == 3:
                    c.fill = cash_fill
                elif 4 <= ci <= 3 + len(terms):
                    c.fill = std_fill
                elif ci == 4 + len(terms):
                    c.fill = cash_fill
                elif ci > 4 + len(terms):
                    c.fill = alt_fill

    # Instructions
    ws2 = wb.create_sheet("Instructions")
    for i, t in enumerate([
        "INSTRUCTIONS - TAUX DE LOCATION SCI",
        "",
        "1. Modifiez les taux dans les onglets Lease 2026 et Lease 2025",
        "2. Lease Cash = rabais avant taxes pour location standard",
        "3. Std = taux de location standard SCI",
        "4. Alt Lease Cash = rabais avant taxes pour location alternative",
        "5. Alt = taux de location alternative SCI",
        "6. Vide = pas de taux disponible pour ce terme",
        "7. Sauvegardez et reimportez dans l'application",
    ], 1):
        c = ws2.cell(row=i, column=1, value=t)
        if i == 1: c.font = Font(bold=True, size=14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=sci_lease_rates.xlsx"}
    )


@router.post("/sci/import-excel")
async def import_sci_lease_excel(file: UploadFile = File(...), password: str = Form("")):
    """Importe un Excel corrige pour les taux SCI. Sauvegarde comme source de verite."""
    from database import ADMIN_PASSWORD

    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe admin incorrect")

    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="openpyxl non disponible")

    rates_path = ROOT_DIR / "data" / "sci_lease_rates_feb2026.json"
    with open(rates_path, 'r') as f:
        data = json.load(f)

    terms = data.get("terms", [24, 27, 36, 39, 42, 48, 51, 54, 60])
    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content))

    updated_total = 0

    for year_key, possible_titles in [("vehicles_2026", ["Lease 2026"]), ("vehicles_2025", ["Lease 2025"])]:
        ws = None
        for title in possible_titles:
            if title in wb.sheetnames:
                ws = wb[title]
                break
        if not ws:
            continue

        vehicles = data.get(year_key, [])
        for ri, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
            if ri >= len(vehicles):
                break
            if not row or not row[0]:
                continue

            v = vehicles[ri]
            v["brand"] = str(row[0]).strip() if row[0] else v.get("brand", "")
            v["model"] = str(row[1]).strip() if row[1] else v.get("model", "")
            v["lease_cash"] = float(row[2]) if row[2] is not None else 0

            # Standard rates
            std = {}
            has_std = False
            for i, t in enumerate(terms):
                val = row[3 + i]
                if val is not None:
                    std[str(t)] = float(val)
                    has_std = True
            v["standard_rates"] = std if has_std else None

            # Alternative lease cash
            alt_cash_idx = 3 + len(terms)
            v["alternative_lease_cash"] = float(row[alt_cash_idx]) if row[alt_cash_idx] is not None else 0

            # Alternative rates
            alt = {}
            has_alt = False
            for i, t in enumerate(terms):
                val = row[alt_cash_idx + 1 + i]
                if val is not None:
                    alt[str(t)] = float(val)
                    has_alt = True
            v["alternative_rates"] = alt if has_alt else None

            updated_total += 1

        data[year_key] = vehicles

    with open(rates_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Force logout all users
    r = await db.tokens.delete_many({})
    logger.info(f"[SCI IMPORT] {updated_total} vehicules mis a jour, {r.deleted_count} tokens invalides")

    return {
        "success": True,
        "message": f"Import SCI termine: {updated_total} vehicules mis a jour. Tous les utilisateurs deconnectes.",
        "updated": updated_total,
    }

