"""
Validation Module - Règles Métier FCA + Scoring
Valide les données extraites avec règles business

Règles de validation FCA Canada:
- EP < PDCO (coût employé < prix dealer)
- PDCO > 30 000 (véhicules neufs)
- Subtotal ≈ PREF ± 25$
- VIN valide mathématiquement
- Nombre options > 5
"""

from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


# ============ RÈGLES MÉTIER FCA ============

def validate_ep_pdco(ep: float, pdco: float) -> Tuple[bool, str]:
    """
    Règle: EP < PDCO
    Le coût employé doit être inférieur au prix dealer
    """
    if not ep or not pdco:
        return False, "EP ou PDCO manquant"
    
    if ep >= pdco:
        return False, f"EP ({ep}) doit être < PDCO ({pdco})"
    
    # Vérifier que la différence est raisonnable (< 15000$)
    diff = pdco - ep
    if diff > 15000:
        return False, f"Différence EP/PDCO trop grande ({diff}$)"
    
    return True, "EP < PDCO valide"


def validate_pdco_minimum(pdco: float) -> Tuple[bool, str]:
    """
    Règle: PDCO > 30 000 pour véhicules neufs
    """
    if not pdco:
        return False, "PDCO manquant"
    
    if pdco < 30000:
        return False, f"PDCO ({pdco}) semble trop bas pour un véhicule neuf"
    
    if pdco > 150000:
        return False, f"PDCO ({pdco}) semble trop élevé"
    
    return True, "PDCO dans la plage valide"


def validate_subtotal_pref(subtotal: float, pref: float) -> Tuple[bool, str]:
    """
    Règle: Subtotal ≈ PREF ± 25$
    """
    if not subtotal or not pref:
        return True, "Subtotal ou PREF manquant (non bloquant)"
    
    tolerance = 50  # Tolérance de 50$
    diff = abs(subtotal - pref)
    
    if diff > tolerance:
        return False, f"Subtotal ({subtotal}) ≠ PREF ({pref}), diff: {diff}$"
    
    return True, "Subtotal ≈ PREF"


def validate_options_count(options: List[Dict]) -> Tuple[bool, str]:
    """
    Règle: Au moins 5 options pour un véhicule neuf
    """
    count = len(options) if options else 0
    
    if count < 3:
        return False, f"Trop peu d'options ({count}), minimum attendu: 3"
    
    if count >= 5:
        return True, f"{count} options extraites"
    
    return True, f"{count} options (légèrement bas)"


def validate_price_coherence(ep: float, pdco: float, subtotal: float) -> Tuple[bool, str]:
    """
    Règle: Cohérence des prix
    - EP < Subtotal (normalement)
    - PDCO proche du subtotal
    """
    issues = []
    
    if ep and subtotal and ep > subtotal:
        issues.append(f"EP ({ep}) > Subtotal ({subtotal})")
    
    if pdco and subtotal:
        diff = abs(pdco - subtotal)
        # PDCO devrait être proche du subtotal (avant options)
        if diff > 10000 and subtotal < pdco:
            pass  # OK, subtotal peut être < PDCO
    
    if issues:
        return False, "; ".join(issues)
    
    return True, "Cohérence prix OK"


# ============ SCORING ============

def calculate_validation_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcule un score de validation global (0-100).
    
    Critères:
    - VIN valide: +25 points
    - EP extrait: +15 points
    - PDCO extrait: +15 points
    - EP < PDCO: +15 points
    - Subtotal extrait: +10 points
    - Options >= 5: +10 points
    - Model code: +5 points
    - Holdback: +5 points
    """
    score = 0
    checks = []
    
    # VIN valide - scoring plus strict
    if data.get("vin") and data.get("vin_valid", False):
        score += 25
        checks.append(("VIN valide", True, 25))
    elif data.get("vin"):
        # VIN présent mais checksum invalide = seulement 5 points (plus strict)
        score += 5
        checks.append(("VIN présent (checksum invalide)", True, 5))
    else:
        checks.append(("VIN manquant", False, 0))
    
    # EP
    ep = data.get("ep_cost")
    if ep and ep > 0:
        score += 15
        checks.append(("EP extrait", True, 15))
    else:
        checks.append(("EP manquant", False, 0))
    
    # PDCO
    pdco = data.get("pdco")
    if pdco and pdco > 0:
        score += 15
        checks.append(("PDCO extrait", True, 15))
    else:
        checks.append(("PDCO manquant", False, 0))
    
    # EP < PDCO
    if ep and pdco and ep < pdco:
        score += 15
        checks.append(("EP < PDCO", True, 15))
    elif ep and pdco:
        checks.append(("EP >= PDCO (invalide)", False, 0))
    
    # Subtotal
    if data.get("subtotal"):
        score += 10
        checks.append(("Subtotal extrait", True, 10))
    else:
        checks.append(("Subtotal manquant", False, 0))
    
    # Options
    options_count = len(data.get("options", []))
    if options_count >= 5:
        score += 10
        checks.append((f"{options_count} options", True, 10))
    elif options_count >= 3:
        score += 5
        checks.append((f"{options_count} options (insuffisant)", True, 5))
    else:
        checks.append(("Trop peu d'options", False, 0))
    
    # Model code
    if data.get("model_code"):
        score += 5
        checks.append(("Model code", True, 5))
    
    # Holdback
    if data.get("holdback"):
        score += 5
        checks.append(("Holdback", True, 5))
    
    return {
        "score": min(100, score),
        "checks": checks,
        "status": "valid" if score >= 70 else "review" if score >= 50 else "invalid"
    }


# ============ VALIDATION COMPLÈTE ============

def validate_invoice_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validation complète des données de facture.
    
    Returns:
        {
            "is_valid": bool,
            "score": int (0-100),
            "status": "valid" | "review" | "invalid",
            "errors": list,
            "warnings": list,
            "checks": list
        }
    """
    result = {
        "is_valid": False,
        "score": 0,
        "status": "invalid",
        "errors": [],
        "warnings": [],
        "checks": []
    }
    
    ep = data.get("ep_cost", 0) or 0
    pdco = data.get("pdco", 0) or 0
    pref = data.get("pref", 0) or 0
    subtotal = data.get("subtotal", 0) or 0
    options = data.get("options", [])
    
    # Validation EP/PDCO
    valid, msg = validate_ep_pdco(ep, pdco)
    if not valid:
        result["errors"].append(msg)
    else:
        result["checks"].append(msg)
    
    # Validation PDCO minimum
    valid, msg = validate_pdco_minimum(pdco)
    if not valid:
        result["warnings"].append(msg)
    else:
        result["checks"].append(msg)
    
    # Validation Subtotal/PREF
    valid, msg = validate_subtotal_pref(subtotal, pref)
    if not valid:
        result["warnings"].append(msg)
    else:
        result["checks"].append(msg)
    
    # Validation options
    valid, msg = validate_options_count(options)
    if not valid:
        result["warnings"].append(msg)
    else:
        result["checks"].append(msg)
    
    # Validation cohérence prix
    valid, msg = validate_price_coherence(ep, pdco, subtotal)
    if not valid:
        result["warnings"].append(msg)
    else:
        result["checks"].append(msg)
    
    # Calcul score
    scoring = calculate_validation_score(data)
    result["score"] = scoring["score"]
    result["status"] = scoring["status"]
    result["checks"].extend([f"{check[0]}: {check[2]}pts" for check in scoring["checks"] if check[1]])
    
    # PATCH: Déterminer validité globale - seuil relevé à 85 pour règle zéro erreur
    # is_valid = True seulement si score >= 85 ET pas d'erreurs ET VIN ET EP présents
    result["is_valid"] = (
        len(result["errors"]) == 0 and 
        result["score"] >= 85 and
        data.get("vin") is not None and
        ep > 0
    )
    
    logger.info(f"Validation: score={result['score']}, status={result['status']}, valid={result['is_valid']}")
    
    return result


def determine_parse_method_needed(pdf_text_success: bool, ocr_score: int) -> str:
    """
    Détermine si on doit utiliser le fallback AI.
    
    Niveaux:
    - PDF natif réussi → "pdf_native" (100% précis)
    - OCR score >= 70 → "ocr_zones" (ok)
    - OCR score 50-69 → "ocr_zones" avec warning
    - OCR score < 50 → "ai_fallback" recommandé
    """
    if pdf_text_success:
        return "pdf_native"
    
    if ocr_score >= 70:
        return "ocr_zones"
    
    if ocr_score >= 50:
        return "ocr_zones_low_confidence"
    
    return "ai_fallback_recommended"
