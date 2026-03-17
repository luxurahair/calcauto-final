"""
OCR par Zones pour Factures FCA - Version Industrielle
Pipeline: Image → Correction → Zones → OCR ciblé → Validation
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image
import io
import re
import logging

logger = logging.getLogger(__name__)


def order_points(pts):
    """Ordonne les 4 points: top-left, top-right, bottom-right, bottom-left"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts):
    """Applique une transformation perspective pour redresser le document"""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


def auto_warp_document(image):
    """Détecte et redresse automatiquement le document"""
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 75, 200)
        
        contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            
            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype("float32")
                return four_point_transform(image, pts)
        
        return image
    except Exception as e:
        logger.warning(f"Auto-warp failed: {e}")
        return image


def preprocess_zone(zone_img):
    """Prétraitement optimisé pour OCR"""
    if len(zone_img.shape) == 3:
        gray = cv2.cvtColor(zone_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = zone_img
    
    # Augmenter contraste
    gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=20)
    
    # Seuillage adaptatif
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )
    
    return thresh


def ocr_zone(zone_img, lang="eng+fra", psm=6):
    """OCR sur une zone prétraitée"""
    try:
        processed = preprocess_zone(zone_img)
        text = pytesseract.image_to_string(
            processed,
            lang=lang,
            config=f"--psm {psm} --oem 3"
        )
        return text.strip()
    except Exception as e:
        logger.error(f"OCR zone error: {e}")
        return ""


def extract_zones(image):
    """Découpe l'image en zones FCA"""
    h, w = image.shape[:2]
    
    zones = {
        # Zone VIN: haut gauche (0-25% hauteur, 0-60% largeur)
        "vin": image[0:int(h*0.25), 0:int(w*0.65)],
        
        # Zone financière: haut droite (0-35% hauteur, 50-100% largeur)
        "finance": image[0:int(h*0.40), int(w*0.45):w],
        
        # Zone options: centre (35-85% hauteur, toute largeur)
        "options": image[int(h*0.35):int(h*0.85), :],
        
        # Zone totaux: bas (80-100% hauteur)
        "totals": image[int(h*0.75):h, :]
    }
    
    return zones


def parse_vin_zone(text):
    """Parse le VIN depuis la zone VIN"""
    # VIN avec tirets FCA: XXXXX-XX-XXXXXX
    vin_match = re.search(r'([0-9A-HJ-NPR-Z]{5})[-\s]?([A-HJ-NPR-Z0-9]{2})[-\s]?([A-HJ-NPR-Z0-9]{6,10})', text)
    if vin_match:
        vin = vin_match.group(1) + vin_match.group(2) + vin_match.group(3)
        return vin[:17] if len(vin) >= 17 else vin
    
    # VIN standard 17 chars
    vin_match = re.search(r'\b([0-9A-HJ-NPR-Z]{17})\b', text)
    if vin_match:
        return vin_match.group(1)
    
    return None


def parse_finance_zone(text):
    """Parse EP, PDCO, PREF depuis la zone financière"""
    data = {
        "ep_raw": None,
        "pdco_raw": None,
        "pref_raw": None,
        "holdback_raw": None
    }
    
    # E.P.
    ep_match = re.search(r'E\.P\.?\s*(\d{7,10})', text)
    if ep_match:
        data["ep_raw"] = ep_match.group(1)
    
    # PDCO
    pdco_match = re.search(r'PDCO\s*(\d{7,10})', text)
    if pdco_match:
        data["pdco_raw"] = pdco_match.group(1)
    
    # PREF
    pref_match = re.search(r'PREF\*?\s*(\d{7,10})', text)
    if pref_match:
        data["pref_raw"] = pref_match.group(1)
    
    # Holdback (6 chiffres commençant par 0)
    holdback_match = re.search(r'\b(0[3-9]\d{4})\b', text)
    if holdback_match:
        data["holdback_raw"] = holdback_match.group(1)
    
    return data


def parse_totals_zone(text):
    """Parse subtotal et total depuis la zone totaux"""
    data = {
        "subtotal": None,
        "total": None
    }
    
    # Subtotal
    subtotal_match = re.search(r'SUB\s*TOTAL[\s\S]*?([\d,]+\.\d{2})', text, re.IGNORECASE)
    if subtotal_match:
        data["subtotal"] = float(subtotal_match.group(1).replace(',', ''))
    
    # Total
    total_match = re.search(r'TOTAL\s+DE\s+LA\s+FACTURE\s*([\d,]+\.\d{2})', text)
    if not total_match:
        total_match = re.search(r'INVOICE\s*TOTAL[\s\S]*?([\d,]+\.\d{2})', text, re.IGNORECASE)
    if total_match:
        data["total"] = float(total_match.group(1).replace(',', ''))
    
    return data


def parse_options_zone(text):
    """Parse les options depuis la zone centrale"""
    options = []
    
    # Pattern: CODE (2-5 chars) + DESCRIPTION + MONTANT (8 chiffres)
    option_pattern = re.findall(
        r'\b([A-Z0-9]{2,5})\s+([A-Z][A-Z0-9\s,\-\'/\.]{4,}?)\s+(\d{6,10}|\*|SANS)',
        text
    )
    
    invalid_codes = {'VIN', 'GST', 'TPS', 'QUE', 'INC', 'PDCO', 'PREF', 'MODEL', 'TOTAL', 'MSRP', 'SUB'}
    
    for code, desc, amount in option_pattern:
        if code.upper() in invalid_codes:
            continue
        options.append({
            "code": code.upper(),
            "description": desc.strip()[:80],
            "amount_raw": amount if amount not in ['*', 'SANS'] else "0"
        })
    
    return options


def clean_fca_price(raw_value):
    """Décode prix FCA: enlève premier 0 + 2 derniers chiffres"""
    raw_value = str(raw_value).strip()
    raw_value = re.sub(r'[^\d]', '', raw_value)
    
    if not raw_value:
        return 0
    
    if raw_value.startswith("0"):
        raw_value = raw_value[1:]
    
    if len(raw_value) >= 2:
        raw_value = raw_value[:-2]
    
    try:
        return int(raw_value)
    except:
        return 0


def process_invoice_by_zones(file_bytes):
    """
    Pipeline complet OCR par zones pour facture FCA.
    
    Returns: dict avec toutes les données extraites
    """
    result = {
        "vin": None,
        "model_code": None,
        "ep_cost": None,
        "pdco": None,
        "pref": None,
        "holdback": None,
        "subtotal": None,
        "invoice_total": None,
        "options": [],
        "parse_method": "ocr_zones",
        "zones_extracted": 0
    }
    
    try:
        # Charger l'image
        nparr = np.frombuffer(file_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            logger.error("Failed to decode image")
            return result
        
        # Redimensionner si trop grande
        max_dim = 2500
        h, w = image.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        
        # Redresser le document
        image = auto_warp_document(image)
        
        # Extraire les zones
        zones = extract_zones(image)
        
        # OCR zone VIN
        vin_text = ocr_zone(zones["vin"], psm=6)
        result["vin"] = parse_vin_zone(vin_text)
        if result["vin"]:
            result["zones_extracted"] += 1
        
        # Chercher model code dans zone VIN
        model_match = re.search(r'\b(WL[A-Z]{2}\d{2}|JT[A-Z]{2}\d{2}|DT[A-Z0-9]{2}\d{2})\b', vin_text)
        if model_match:
            result["model_code"] = model_match.group(1)
        
        # OCR zone financière
        finance_text = ocr_zone(zones["finance"], psm=6)
        finance_data = parse_finance_zone(finance_text)
        
        if finance_data["ep_raw"]:
            result["ep_cost"] = clean_fca_price(finance_data["ep_raw"])
            result["zones_extracted"] += 1
        
        if finance_data["pdco_raw"]:
            result["pdco"] = clean_fca_price(finance_data["pdco_raw"])
        
        if finance_data["pref_raw"]:
            result["pref"] = clean_fca_price(finance_data["pref_raw"])
        
        if finance_data["holdback_raw"]:
            result["holdback"] = clean_fca_price(finance_data["holdback_raw"])
        
        # OCR zone totaux
        totals_text = ocr_zone(zones["totals"], psm=6)
        totals_data = parse_totals_zone(totals_text)
        
        if totals_data["subtotal"]:
            result["subtotal"] = totals_data["subtotal"]
            result["zones_extracted"] += 1
        
        if totals_data["total"]:
            result["invoice_total"] = totals_data["total"]
        
        # OCR zone options
        options_text = ocr_zone(zones["options"], psm=6)
        options_raw = parse_options_zone(options_text)
        
        for opt in options_raw:
            result["options"].append({
                "product_code": opt["code"],
                "description": opt["description"],
                "amount": clean_fca_price(opt["amount_raw"])
            })
        
        if len(result["options"]) >= 3:
            result["zones_extracted"] += 1
        
        logger.info(f"OCR Zones: VIN={result['vin']}, EP={result['ep_cost']}, zones={result['zones_extracted']}")
        
    except Exception as e:
        logger.error(f"OCR zones pipeline error: {e}")
    
    return result
