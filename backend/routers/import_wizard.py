from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Header
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import re
import io
import asyncio
import pypdf
import pdfplumber
from database import db, ADMIN_PASSWORD, OPENAI_API_KEY, SMTP_EMAIL, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT, ROOT_DIR, logger
from models import (
    PDFExtractRequest, ProgramPreview, ExtractedDataResponse,
    SaveProgramsRequest, FinancingRates, VehicleProgram
)
from dependencies import get_current_user
from services.email_service import send_email

try:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

import re as re_module

def normalize_correction_str(s: str) -> str:
    """Normalise une chaine pour matching flexible des corrections."""
    if not s:
        return ""
    s = s.strip().lower()
    s = re_module.sub(r'\(cpos[^)]*\)', '', s)
    s = re_module.sub(r'\([A-Z]{2,}[0-9]+[^)]*\)', '', s, flags=re_module.IGNORECASE)
    s = re_module.sub(r'\(etm\)', '', s, flags=re_module.IGNORECASE)
    s = re_module.sub(r'\s+', ' ', s).strip()
    s = s.rstrip(' ,')
    return s

def normalize_correction_model(model: str) -> str:
    """Normalise le nom du modele pour matching flexible."""
    if not model:
        return ""
    m = model.strip().lower()
    m = m.replace("grand cherokee/grand cherokee l", "grand cherokee/l")
    m = m.replace("grand wagoneer / grand wagoneer l", "grand wagoneer/l")
    m = m.replace("grand wagoneer/grand wagoneer l", "grand wagoneer/l")
    m = m.replace("wagoneer / wagoneer l", "wagoneer/l")
    m = m.replace("wagoneer/wagoneer l", "wagoneer/l")
    m = re_module.sub(r'\s+', ' ', m).strip()
    return m

async def find_best_correction(brand: str, model: str, trim: str, year: int) -> dict:
    """Cherche la meilleure correction memorisee avec matching flexible."""
    # Strategie 1: Match exact
    correction = await db.program_corrections.find_one(
        {"brand": brand, "model": model, "trim": trim, "year": year},
        {"_id": 0}
    )
    if correction:
        return correction

    # Strategie 2: Match normalise
    norm_model = normalize_correction_model(model)
    norm_trim = normalize_correction_str(trim)

    all_corrections = await db.program_corrections.find(
        {"year": year},
        {"_id": 0}
    ).to_list(500)

    for c in all_corrections:
        if c.get("brand", "").lower() != brand.lower():
            continue
        c_model = normalize_correction_model(c.get("model", ""))
        c_trim = normalize_correction_str(c.get("trim", ""))
        if c_model == norm_model and c_trim == norm_trim:
            return c
        # Trim partiel
        if c_model == norm_model and norm_trim and c_trim and (c_trim in norm_trim or norm_trim in c_trim):
            return c

    return None

router = APIRouter()

# ============ Excel Generation Function ============

def generate_excel_from_programs(programs: List[Dict[str, Any]], program_month: int, program_year: int) -> bytes:
    """Génère un fichier Excel selon le format du PDF Stellantis"""
    if not EXCEL_AVAILABLE:
        raise HTTPException(status_code=500, detail="openpyxl non disponible")
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Programmes"
    
    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
    option1_fill = PatternFill(start_color="C62828", end_color="C62828", fill_type="solid")  # Rouge pour Option 1
    option2_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")  # Bleu pour Option 2
    bonus_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")  # Vert pour Bonus
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Month names
    month_names = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                   "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    
    # Title Row 1
    ws.merge_cells('A1:S1')
    ws['A1'] = f"PROGRAMMES DE FINANCEMENT RETAIL - {month_names[program_month].upper()} {program_year}"
    ws['A1'].font = Font(bold=True, size=16, color="FFFFFF")
    ws['A1'].fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
    ws['A1'].alignment = Alignment(horizontal="center")
    
    # Sub-header Row 2 - Group headers
    ws.merge_cells('A2:D2')
    ws['A2'] = "VÉHICULE"
    ws['A2'].font = header_font
    ws['A2'].fill = header_fill
    ws['A2'].alignment = header_alignment
    
    # Option 1 header with rabais
    ws.merge_cells('E2:K2')
    ws['E2'] = "OPTION 1 - Consumer Cash + Taux Standard"
    ws['E2'].font = header_font
    ws['E2'].fill = option1_fill
    ws['E2'].alignment = header_alignment
    
    # Option 2 header with rabais
    ws.merge_cells('L2:R2')
    ws['L2'] = "OPTION 2 - Alternative Consumer Cash + Taux Réduit"
    ws['L2'].font = header_font
    ws['L2'].fill = option2_fill
    ws['L2'].alignment = header_alignment
    
    # Bonus header
    ws['S2'] = "BONUS"
    ws['S2'].font = header_font
    ws['S2'].fill = bonus_fill
    ws['S2'].alignment = header_alignment
    
    # Detail Headers Row 3
    headers = [
        "Marque", "Modèle", "Version", "Année",  # Véhicule (A-D)
        "Rabais ($)", "36m", "48m", "60m", "72m", "84m", "96m",  # Option 1: Rabais + Taux (E-K)
        "Rabais ($)", "36m", "48m", "60m", "72m", "84m", "96m",  # Option 2: Rabais + Taux (L-R)
        "Bonus ($)"  # Bonus (S)
    ]
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=header)
        cell.font = Font(bold=True, size=9, color="FFFFFF")
        cell.alignment = header_alignment
        cell.border = thin_border
        
        if col <= 4:
            cell.fill = header_fill
        elif col <= 11:  # Option 1
            cell.fill = option1_fill
        elif col <= 18:  # Option 2
            cell.fill = option2_fill
        else:  # Bonus
            cell.fill = bonus_fill
    
    # Data rows
    for row_idx, prog in enumerate(programs, 4):
        opt1_rates = prog.get("option1_rates") or {}
        opt2_rates = prog.get("option2_rates") or {}
        
        consumer_cash = prog.get("consumer_cash", 0) or 0
        alt_consumer_cash = prog.get("alt_consumer_cash", 0) or 0  # Alternative Consumer Cash pour Option 2
        bonus_cash = prog.get("bonus_cash", 0) or 0
        
        # Format rate display
        def format_rate(rate):
            if rate is None or rate == "-":
                return "-"
            try:
                r = float(rate)
                return f"{r:.2f}%" if r > 0 else "0%"
            except:
                return "-"
        
        data = [
            prog.get("brand", ""),
            prog.get("model", ""),
            prog.get("trim", "") or "",
            prog.get("year", ""),
            # Option 1: Rabais + Taux
            f"${consumer_cash:,.0f}" if consumer_cash else "-",
            format_rate(opt1_rates.get("rate_36")) if opt1_rates else "-",
            format_rate(opt1_rates.get("rate_48")) if opt1_rates else "-",
            format_rate(opt1_rates.get("rate_60")) if opt1_rates else "-",
            format_rate(opt1_rates.get("rate_72")) if opt1_rates else "-",
            format_rate(opt1_rates.get("rate_84")) if opt1_rates else "-",
            format_rate(opt1_rates.get("rate_96")) if opt1_rates else "-",
            # Option 2: Rabais + Taux
            f"${alt_consumer_cash:,.0f}" if alt_consumer_cash else "-",
            format_rate(opt2_rates.get("rate_36")) if opt2_rates else "-",
            format_rate(opt2_rates.get("rate_48")) if opt2_rates else "-",
            format_rate(opt2_rates.get("rate_60")) if opt2_rates else "-",
            format_rate(opt2_rates.get("rate_72")) if opt2_rates else "-",
            format_rate(opt2_rates.get("rate_84")) if opt2_rates else "-",
            format_rate(opt2_rates.get("rate_96")) if opt2_rates else "-",
            # Bonus
            f"${bonus_cash:,.0f}" if bonus_cash else "-",
        ]
        
        for col, value in enumerate(data, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center")
            
            # Color coding for columns
            if col >= 5 and col <= 11:  # Option 1
                cell.fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
            elif col >= 12 and col <= 18:  # Option 2
                cell.fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")
            elif col == 19:  # Bonus
                cell.fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    
    # Adjust column widths
    column_widths = [12, 18, 28, 7, 12, 8, 8, 8, 8, 8, 8, 12, 8, 8, 8, 8, 8, 8, 12]
    for col, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width
    
    # Row height for headers
    ws.row_dimensions[2].height = 30
    ws.row_dimensions[3].height = 25
    
    # Freeze panes
    ws.freeze_panes = 'A4'
    
    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

def send_excel_email(excel_data: bytes, admin_email: str, program_month: int, program_year: int, program_count: int):
    """Envoie le fichier Excel par email"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    
    month_names = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                   "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    
    msg = MIMEMultipart()
    msg['From'] = SMTP_EMAIL
    msg['To'] = admin_email
    msg['Subject'] = f"CalcAuto AiPro - Extraction PDF {month_names[program_month]} {program_year}"
    
    body = f"""
Bonjour,

L'extraction du PDF des programmes de financement est terminée.

📊 Résumé:
• Période: {month_names[program_month]} {program_year}
• Programmes extraits: {program_count}

Le fichier Excel est joint à cet email pour vérification.

⚠️ IMPORTANT: Veuillez vérifier les données dans le fichier Excel avant de confirmer l'import dans l'application.

---
CalcAuto AiPro
    """
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Attach Excel file
    attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    attachment.set_payload(excel_data)
    encoders.encode_base64(attachment)
    filename = f"programmes_{month_names[program_month].lower()}_{program_year}.xlsx"
    attachment.add_header('Content-Disposition', f'attachment; filename={filename}')
    msg.attach(attachment)
    
    # Send email
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Error sending Excel email: {str(e)}")
        return False

# ============ PDF Import with AI ============

@router.post("/verify-password")
async def verify_password(password: str = Form(...)):
    """Vérifie le mot de passe admin"""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    return {"success": True, "message": "Mot de passe vérifié"}

@router.post("/extract-pdf", response_model=ExtractedDataResponse)
async def extract_pdf(
    file: UploadFile = File(...),
    password: str = Form(...),
    program_month: int = Form(...),
    program_year: int = Form(...),
    start_page: int = Form(1),
    end_page: int = Form(9999),
    lease_start_page: Optional[int] = Form(None),
    lease_end_page: Optional[int] = Form(None)
):
    """
    Extrait les données de financement d'un PDF via OpenAI GPT-4
    Retourne les programmes pour prévisualisation/modification avant sauvegarde
    
    start_page/end_page = pages Retail
    lease_start_page/lease_end_page = pages SCI Lease (optionnel)
    (indexation commence à 1)
    """
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Clé OpenAI non configurée")
    
    try:
        import tempfile
        import os as os_module
        import base64
        from openai import OpenAI
        import PyPDF2
        
        # Save uploaded PDF temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Extract text ONLY from specified pages using PyPDF2
            pdf_text = ""
            with open(tmp_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                total_pages = len(reader.pages)
                
                # Convert to 0-based index and validate range
                start_idx = max(0, start_page - 1)  # Convert 1-based to 0-based
                end_idx = min(total_pages, end_page)  # Keep as-is (exclusive end)
                
                logger.info(f"PDF has {total_pages} pages. Extracting pages {start_page} to {end_page} (indices {start_idx} to {end_idx})")
                
                # Only extract the specified pages
                for page_num in range(start_idx, end_idx):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    pdf_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
                
                logger.info(f"Extracted {end_idx - start_idx} pages, total text length: {len(pdf_text)} characters")
            
            # Use OpenAI to extract structured data
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            extraction_prompt = f"""EXTRAIS TOUS LES VÉHICULES de ce PDF de programmes de financement FCA Canada.

TEXTE COMPLET DU PDF:
{pdf_text}

=== FORMAT DES LIGNES DU PDF ===
Chaque ligne suit ce format:
VÉHICULE [Consumer Cash $X,XXX] [6 taux Option1] [6 taux Option2] [Bonus Cash]

- Si tu vois "- - - - - -" = option non disponible (null)
- Si tu vois "P" avant un montant = c'est quand même le montant
- 6 taux = 36M, 48M, 60M, 72M, 84M, 96M

=== OPTION 2 - RÈGLE CRITIQUE ===
ATTENTION: BEAUCOUP de véhicules n'ont PAS d'Option 2 (Alternative Consumer Cash Finance Rates).
- Les colonnes Option 2 dans le PDF sont SOUVENT VIDES (pas de chiffres, pas de tirets)
- Si les colonnes Option 2 d'un véhicule sont VIDES ou contiennent UNIQUEMENT des tirets "- - - - - -", alors option2_rates = null
- NE PAS inventer ou copier des taux Option 2 d'un autre véhicule
- NE PAS supposer qu'un véhicule a Option 2 juste parce qu'un autre véhicule du même modèle l'a
- Chaque ligne/véhicule doit être traitée INDIVIDUELLEMENT pour Option 2
- En cas de DOUTE sur l'existence d'Option 2, mettre null

=== BONUS CASH / DELIVERY CREDIT - RÈGLE CRITIQUE ===
ATTENTION: La dernière colonne du PDF est "Delivery Credit" (code 261Q02).
Cette colonne est marquée TYPE OF SALE: 'E' Only.
*** NE JAMAIS IMPORTER LES VALEURS DE DELIVERY CREDIT ***
Le Delivery Credit ($1,000, $3,000, $5,000 etc.) est UNIQUEMENT pour les ventes en ligne ('E').
Il ne s'applique PAS aux ventes en concession.
bonus_cash doit TOUJOURS être 0 pour TOUS les véhicules.
Ignore complètement cette colonne lors de l'extraction.

=== EXEMPLES ===

2026 MODELS:
"Grand Caravan SXT    4.99%... " → bonus_cash: 0
"Ram 1500 Big Horn    $6,000  4.99%..." → bonus_cash: 0

2025 MODELS (IGNORER le Delivery Credit à droite!):
"Compass North  $7,500  4.99%...   $1,000" → bonus_cash: 0 (le $1,000 est Delivery Credit = IGNORER)
"Ram 1500 Sport  $10,000  4.99%...  $3,000" → bonus_cash: 0 (le $3,000 est Delivery Credit = IGNORER)
"Ram 2500/3500 Gas Models  $9,500  4.99%...  -" → bonus_cash: 0

=== MARQUES À EXTRAIRE ===
- CHRYSLER: Grand Caravan, Pacifica
- JEEP: Compass, Cherokee, Wrangler, Gladiator, Grand Cherokee, Grand Wagoneer
- DODGE: Durango, Charger, Hornet
- RAM: ProMaster, 1500, 2500, 3500, Chassis Cab

=== ANNÉES ===
- "2026 MODELS" → year: 2026
- "2025 MODELS" → year: 2025
Extrais les véhicules des DEUX sections!

=== JSON REQUIS ===
{{
    "programs": [
        {{
            "brand": "Chrysler",
            "model": "Grand Caravan", 
            "trim": "SXT",
            "year": 2026,
            "consumer_cash": 0,
            "bonus_cash": 0,
            "option1_rates": {{"rate_36": 4.99, "rate_48": 4.99, "rate_60": 4.99, "rate_72": 4.99, "rate_84": 4.99, "rate_96": 4.99}},
            "option2_rates": null
        }},
        ... TOUS les autres véhicules ...
    ]
}}

EXTRAIS ABSOLUMENT TOUS LES VÉHICULES DES SECTIONS 2026 ET 2025. 
BONUS_CASH = 0 POUR TOUS LES VÉHICULES (la colonne Delivery Credit 'E' Only est à IGNORER).
VÉRIFIE OPTION 2 POUR CHAQUE VÉHICULE: si les colonnes sont vides → null!"""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Tu extrais TOUS les véhicules d'un PDF FCA Canada. CHAQUE ligne = 1 entrée. N'oublie AUCUN véhicule. Sections 2026 ET 2025. JSON valide uniquement."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=16000,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                response_text = response_text.strip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
            
            # Clean common JSON issues
            response_text = response_text.replace('\n', ' ').replace('\r', '')
            response_text = re.sub(r',\s*}', '}', response_text)  # Remove trailing commas
            response_text = re.sub(r',\s*]', ']', response_text)  # Remove trailing commas in arrays
            
            try:
                data = json.loads(response_text)
                programs = data.get("programs", [])
            except json.JSONDecodeError as e:
                # Try to fix common issues and retry
                try:
                    # Find the programs array and try to parse it
                    programs_match = re.search(r'"programs"\s*:\s*\[(.*)\]', response_text, re.DOTALL)
                    if programs_match:
                        programs_str = programs_match.group(1)
                        # Try to parse individual objects
                        programs = []
                        obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                        for obj_match in re.finditer(obj_pattern, programs_str):
                            try:
                                obj = json.loads(obj_match.group())
                                programs.append(obj)
                            except:
                                continue
                        if programs:
                            data = {"programs": programs}
                        else:
                            raise e
                    else:
                        raise e
                except:
                    return ExtractedDataResponse(
                        success=False,
                        message=f"Erreur de parsing JSON: {str(e)}",
                        programs=[],
                        raw_text=response_text[:3000]
                    )
            
            # Validate and clean programs
            valid_programs = []
            for p in programs:
                # Ensure required fields exist
                if 'brand' in p and 'model' in p:
                    # Clean up rates
                    if p.get('option1_rates') and isinstance(p['option1_rates'], dict):
                        for key in ['rate_36', 'rate_48', 'rate_60', 'rate_72', 'rate_84', 'rate_96']:
                            if key not in p['option1_rates']:
                                p['option1_rates'][key] = 4.99
                    
                    # Validate Option 2 rates - remove if suspicious
                    if p.get('option2_rates') and isinstance(p['option2_rates'], dict):
                        opt2 = p['option2_rates']
                        # Check if all Option 2 rates are 0 or missing -> likely should be null
                        rate_values = [opt2.get(f'rate_{t}', 0) for t in [36, 48, 60, 72, 84, 96]]
                        all_zero_or_missing = all(v == 0 or v is None for v in rate_values)
                        
                        if all_zero_or_missing:
                            # All rates are 0 = no real Option 2
                            p['option2_rates'] = None
                            logger.info(f"[Import] Removed empty option2_rates for {p.get('brand')} {p.get('model')} {p.get('trim','')}")
                        else:
                            for key in ['rate_36', 'rate_48', 'rate_60', 'rate_72', 'rate_84', 'rate_96']:
                                if key not in opt2:
                                    opt2[key] = 0
                    
                    valid_programs.append(p)
            
            # Generate Excel and send by email
            excel_sent = False
            if EXCEL_AVAILABLE and valid_programs and SMTP_EMAIL:
                try:
                    excel_data = generate_excel_from_programs(valid_programs, program_month, program_year)
                    excel_sent = send_excel_email(excel_data, SMTP_EMAIL, program_month, program_year, len(valid_programs))
                    logger.info(f"Excel generated and sent: {excel_sent}")
                except Exception as excel_error:
                    logger.error(f"Error generating/sending Excel: {str(excel_error)}")
            
            # AUTO-SAVE: Sauvegarder automatiquement les programmes dans la base de données
            saved_count = 0
            try:
                # D'abord, supprimer les anciens programmes de la même période
                delete_result = await db.programs.delete_many({
                    "program_month": program_month,
                    "program_year": program_year
                })
                logger.info(f"Deleted {delete_result.deleted_count} old programs for {program_month}/{program_year}")
                
                # Taux par défaut (4.99% standard)
                default_rates = {
                    "rate_36": 4.99, "rate_48": 4.99, "rate_60": 4.99,
                    "rate_72": 4.99, "rate_84": 4.99, "rate_96": 4.99
                }
                
                # Ensuite, ajouter les nouveaux programmes
                for prog in valid_programs:
                    # S'assurer que option1_rates n'est pas None
                    opt1 = prog.get("option1_rates")
                    if opt1 is None or not isinstance(opt1, dict):
                        opt1 = default_rates.copy()
                    
                    program_doc = {
                        "id": str(uuid.uuid4()),
                        "brand": prog.get("brand", ""),
                        "model": prog.get("model", ""),
                        "trim": prog.get("trim", ""),
                        "year": prog.get("year", program_year),
                        "consumer_cash": prog.get("consumer_cash", 0) or 0,
                        "bonus_cash": prog.get("bonus_cash", 0) or 0,
                        "alt_consumer_cash": prog.get("alt_consumer_cash", 0) or 0,
                        "option1_rates": opt1,
                        "option2_rates": prog.get("option2_rates"),
                        "program_month": program_month,
                        "program_year": program_year,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    await db.programs.insert_one(program_doc)
                    saved_count += 1
                
                logger.info(f"Auto-saved {saved_count} programs for {program_month}/{program_year}")
            except Exception as save_error:
                logger.error(f"Error auto-saving programs: {str(save_error)}")
            
            # ============ SCI LEASE RATES EXTRACTION ============
            sci_lease_count = 0
            if lease_start_page and lease_end_page:
                try:
                    # Extract text from SCI Lease pages
                    lease_text = ""
                    with open(tmp_path, 'rb') as pdf_file:
                        reader = PyPDF2.PdfReader(pdf_file)
                        total_pages = len(reader.pages)
                        lease_start_idx = max(0, lease_start_page - 1)
                        lease_end_idx = min(total_pages, lease_end_page)
                        
                        logger.info(f"Extracting SCI Lease pages {lease_start_page} to {lease_end_page}")
                        
                        for page_num in range(lease_start_idx, lease_end_idx):
                            page = reader.pages[page_num]
                            page_text = page.extract_text()
                            lease_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
                        
                        logger.info(f"SCI Lease: Extracted {lease_end_idx - lease_start_idx} pages, {len(lease_text)} chars")
                    
                    if lease_text.strip():
                        # Use GPT-4o to extract SCI Lease rates
                        lease_extraction_prompt = f"""EXTRAIS TOUS les véhicules et leurs taux de LOCATION SCI (SCI Lease) de ce PDF.

TEXTE DU PDF (pages SCI Lease):
{lease_text}

=== CONTEXTE ===
Ce sont les programmes de LOCATION (lease) SCI Lease Corp pour concessionnaires FCA Canada.
Chaque véhicule peut avoir:
- Un "Standard Rate" (taux standard SCI, stackable avec Lease Cash seulement)
- Un "Alternative Rate" (taux alternatif, stackable avec Alternative Lease Cash)
- Un "Lease Cash" (rabais avant taxes pour la location)
- Un "Bonus Cash" / "Alt Lease Cash" (rabais supplémentaire)

Les termes de location sont: 24, 27, 36, 39, 42, 48, 51, 54, 60 mois.

=== IMPORTANT ===
- Si un taux montre "- -" ou est vide = null (pas disponible)
- Si "Standard Rate" n'est pas disponible, standard_rates = null
- Si "Alternative Rate" n'est pas disponible, alternative_rates = null
- Le Lease Cash peut varier par véhicule ($0, $3500, $7500, $10000, etc.)
- SÉPARER les véhicules 2026 et 2025

=== MARQUES À EXTRAIRE ===
- CHRYSLER: Grand Caravan, Pacifica
- JEEP: Compass, Cherokee, Wrangler, Gladiator, Grand Cherokee, Grand Wagoneer
- DODGE: Durango, Charger, Hornet
- RAM: ProMaster, 1500, 2500, 3500
- FIAT: 500e

=== JSON REQUIS ===
{{
    "vehicles_2026": [
        {{
            "model": "Grand Caravan SXT",
            "brand": "Chrysler",
            "lease_cash": 0,
            "standard_rates": null,
            "alternative_rates": {{"24": 4.99, "27": 4.99, "36": 5.49, "39": 5.49, "42": 5.49, "48": 6.49, "51": 6.49, "54": 6.49, "60": 6.99}}
        }}
    ],
    "vehicles_2025": [
        {{
            "model": "Compass North",
            "brand": "Jeep",
            "lease_cash": 7500,
            "standard_rates": {{"24": 8.79, "27": 8.79, "36": 8.29, "39": 8.29, "42": 8.29, "48": 8.29, "51": 8.29, "54": 8.29, "60": 8.29}},
            "alternative_rates": {{"24": 1.99, "27": 1.99, "36": 1.99, "39": 1.99, "42": 1.99, "48": 1.99, "51": 1.99, "54": 1.99, "60": 1.99}}
        }}
    ]
}}

EXTRAIS ABSOLUMENT TOUS LES VÉHICULES. JSON valide uniquement."""

                        lease_response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "Tu extrais les taux de location SCI Lease d'un PDF FCA Canada. CHAQUE véhicule = 1 entrée. N'oublie AUCUN véhicule. JSON valide uniquement."},
                                {"role": "user", "content": lease_extraction_prompt}
                            ],
                            temperature=0.1,
                            max_tokens=16000,
                            response_format={"type": "json_object"}
                        )
                        
                        lease_response_text = lease_response.choices[0].message.content.strip()
                        
                        # Clean up response
                        if lease_response_text.startswith("```"):
                            lines = lease_response_text.split("\n")
                            lease_response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                            lease_response_text = lease_response_text.strip()
                        if lease_response_text.endswith("```"):
                            lease_response_text = lease_response_text[:-3].strip()
                        
                        lease_response_text = lease_response_text.replace('\n', ' ').replace('\r', '')
                        lease_response_text = re.sub(r',\s*}', '}', lease_response_text)
                        lease_response_text = re.sub(r',\s*]', ']', lease_response_text)
                        
                        lease_data = json.loads(lease_response_text)
                        
                        vehicles_2026 = lease_data.get("vehicles_2026", [])
                        vehicles_2025 = lease_data.get("vehicles_2025", [])
                        sci_lease_count = len(vehicles_2026) + len(vehicles_2025)
                        
                        if sci_lease_count > 0:
                            # Build the SCI lease rates JSON
                            month_names_local = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                                           "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
                            
                            sci_lease_rates = {
                                "program_period": f"{month_names_local[program_month]} {program_year}",
                                "source": "FCA Canada QBC Retail Lease Incentive Program",
                                "terms": [24, 27, 36, 39, 42, 48, 51, 54, 60],
                                "notes": {
                                    "standard_rates": "SCI Standard Rate - Stackable with Lease Cash only (Type of Sale L)",
                                    "alternative_rates": "SCI Alternative Rate - Stackable with Alternative Lease Cash (Type of Sale L)",
                                    "lease_cash": "Before Tax discount - reduce selling price",
                                    "bonus_cash": "After Tax discount - shown as line item on Bill of Sale",
                                    "dealer_reserve": "$200 flat fee from SCI Lease Corp per funded lease deal"
                                },
                                "vehicles_2026": vehicles_2026,
                                "vehicles_2025": vehicles_2025
                            }
                            
                            # Save to JSON file
                            # Use English month abbreviations for file naming consistency
                            en_month_abbrev = ["", "jan", "feb", "mar", "apr", "may", "jun",
                                              "jul", "aug", "sep", "oct", "nov", "dec"]
                            sci_filename = f"sci_lease_rates_{en_month_abbrev[program_month]}{program_year}.json"
                            sci_path = ROOT_DIR / "data" / sci_filename
                            
                            with open(sci_path, 'w', encoding='utf-8') as f:
                                json.dump(sci_lease_rates, f, indent=2, ensure_ascii=False)
                            
                            logger.info(f"SCI Lease rates saved: {sci_path} ({sci_lease_count} vehicles)")
                            
                            # Also update the standard reference file used by the app
                            ref_path = ROOT_DIR / "data" / f"sci_lease_rates_{en_month_abbrev[program_month]}{program_year}.json"
                            if sci_path != ref_path:
                                import shutil
                                shutil.copy2(sci_path, ref_path)
                                logger.info(f"Updated reference file: {ref_path}")
                        
                except json.JSONDecodeError as je:
                    logger.error(f"SCI Lease JSON parse error: {str(je)}")
                except Exception as lease_error:
                    logger.error(f"Error extracting SCI Lease rates: {str(lease_error)}")
            
            lease_msg = f" + {sci_lease_count} taux SCI Lease" if sci_lease_count > 0 else ""
            return ExtractedDataResponse(
                success=True,
                message=f"Extrait et sauvegardé {len(valid_programs)} programmes{lease_msg}" + (" - Excel envoyé par email!" if excel_sent else ""),
                programs=valid_programs,
                raw_text="",
                sci_lease_count=sci_lease_count
            )
            
        finally:
            # Clean up temp file
            os_module.unlink(tmp_path)
            
    except Exception as e:
        logger.error(f"Error extracting PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur d'extraction: {str(e)}")

# ============ Async PDF Extraction (for environments with short timeouts) ============

async def _run_extraction_task(task_id: str, pdf_content: bytes, password: str,
                                program_month: int, program_year: int,
                                start_page: int, end_page: int,
                                lease_start_page: Optional[int], lease_end_page: Optional[int]):
    """Background task: extracts PDF, saves programs, sends email, updates task status in MongoDB."""
    try:
        await db.extract_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "extracting", "message": "Extraction du texte PDF..."}}
        )
        
        import tempfile
        import os as os_module
        import base64
        from openai import OpenAI
        import PyPDF2

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = tmp_file.name

        try:
            # Extract text from specified pages
            pdf_text = ""
            with open(tmp_path, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                total_pages = len(reader.pages)
                start_idx = max(0, start_page - 1)
                end_idx = min(total_pages, end_page)
                for page_num in range(start_idx, end_idx):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    pdf_text += f"\n--- PAGE {page_num + 1} ---\n{page_text}\n"
                logger.info(f"[Async] Extracted {end_idx - start_idx} pages, {len(pdf_text)} chars")

            await db.extract_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "ai_processing", "message": "Analyse IA en cours (programmes)..."}}
            )

            # Use OpenAI to extract structured data (reuse the same prompt as sync endpoint)
            client = OpenAI(api_key=OPENAI_API_KEY)
            extraction_prompt = f"""EXTRAIS TOUS LES VÉHICULES de ce PDF de programmes de financement FCA Canada.

TEXTE COMPLET DU PDF:
{pdf_text}

=== FORMAT DES LIGNES DU PDF ===
Chaque ligne suit ce format:
VÉHICULE [Consumer Cash $X,XXX] [6 taux Option1] [6 taux Option2] [Bonus Cash]

- Si tu vois "- - - - - -" = option non disponible (null)
- Si tu vois "P" avant un montant = c'est quand même le montant
- 6 taux = 36M, 48M, 60M, 72M, 84M, 96M

=== OPTION 2 - RÈGLE CRITIQUE ===
ATTENTION: BEAUCOUP de véhicules n'ont PAS d'Option 2 (Alternative Consumer Cash Finance Rates).
- Les colonnes Option 2 dans le PDF sont SOUVENT VIDES (pas de chiffres, pas de tirets)
- Si les colonnes Option 2 d'un véhicule sont VIDES ou contiennent UNIQUEMENT des tirets "- - - - - -", alors option2_rates = null
- NE PAS inventer ou copier des taux Option 2 d'un autre véhicule
- NE PAS supposer qu'un véhicule a Option 2 juste parce qu'un autre véhicule du même modèle l'a
- Chaque ligne/véhicule doit être traitée INDIVIDUELLEMENT pour Option 2
- En cas de DOUTE sur l'existence d'Option 2, mettre null

=== BONUS CASH / DELIVERY CREDIT - RÈGLE CRITIQUE ===
ATTENTION: La dernière colonne du PDF est "Delivery Credit" (code 261Q02).
Cette colonne est marquée TYPE OF SALE: 'E' Only.
*** NE JAMAIS IMPORTER LES VALEURS DE DELIVERY CREDIT ***
bonus_cash doit TOUJOURS être 0 pour TOUS les véhicules.

=== MARQUES À EXTRAIRE ===
- CHRYSLER: Grand Caravan, Pacifica
- JEEP: Compass, Cherokee, Wrangler, Gladiator, Grand Cherokee, Grand Wagoneer
- DODGE: Durango, Charger, Hornet
- RAM: ProMaster, 1500, 2500, 3500, Chassis Cab

=== ANNÉES ===
- "2026 MODELS" → year: 2026
- "2025 MODELS" → year: 2025
Extrais les véhicules des DEUX sections!

=== JSON REQUIS ===
{{
    "programs": [
        {{
            "brand": "Chrysler",
            "model": "Grand Caravan", 
            "trim": "SXT",
            "year": 2026,
            "consumer_cash": 0,
            "bonus_cash": 0,
            "option1_rates": {{"rate_36": 4.99, "rate_48": 4.99, "rate_60": 4.99, "rate_72": 4.99, "rate_84": 4.99, "rate_96": 4.99}},
            "option2_rates": null
        }}
    ]
}}

EXTRAIS ABSOLUMENT TOUS LES VÉHICULES DES SECTIONS 2026 ET 2025. 
BONUS_CASH = 0 POUR TOUS LES VÉHICULES."""

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Tu extrais TOUS les véhicules d'un PDF FCA Canada. CHAQUE ligne = 1 entrée. N'oublie AUCUN véhicule. Sections 2026 ET 2025. JSON valide uniquement."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=16000,
                response_format={"type": "json_object"}
            )

            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                response_text = response_text.strip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].strip()
            response_text = response_text.replace('\n', ' ').replace('\r', '')
            response_text = re.sub(r',\s*}', '}', response_text)
            response_text = re.sub(r',\s*]', ']', response_text)

            data = json.loads(response_text)
            programs = data.get("programs", [])

            # Validate and clean programs
            valid_programs = []
            for p in programs:
                if 'brand' in p and 'model' in p:
                    if p.get('option1_rates') and isinstance(p['option1_rates'], dict):
                        for key in ['rate_36', 'rate_48', 'rate_60', 'rate_72', 'rate_84', 'rate_96']:
                            if key not in p['option1_rates']:
                                p['option1_rates'][key] = 4.99
                    if p.get('option2_rates') and isinstance(p['option2_rates'], dict):
                        opt2 = p['option2_rates']
                        rate_values = [opt2.get(f'rate_{t}', 0) for t in [36, 48, 60, 72, 84, 96]]
                        if all(v == 0 or v is None for v in rate_values):
                            p['option2_rates'] = None
                        else:
                            for key in ['rate_36', 'rate_48', 'rate_60', 'rate_72', 'rate_84', 'rate_96']:
                                if key not in opt2:
                                    opt2[key] = 0
                    valid_programs.append(p)

            await db.extract_tasks.update_one(
                {"task_id": task_id},
                {"$set": {"status": "saving", "message": f"{len(valid_programs)} programmes extraits. Sauvegarde..."}}
            )

            # Generate Excel and send email
            excel_sent = False
            if EXCEL_AVAILABLE and valid_programs and SMTP_EMAIL:
                try:
                    excel_data = generate_excel_from_programs(valid_programs, program_month, program_year)
                    excel_sent = send_excel_email(excel_data, SMTP_EMAIL, program_month, program_year, len(valid_programs))
                    logger.info(f"[Async] Excel sent: {excel_sent}")
                except Exception as excel_error:
                    logger.error(f"[Async] Excel email error: {str(excel_error)}")

            # Auto-save programs
            saved_count = 0
            try:
                await db.programs.delete_many({"program_month": program_month, "program_year": program_year})
                default_rates = {"rate_36": 4.99, "rate_48": 4.99, "rate_60": 4.99, "rate_72": 4.99, "rate_84": 4.99, "rate_96": 4.99}
                for prog in valid_programs:
                    opt1 = prog.get("option1_rates")
                    if opt1 is None or not isinstance(opt1, dict):
                        opt1 = default_rates.copy()
                    program_doc = {
                        "id": str(uuid.uuid4()),
                        "brand": prog.get("brand", ""),
                        "model": prog.get("model", ""),
                        "trim": prog.get("trim", ""),
                        "year": prog.get("year", program_year),
                        "consumer_cash": prog.get("consumer_cash", 0) or 0,
                        "bonus_cash": prog.get("bonus_cash", 0) or 0,
                        "alt_consumer_cash": prog.get("alt_consumer_cash", 0) or 0,
                        "option1_rates": opt1,
                        "option2_rates": prog.get("option2_rates"),
                        "program_month": program_month,
                        "program_year": program_year,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    await db.programs.insert_one(program_doc)
                    saved_count += 1
                logger.info(f"[Async] Saved {saved_count} programs")
            except Exception as save_error:
                logger.error(f"[Async] Save error: {str(save_error)}")

            # SCI Lease extraction
            sci_lease_count = 0
            if lease_start_page and lease_end_page:
                try:
                    await db.extract_tasks.update_one(
                        {"task_id": task_id},
                        {"$set": {"status": "ai_processing_lease", "message": "Analyse IA en cours (SCI Lease)..."}}
                    )
                    lease_text = ""
                    with open(tmp_path, 'rb') as pdf_file:
                        reader = PyPDF2.PdfReader(pdf_file)
                        total_pages = len(reader.pages)
                        lease_start_idx = max(0, lease_start_page - 1)
                        lease_end_idx = min(total_pages, lease_end_page)
                        for page_num in range(lease_start_idx, lease_end_idx):
                            page = reader.pages[page_num]
                            lease_text += f"\n--- PAGE {page_num + 1} ---\n{page.extract_text()}\n"

                    if lease_text.strip():
                        lease_extraction_prompt = f"""EXTRAIS TOUS les véhicules et leurs taux de LOCATION SCI (SCI Lease) de ce PDF.

TEXTE DU PDF (pages SCI Lease):
{lease_text}

Ce sont les programmes de LOCATION (lease) SCI Lease Corp pour concessionnaires FCA Canada.
Les termes de location sont: 24, 27, 36, 39, 42, 48, 51, 54, 60 mois.
Si un taux montre "- -" ou est vide = null.

=== MARQUES À EXTRAIRE ===
- CHRYSLER: Grand Caravan, Pacifica
- JEEP: Compass, Cherokee, Wrangler, Gladiator, Grand Cherokee, Grand Wagoneer
- DODGE: Durango, Charger, Hornet
- RAM: ProMaster, 1500, 2500, 3500
- FIAT: 500e

=== JSON REQUIS ===
{{
    "vehicles_2026": [
        {{
            "model": "Grand Caravan SXT",
            "brand": "Chrysler",
            "lease_cash": 0,
            "standard_rates": null,
            "alternative_rates": {{"24": 4.99, "27": 4.99, "36": 5.49, "39": 5.49, "42": 5.49, "48": 6.49, "51": 6.49, "54": 6.49, "60": 6.99}}
        }}
    ],
    "vehicles_2025": []
}}

EXTRAIS ABSOLUMENT TOUS LES VÉHICULES. JSON valide uniquement."""

                        lease_response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "Tu extrais les taux de location SCI Lease d'un PDF FCA Canada. JSON valide uniquement."},
                                {"role": "user", "content": lease_extraction_prompt}
                            ],
                            temperature=0.1,
                            max_tokens=16000,
                            response_format={"type": "json_object"}
                        )
                        lease_response_text = lease_response.choices[0].message.content.strip()
                        if lease_response_text.startswith("```"):
                            lines_l = lease_response_text.split("\n")
                            lease_response_text = "\n".join(lines_l[1:-1] if lines_l[-1] == "```" else lines_l[1:])
                        if lease_response_text.endswith("```"):
                            lease_response_text = lease_response_text[:-3].strip()
                        lease_response_text = lease_response_text.replace('\n', ' ').replace('\r', '')
                        lease_response_text = re.sub(r',\s*}', '}', lease_response_text)
                        lease_response_text = re.sub(r',\s*]', ']', lease_response_text)
                        lease_data = json.loads(lease_response_text)

                        vehicles_2026 = lease_data.get("vehicles_2026", [])
                        vehicles_2025 = lease_data.get("vehicles_2025", [])
                        sci_lease_count = len(vehicles_2026) + len(vehicles_2025)

                        if sci_lease_count > 0:
                            month_names_local = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                                               "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
                            en_month_abbrev = ["", "jan", "feb", "mar", "apr", "may", "jun",
                                              "jul", "aug", "sep", "oct", "nov", "dec"]
                            sci_lease_rates = {
                                "program_period": f"{month_names_local[program_month]} {program_year}",
                                "source": "FCA Canada QBC Retail Lease Incentive Program",
                                "terms": [24, 27, 36, 39, 42, 48, 51, 54, 60],
                                "vehicles_2026": vehicles_2026,
                                "vehicles_2025": vehicles_2025
                            }
                            sci_filename = f"sci_lease_rates_{en_month_abbrev[program_month]}{program_year}.json"
                            sci_path = ROOT_DIR / "data" / sci_filename
                            with open(sci_path, 'w', encoding='utf-8') as f:
                                json.dump(sci_lease_rates, f, indent=2, ensure_ascii=False)
                            logger.info(f"[Async] SCI Lease saved: {sci_path} ({sci_lease_count} vehicles)")
                except Exception as lease_error:
                    logger.error(f"[Async] SCI Lease error: {str(lease_error)}")

            # Mark task as complete
            lease_msg = f" + {sci_lease_count} taux SCI Lease" if sci_lease_count > 0 else ""
            email_msg = " - Excel envoyé par email!" if excel_sent else ""
            await db.extract_tasks.update_one(
                {"task_id": task_id},
                {"$set": {
                    "status": "complete",
                    "message": f"Extrait et sauvegardé {len(valid_programs)} programmes{lease_msg}{email_msg}",
                    "programs": valid_programs,
                    "sci_lease_count": sci_lease_count,
                    "completed_at": datetime.utcnow().isoformat()
                }}
            )
        finally:
            os_module.unlink(tmp_path)

    except Exception as e:
        logger.error(f"[Async] Task {task_id} failed: {str(e)}")
        await db.extract_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "error", "message": f"Erreur: {str(e)}"}}
        )


@router.post("/extract-pdf-async")
async def extract_pdf_async(
    file: UploadFile = File(...),
    password: str = Form(...),
    program_month: int = Form(...),
    program_year: int = Form(...),
    start_page: int = Form(1),
    end_page: int = Form(9999),
    lease_start_page: Optional[int] = Form(None),
    lease_end_page: Optional[int] = Form(None)
):
    """Upload PDF and start extraction in background. Returns task_id for polling."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Clé OpenAI non configurée")

    pdf_content = await file.read()
    task_id = str(uuid.uuid4())

    await db.extract_tasks.insert_one({
        "task_id": task_id,
        "status": "queued",
        "message": "En file d'attente...",
        "programs": [],
        "sci_lease_count": 0,
        "created_at": datetime.utcnow().isoformat()
    })

    asyncio.create_task(_run_extraction_task(
        task_id, pdf_content, password,
        program_month, program_year,
        start_page, end_page,
        lease_start_page, lease_end_page
    ))

    return {"task_id": task_id, "status": "queued", "message": "Extraction démarrée en arrière-plan"}


@router.get("/extract-task/{task_id}")
async def get_extract_task(task_id: str):
    """Poll extraction task status."""
    task = await db.extract_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return task


# ============ Residual Guide PDF Upload ============

@router.post("/upload-residual-guide")
async def upload_residual_guide(
    file: UploadFile = File(...),
    password: str = Form(...),
    effective_month: int = Form(...),
    effective_year: int = Form(...)
):
    """
    Upload et parse automatiquement un PDF du guide des valeurs résiduelles SCI.
    Génère un Excel de vérification et l'envoie par email.
    """
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    
    import tempfile
    import os as os_module
    
    tmp_path = None
    try:
        # Save uploaded file temporarily
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        # Parse PDF using our existing parser logic
        import fitz
        TERMS = ["24", "27", "36", "39", "42", "48", "51", "54", "60"]
        BODY_STYLES = [
            "4D Wagon AWD", "4D Wagon", "3D Hatchback",
            "2D Coupe AWD", "4D Sedan AWD",
            "4D Utility 4WD", "4D Utility AWD", "4D Utility",
            "2D Utility 4WD", "2D Utility AWD", "2D Utility",
            "Crew Cab LWB 2WD", "Crew Cab LWB 4WD",
            "Crew Cab SWB 2WD", "Crew Cab SWB 4WD",
            "Crew Cab 4WD",
            "Quad Cab SWB 4WD", "Quad Cab SWB 2WD",
            "Mega Cab 4WD", "Mega Cab 2WD",
            "Reg Cab LWB 2WD", "Reg Cab LWB 4WD",
            "Reg Cab 2WD", "Reg Cab 4WD",
        ]
        
        def is_number(s):
            try:
                int(s)
                return True
            except:
                return False
        
        def is_body_style(s):
            return s in BODY_STYLES
        
        doc = fitz.open(tmp_path)
        all_vehicles = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            lines_raw = [l.strip() for l in text.split('\n') if l.strip()]
            
            clean = []
            for l in lines_raw:
                if '675 Cochrane' in l or 'scileasecorp' in l or 'T: 1-888' in l or 'F: 1-866' in l:
                    continue
                if l in ('LEASE RESIDUAL VALUES', 'STANDARD', 'FEBRUARY 2026', 'RESIDUAL VALUE GUIDE') or l.startswith('Effective:'):
                    continue
                clean.append(l)
            
            current_brand = None
            current_model = None
            current_year = None
            
            i = 0
            while i < len(clean):
                line = clean[i]
                
                if line in ('CHRYSLER', 'DODGE', 'JEEP', 'RAM', 'FIAT'):
                    current_brand = line.title()
                    i += 1
                    if i < len(clean) and (clean[i] == '24' or clean[i].startswith('24 27')):
                        if clean[i] == '24':
                            skip = 0
                            while i + skip < len(clean) and clean[i + skip] in TERMS:
                                skip += 1
                            i += skip
                        else:
                            i += 1
                    continue
                
                if line.startswith('MODEL YEAR'):
                    i += 1
                    continue
                
                import re
                year_match = re.match(r'^(20\d{2})\s+(.+)$', line)
                if year_match:
                    current_year = int(year_match.group(1))
                    model_raw = year_match.group(2).strip()
                    
                    if i + 1 < len(clean):
                        next_line = clean[i + 1]
                        if (not is_body_style(next_line) and not is_number(next_line) and
                            not re.match(r'^(20\d{2})\s+', next_line) and
                            next_line not in ('CHRYSLER', 'DODGE', 'JEEP', 'RAM', 'FIAT') and
                            next_line not in TERMS and not next_line.startswith('24 27')):
                            if i + 2 < len(clean) and (is_body_style(clean[i + 2]) or is_number(clean[i + 2])):
                                current_model = model_raw
                            else:
                                current_model = model_raw + ' ' + next_line
                                i += 1
                        else:
                            current_model = model_raw
                    else:
                        current_model = model_raw
                    
                    i += 1
                    continue
                
                if current_brand and current_model and current_year:
                    trim = line
                    
                    if i + 1 < len(clean):
                        next_line = clean[i + 1]
                        
                        if is_body_style(next_line):
                            body_style = next_line
                            vals = []
                            j = i + 2
                            while j < len(clean) and len(vals) < 9:
                                if is_number(clean[j]):
                                    vals.append(int(clean[j]))
                                    j += 1
                                else:
                                    break
                            
                            if len(vals) == 9:
                                all_vehicles.append({
                                    "brand": current_brand,
                                    "model_year": current_year,
                                    "model_name": current_model,
                                    "trim": trim,
                                    "body_style": body_style,
                                    "residual_percentages": dict(zip(TERMS, vals))
                                })
                                i = j
                                continue
                        
                        if not is_body_style(next_line) and not is_number(next_line):
                            combined_trim = trim + ' ' + next_line
                            if i + 2 < len(clean) and is_body_style(clean[i + 2]):
                                body_style = clean[i + 2]
                                vals = []
                                j = i + 3
                                while j < len(clean) and len(vals) < 9:
                                    if is_number(clean[j]):
                                        vals.append(int(clean[j]))
                                        j += 1
                                    else:
                                        break
                                
                                if len(vals) == 9:
                                    all_vehicles.append({
                                        "brand": current_brand,
                                        "model_year": current_year,
                                        "model_name": current_model,
                                        "trim": combined_trim,
                                        "body_style": body_style,
                                        "residual_percentages": dict(zip(TERMS, vals))
                                    })
                                    i = j
                                    continue
                
                i += 1
        
        doc.close()
        
        if len(all_vehicles) == 0:
            raise HTTPException(status_code=400, detail="Aucun véhicule trouvé dans le PDF. Vérifiez le format du document.")
        
        # Build JSON result
        month_names = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                       "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        
        result = {
            "effective_from": f"{effective_year}-{effective_month:02d}-01",
            "source": f"SCI Lease Corp Stellantis Residual Guide - {month_names[effective_month]} {effective_year}",
            "km_adjustments": {
                "standard_km": 24000,
                "adjustments": {
                    "18000": {"24": 1, "27": 1, "36": 2, "39": 2, "42": 2, "48": 3, "51": 3, "54": 3, "60": 4},
                    "12000": {"24": 2, "27": 2, "36": 3, "39": 3, "42": 3, "48": 4, "51": 4, "54": 4, "60": 5}
                },
                "max_km_per_year": 36000
            },
            "vehicles": all_vehicles
        }
        
        # Save JSON file
        month_lower = month_names[effective_month].lower()
        json_filename = f"sci_residuals_{month_lower}{effective_year}.json"
        json_path = ROOT_DIR / "data" / json_filename
        with open(json_path, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Also update the current reference file
        current_path = ROOT_DIR / "data" / f"sci_residuals_{month_lower}{effective_year}.json"
        logger.info(f"Residual guide saved: {json_path} ({len(all_vehicles)} vehicles)")
        
        # Generate Excel for verification
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from io import BytesIO
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Valeurs résiduelles"
        
        headers = ["Marque", "Année", "Modèle", "Trim", "Carrosserie", "24m", "27m", "36m", "39m", "42m", "48m", "51m", "54m", "60m"]
        header_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
        header_font = Font(color="4ECDC4", bold=True, size=11)
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border
        
        for idx, v in enumerate(all_vehicles, 2):
            ws.cell(row=idx, column=1, value=v["brand"]).border = thin_border
            ws.cell(row=idx, column=2, value=v["model_year"]).border = thin_border
            ws.cell(row=idx, column=3, value=v["model_name"]).border = thin_border
            ws.cell(row=idx, column=4, value=v["trim"]).border = thin_border
            ws.cell(row=idx, column=5, value=v["body_style"]).border = thin_border
            for ti, term in enumerate(TERMS):
                val = v["residual_percentages"].get(term, 0)
                cell = ws.cell(row=idx, column=6 + ti, value=val)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
        
        # Auto-width columns
        for col in range(1, len(headers) + 1):
            max_len = max(len(str(ws.cell(row=r, column=col).value or '')) for r in range(1, len(all_vehicles) + 2))
            ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = max_len + 3
        
        excel_buffer = BytesIO()
        wb.save(excel_buffer)
        excel_data = excel_buffer.getvalue()
        
        # Send verification email
        email_sent = False
        if SMTP_EMAIL and SMTP_PASSWORD:
            try:
                import smtplib
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                from email.mime.base import MIMEBase
                from email import encoders
                
                msg = MIMEMultipart()
                msg['From'] = SMTP_EMAIL
                msg['To'] = SMTP_EMAIL
                msg['Subject'] = f"CalcAuto - Guide Résiduel {month_names[effective_month]} {effective_year} ({len(all_vehicles)} véhicules)"
                
                # Count by brand
                brands = {}
                for v in all_vehicles:
                    b = v["brand"]
                    brands[b] = brands.get(b, 0) + 1
                brand_summary = "\n".join([f"  • {b}: {c} véhicules" for b, c in sorted(brands.items())])
                
                body = f"""Bonjour,

Le guide des valeurs résiduelles a été importé avec succès.

📊 Résumé:
• Période: {month_names[effective_month]} {effective_year}
• Total: {len(all_vehicles)} véhicules extraits

Par marque:
{brand_summary}

Le fichier Excel est joint pour vérification.

⚠️ IMPORTANT: Vérifiez les données avant utilisation dans les calculs de location.

---
CalcAuto AiPro"""
                
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                attachment = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                attachment.set_payload(excel_data)
                encoders.encode_base64(attachment)
                att_filename = f"residuels_{month_lower}_{effective_year}.xlsx"
                attachment.add_header('Content-Disposition', f'attachment; filename={att_filename}')
                msg.attach(attachment)
                
                server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
                server.starttls()
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
                server.send_message(msg)
                server.quit()
                email_sent = True
                logger.info(f"Residual guide email sent to {SMTP_EMAIL}")
            except Exception as e:
                logger.error(f"Error sending residual email: {str(e)}")
        
        # Count by brand for response
        brands_count = {}
        for v in all_vehicles:
            brands_count[v["brand"]] = brands_count.get(v["brand"], 0) + 1
        
        return {
            "success": True,
            "total_vehicles": len(all_vehicles),
            "brands": brands_count,
            "json_file": json_filename,
            "email_sent": email_sent,
            "message": f"{len(all_vehicles)} véhicules extraits et sauvegardés"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing residual guide: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")
    finally:
        if tmp_path and os_module.path.exists(tmp_path):
            os_module.unlink(tmp_path)

@router.post("/save-programs")
async def save_programs(request: SaveProgramsRequest):
    """
    Sauvegarde les programmes validés dans la base de données
    Remplace les programmes existants pour le mois/année spécifié
    Garde seulement les 6 derniers mois d'historique
    """
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")
    
    # Delete existing programs for this period
    await db.programs.delete_many({
        "program_month": request.program_month,
        "program_year": request.program_year
    })
    
    # Insert new programs
    inserted = 0
    skipped = 0
    corrections_applied = []
    default_rates = {"rate_36": 4.99, "rate_48": 4.99, "rate_60": 4.99, "rate_72": 4.99, "rate_84": 4.99, "rate_96": 4.99}
    
    for prog_data in request.programs:
        # Skip invalid entries (missing brand/model)
        if not prog_data.get("brand") or not prog_data.get("model"):
            skipped += 1
            continue
            
        # Ensure option1_rates has a default value if missing
        if not prog_data.get("option1_rates"):
            prog_data["option1_rates"] = default_rates.copy()
        elif isinstance(prog_data["option1_rates"], dict):
            prog_data["option1_rates"] = FinancingRates(**prog_data["option1_rates"]).dict()
            
        # Process option2_rates if present
        if prog_data.get("option2_rates") and isinstance(prog_data["option2_rates"], dict):
            prog_data["option2_rates"] = FinancingRates(**prog_data["option2_rates"]).dict()
        
        prog_data["program_month"] = request.program_month
        prog_data["program_year"] = request.program_year
        prog_data["bonus_cash"] = prog_data.get("bonus_cash", 0)
        prog_data["consumer_cash"] = prog_data.get("consumer_cash", 0)

        # Appliquer les corrections memorisees (matching flexible)
        correction = await find_best_correction(
            prog_data.get("brand", ""),
            prog_data.get("model", ""),
            prog_data.get("trim", ""),
            prog_data.get("year", 2026)
        )
        correction_applied = False
        correction_details = {}
        if correction and correction.get("corrected_values"):
            cv = correction["corrected_values"]
            if cv.get("consumer_cash") is not None:
                old_val = prog_data.get("consumer_cash", 0)
                prog_data["consumer_cash"] = cv["consumer_cash"]
                if old_val != cv["consumer_cash"]:
                    correction_details["consumer_cash"] = {"avant": old_val, "apres": cv["consumer_cash"]}
            if cv.get("alternative_consumer_cash") is not None:
                old_val = prog_data.get("alternative_consumer_cash", 0)
                prog_data["alternative_consumer_cash"] = cv["alternative_consumer_cash"]
                if old_val != cv["alternative_consumer_cash"]:
                    correction_details["alternative_consumer_cash"] = {"avant": old_val, "apres": cv["alternative_consumer_cash"]}
            if cv.get("bonus_cash") is not None:
                old_val = prog_data.get("bonus_cash", 0)
                prog_data["bonus_cash"] = cv["bonus_cash"]
                if old_val != cv["bonus_cash"]:
                    correction_details["bonus_cash"] = {"avant": old_val, "apres": cv["bonus_cash"]}
            if cv.get("option1_rates"):
                prog_data["option1_rates"] = cv["option1_rates"]
                correction_details["option1_rates"] = "corrige"
            if cv.get("option2_rates") is not None:
                prog_data["option2_rates"] = cv["option2_rates"]
                correction_details["option2_rates"] = "corrige"
            correction_applied = True
            # Incrementer le compteur d'application
            await db.program_corrections.update_one(
                {"brand": correction["brand"], "model": correction["model"], "trim": correction["trim"], "year": correction["year"]},
                {"$inc": {"times_applied": 1}, "$set": {"last_applied_at": datetime.utcnow().isoformat()}}
            )
            logger.info(f"[CORRECTION] Appliquee pour {prog_data.get('brand')} {prog_data.get('model')} {prog_data.get('trim')}")
        
        if correction_applied:
            corrections_applied.append({
                "vehicule": f"{prog_data.get('brand')} {prog_data.get('model')} {prog_data.get('trim')} {prog_data.get('year')}",
                "changes": correction_details
            })
        
        try:
            prog = VehicleProgram(**prog_data)
            await db.programs.insert_one(prog.dict())
            inserted += 1
        except Exception as e:
            logger.warning(f"Skipped invalid program: {prog_data.get('brand')} {prog_data.get('model')} - {str(e)}")
            skipped += 1
            continue
    
    # Clean up old programs (keep only 6 months)
    await cleanup_old_programs()
    
    # Calculate brands summary for report
    brands_summary = {}
    for prog_data in request.programs:
        brand = prog_data.get("brand", "Inconnu")
        if brand not in brands_summary:
            brands_summary[brand] = 0
        brands_summary[brand] += 1
    
    # Send automatic email report
    try:
        await send_import_report_email(
            programs_count=inserted,
            program_month=request.program_month,
            program_year=request.program_year,
            brands_summary=brands_summary,
            skipped_count=skipped
        )
        logger.info(f"Import report email sent to {SMTP_EMAIL}")
    except Exception as e:
        logger.warning(f"Failed to send import report email: {str(e)}")
    
    # Force logout all users after data change
    await db.tokens.delete_many({})
    logger.info(f"[PDF IMPORT] Tokens invalides pour forcer reconnexion")

    return {
        "success": True,
        "message": f"Sauvegardé {inserted} programmes pour {request.program_month}/{request.program_year}" + (f" ({skipped} ignorés)" if skipped > 0 else "") + (f" — {len(corrections_applied)} corrections appliquées" if corrections_applied else "") + " - Tous les utilisateurs deconnectes",
        "inserted": inserted,
        "skipped": skipped,
        "corrections_applied": len(corrections_applied),
        "correction_details": corrections_applied[:50]
    }


@router.get("/corrections")
async def list_corrections():
    """Retourne toutes les corrections memorisees avec statistiques."""
    corrections = await db.program_corrections.find({}, {"_id": 0}).sort("corrected_at", -1).to_list(500)
    return {
        "total": len(corrections),
        "corrections": corrections
    }


@router.delete("/corrections/{brand}/{model}/{year}")
async def delete_correction(brand: str, model: str, year: int, password: str = ""):
    """Supprime une correction memorisee."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe admin incorrect")
    result = await db.program_corrections.delete_many({"brand": brand, "model": model, "year": year})
    return {"deleted": result.deleted_count}


@router.delete("/corrections/all")
async def delete_all_corrections(password: str = ""):
    """Supprime toutes les corrections memorisees."""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Mot de passe admin incorrect")
    result = await db.program_corrections.delete_many({})
    return {"deleted": result.deleted_count}


async def send_import_report_email(programs_count: int, program_month: int, program_year: int, brands_summary: dict, skipped_count: int = 0):
    """Envoie automatiquement un rapport par email après l'import des programmes"""
    months_fr = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
        5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
        9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
    }
    month_name = months_fr.get(program_month, str(program_month))
    
    # Generate brands table
    brands_rows = ""
    total_programs = 0
    for brand in ['Chrysler', 'Jeep', 'Dodge', 'Ram', 'Fiat']:
        count = brands_summary.get(brand, 0)
        if count > 0:
            brands_rows += f"<tr><td style='padding: 10px; border-bottom: 1px solid #eee;'>{brand}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold;'>{count}</td></tr>"
            total_programs += count
    
    # Add any other brands not in the standard list
    for brand, count in brands_summary.items():
        if brand not in ['Chrysler', 'Jeep', 'Dodge', 'Ram', 'Fiat'] and count > 0:
            brands_rows += f"<tr><td style='padding: 10px; border-bottom: 1px solid #eee;'>{brand}</td><td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; font-weight: bold;'>{count}</td></tr>"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #1a5f4a 0%, #2d8f6f 100%); color: #fff; padding: 25px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .header .subtitle {{ margin-top: 8px; opacity: 0.9; }}
            .content {{ padding: 25px; }}
            .success-badge {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; font-size: 16px; }}
            .success-badge strong {{ font-size: 18px; }}
            .stats-box {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px; text-align: center; }}
            .big-number {{ font-size: 56px; font-weight: bold; color: #1a5f4a; }}
            .big-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th {{ background: #1a5f4a; color: #fff; padding: 12px; text-align: left; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; border-top: 1px solid #eee; }}
            .warning-box {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 12px; margin-top: 15px; color: #856404; font-size: 13px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Import Réussi!</h1>
                <div class="subtitle">CalcAuto AiPro - Rapport d'import automatique</div>
            </div>
            <div class="content">
                <div class="success-badge">
                    <strong>🎉 Programmes {month_name} {program_year}</strong><br>
                    importés avec succès!
                </div>
                
                <div class="stats-box">
                    <div class="big-number">{programs_count}</div>
                    <div class="big-label">programmes de financement</div>
                </div>
                
                <h3 style="color: #1a5f4a; border-bottom: 2px solid #1a5f4a; padding-bottom: 8px;">📊 Répartition par marque</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Marque</th>
                            <th style="text-align: center;">Nombre</th>
                        </tr>
                    </thead>
                    <tbody>
                        {brands_rows}
                        <tr style="background: #f8f9fa; font-weight: bold;">
                            <td style="padding: 12px;">TOTAL</td>
                            <td style="padding: 12px; text-align: center;">{programs_count}</td>
                        </tr>
                    </tbody>
                </table>
                
                {f'<div class="warning-box">⚠️ {skipped_count} programme(s) ignoré(s) en raison de données invalides.</div>' if skipped_count > 0 else ''}
                
                <p style="margin-top: 25px; color: #666; font-size: 14px;">
                    Les nouveaux programmes sont maintenant disponibles dans l'application CalcAuto AiPro. 
                    Vos clients peuvent commencer à utiliser les nouveaux taux immédiatement.
                </p>
            </div>
            <div class="footer">
                <p style="margin: 0;"><strong>CalcAuto AiPro</strong></p>
                <p style="margin: 8px 0 0;">Rapport généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    subject = f"✅ Import {month_name} {program_year} - {programs_count} programmes"
    
    send_email(SMTP_EMAIL, subject, html_body)

async def cleanup_old_programs():
    """Supprime les programmes de plus de 6 mois"""
    # Get all unique periods
    pipeline = [
        {"$group": {
            "_id": {"month": "$program_month", "year": "$program_year"}
        }},
        {"$sort": {"_id.year": -1, "_id.month": -1}}
    ]
    periods = await db.programs.aggregate(pipeline).to_list(100)
    
    # Keep only the 6 most recent periods
    if len(periods) > 6:
        periods_to_delete = periods[6:]
        for p in periods_to_delete:
            await db.programs.delete_many({
                "program_month": p["_id"]["month"],
                "program_year": p["_id"]["year"]
            })
            logger.info(f"Deleted old programs for {p['_id']['month']}/{p['_id']['year']}")

