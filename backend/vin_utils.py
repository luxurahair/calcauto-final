"""
VIN Utilities - Validation et Auto-correction Industrielles
Module de validation VIN avec check-digit et correction automatique

Caractéristiques:
- Validation check-digit ISO 3779
- Auto-correction erreurs OCR courantes
- Décodage année/marque/modèle
"""

import re
from typing import Dict, Optional, Tuple, List
import logging

logger = logging.getLogger(__name__)


# ============ VIN CHECK DIGIT ============

# Valeurs de translittération VIN (ISO 3779)
VIN_TRANSLITERATION = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
    'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9
}

# Poids par position (1-17)
VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def calculate_check_digit(vin: str) -> str:
    """
    Calcule le check digit d'un VIN (position 9).
    
    Formule ISO 3779:
    1. Translittérer chaque caractère en valeur numérique
    2. Multiplier par le poids de position
    3. Sommer et modulo 11
    4. Si résultat = 10, check digit = 'X'
    """
    if len(vin) != 17:
        return ""
    
    vin = vin.upper()
    total = 0
    
    for i, char in enumerate(vin):
        if i == 8:  # Position 9 (index 8) est le check digit lui-même
            continue
        
        value = VIN_TRANSLITERATION.get(char, 0)
        total += value * VIN_WEIGHTS[i]
    
    remainder = total % 11
    return 'X' if remainder == 10 else str(remainder)


def validate_vin_checksum(vin: str) -> bool:
    """
    Vérifie si le check digit du VIN est valide.
    """
    if not vin or len(vin) != 17:
        return False
    
    vin = vin.upper()
    expected_check = calculate_check_digit(vin)
    actual_check = vin[8]
    
    return actual_check == expected_check


# ============ AUTO-CORRECTION OCR ============

# Erreurs OCR courantes - caractères qui n'existent pas dans un VIN
OCR_CORRECTIONS = {
    'O': '0',  # O → 0
    'I': '1',  # I → 1
    'Q': '0',  # Q → 0 (Q n'existe pas dans VIN)
    'o': '0',
    'l': '1',  # l minuscule → 1
    'i': '1',
    'q': '0',
}

# Caractères invalides dans un VIN (I, O, Q)
INVALID_VIN_CHARS = set('IOQ')

# NOUVEAU: Paires de confusion OCR fréquentes (source → destinations possibles)
# Utilisé pour correction intelligente quand le checksum échoue
OCR_CONFUSION_PAIRS = {
    # Chiffres similaires
    '8': ['9', 'B', '6'],      # 8 souvent confondu avec 9, B, 6
    '9': ['8', 'G', '0', '5'], # 9 souvent confondu avec 8, G, 0, 5
    '6': ['8', 'G', 'B'],      # 6 souvent confondu avec 8, G
    '0': ['8', 'D', 'G'],      # 0 souvent confondu avec 8, D
    '5': ['S', '6', '9'],      # 5 souvent confondu avec S, 9
    '1': ['7', 'L'],           # 1 souvent confondu avec 7, L
    '2': ['Z'],                # 2 souvent confondu avec Z
    '7': ['1', 'T'],           # 7 souvent confondu avec 1
    # Lettres similaires
    'S': ['5', '8'],           # S souvent confondu avec 5, 8
    'B': ['8', '6'],           # B souvent confondu avec 8
    'G': ['6', '9', 'C'],      # G souvent confondu avec 6, 9
    'Z': ['2'],                # Z souvent confondu avec 2
    'D': ['0'],                # D souvent confondu avec 0
    'L': ['1'],                # L souvent confondu avec 1
    'T': ['7'],                # T souvent confondu avec 7
    'C': ['G'],                # C souvent confondu avec G
    'X': ['K'],                # X souvent confondu avec K (erreur GPT fréquente)
    'K': ['X'],                # K souvent confondu avec X
}


def correct_vin_ocr_errors(vin: str) -> str:
    """
    Corrige les erreurs OCR courantes dans un VIN.
    - O → 0
    - I → 1
    - Q → 0
    - Correction spécifique Jeep: 1C4RJX → 1C4RJK (X→K en position 5)
    """
    if not vin:
        return vin
    
    corrected = []
    for char in vin.upper():
        if char in OCR_CORRECTIONS:
            corrected.append(OCR_CORRECTIONS[char])
        else:
            corrected.append(char)
    
    result = ''.join(corrected)
    
    # Correction spécifique Jeep: position 5 devrait être K, pas X
    # Les VIN Jeep commencent par 1C4RJK, pas 1C4RJX
    if result.startswith('1C4RJX'):
        result = '1C4RJK' + result[6:]
        logger.info(f"VIN Jeep corrigé: X→K en position 5")
    
    # Correction position 10 (année): doit être une lettre (R, S, T), pas un chiffre
    # Si position 10 est 5 ou 8, c'est probablement S (2025)
    if len(result) >= 10:
        pos10 = result[9]
        if pos10 in '58':
            result = result[:9] + 'S' + result[10:]
            logger.info(f"VIN année corrigé: {pos10}→S en position 10 (2025)")
        elif pos10 == '4':
            result = result[:9] + 'R' + result[10:]
            logger.info(f"VIN année corrigé: {pos10}→R en position 10 (2024)")
    
    # Correction spécifique FCA: "88" en positions 9-10 devrait être "S8" (année 2025 + usine 8)
    # Format VIN FCA: XXXXXXXXX-S8-XXXXXX où S=année 2025, 8=usine Windsor
    if len(result) >= 11 and result[9:11] == '88':
        result = result[:9] + 'S8' + result[11:]
        logger.info(f"VIN FCA corrigé: 88→S8 en positions 10-11 (2025 + usine)")
    elif len(result) >= 11 and result[9:11] == '58':
        result = result[:9] + 'S8' + result[11:]
        logger.info(f"VIN FCA corrigé: 58→S8 en positions 10-11 (2025 + usine)")
    elif len(result) >= 11 and result[9:11] == '55':
        result = result[:9] + 'S5' + result[11:]
        logger.info(f"VIN FCA corrigé: 55→S5 en positions 10-11")
    
    return result


def try_fix_check_digit(vin: str) -> Tuple[str, bool]:
    """
    Tente de corriger le VIN si le check digit est invalide.
    
    Stratégie:
    1. Corriger les erreurs OCR courantes
    2. Si toujours invalide, essayer de remplacer position 9 par le bon check digit
    
    Returns: (VIN corrigé, succès)
    """
    if len(vin) != 17:
        return vin, False
    
    vin = vin.upper()
    
    # Étape 1: Corriger erreurs OCR
    corrected_vin = correct_vin_ocr_errors(vin)
    
    if validate_vin_checksum(corrected_vin):
        return corrected_vin, True
    
    # Étape 2: Recalculer et remplacer le check digit
    correct_check = calculate_check_digit(corrected_vin)
    if correct_check:
        fixed_vin = corrected_vin[:8] + correct_check + corrected_vin[9:]
        if validate_vin_checksum(fixed_vin):
            logger.info(f"VIN check digit corrected: {corrected_vin} → {fixed_vin}")
            return fixed_vin, True
    
    return corrected_vin, False


def smart_vin_correction(vin: str) -> Dict[str, any]:
    """
    Correction intelligente du VIN avec plusieurs stratégies.
    
    Stratégies (dans l'ordre):
    1. Vérifier si déjà valide
    2. Corrections OCR simples (I→1, O→0, Q→0)
    3. Correction single-char avec paires de confusion OCR
    4. Correction double-char (2 positions problématiques)
    5. Si toujours invalide → marquer pour révision manuelle
    
    Returns:
        {
            "original": VIN original
            "corrected": VIN corrigé
            "is_valid": Bool
            "correction_applied": Bool
            "correction_type": str
        }
    """
    result = {
        "original": vin,
        "corrected": vin,
        "is_valid": False,
        "correction_applied": False,
        "correction_type": None
    }
    
    if not vin or len(vin) != 17:
        return result
    
    vin = vin.upper()
    result["original"] = vin
    
    # Vérifier si déjà valide
    if validate_vin_checksum(vin):
        result["corrected"] = vin
        result["is_valid"] = True
        return result
    
    # Stratégie 1: Corrections OCR simples (caractères invalides dans VIN)
    corrected = correct_vin_ocr_errors(vin)
    if validate_vin_checksum(corrected):
        result["corrected"] = corrected
        result["is_valid"] = True
        result["correction_applied"] = True
        result["correction_type"] = "ocr_simple"
        return result
    
    # Stratégie 2: Correction single-char avec OCR_CONFUSION_PAIRS
    # Essayer de remplacer un caractère à la fois
    for pos in range(17):
        if pos == 8:  # Skip check digit position
            continue
        
        current_char = corrected[pos]
        
        # Obtenir les alternatives possibles pour ce caractère
        alternatives = OCR_CONFUSION_PAIRS.get(current_char, [])
        
        for alt_char in alternatives:
            if alt_char in INVALID_VIN_CHARS:
                continue  # Ignorer I, O, Q
            
            test_vin = corrected[:pos] + alt_char + corrected[pos+1:]
            if validate_vin_checksum(test_vin):
                result["corrected"] = test_vin
                result["is_valid"] = True
                result["correction_applied"] = True
                result["correction_type"] = f"single_char_pos_{pos}_{current_char}→{alt_char}"
                logger.info(f"VIN corrigé par single-char: position {pos}, {current_char}→{alt_char}")
                return result
    
    # Stratégie 3: Correction double-char (2 erreurs simultanées)
    # Ceci couvre le cas typique: 8→9 et S→5 en même temps
    # Limiter aux positions connues pour être problématiques (sauf position 8)
    problem_positions = [i for i in range(17) if i != 8]
    
    for pos1 in problem_positions:
        char1 = corrected[pos1]
        alts1 = OCR_CONFUSION_PAIRS.get(char1, [])
        
        for alt1 in alts1:
            if alt1 in INVALID_VIN_CHARS:
                continue
            
            # Premier remplacement
            test_vin1 = corrected[:pos1] + alt1 + corrected[pos1+1:]
            
            # Vérifier si déjà valide
            if validate_vin_checksum(test_vin1):
                result["corrected"] = test_vin1
                result["is_valid"] = True
                result["correction_applied"] = True
                result["correction_type"] = f"double_char_pos_{pos1}_{char1}→{alt1}"
                logger.info(f"VIN corrigé par double-char (1er): position {pos1}, {char1}→{alt1}")
                return result
            
            # Essayer une deuxième correction
            for pos2 in problem_positions:
                if pos2 <= pos1:
                    continue  # Éviter les doublons
                
                char2 = test_vin1[pos2]
                alts2 = OCR_CONFUSION_PAIRS.get(char2, [])
                
                for alt2 in alts2:
                    if alt2 in INVALID_VIN_CHARS:
                        continue
                    
                    test_vin2 = test_vin1[:pos2] + alt2 + test_vin1[pos2+1:]
                    if validate_vin_checksum(test_vin2):
                        result["corrected"] = test_vin2
                        result["is_valid"] = True
                        result["correction_applied"] = True
                        result["correction_type"] = f"double_char_pos_{pos1}_{pos2}"
                        logger.info(f"VIN corrigé par double-char: {pos1}:{char1}→{alt1}, {pos2}:{char2}→{alt2}")
                        return result
    
    # STRATÉGIE 4: NE JAMAIS FORCER LE CHECK DIGIT
    # Si le VIN est toujours invalide après corrections → révision manuelle requise
    result["corrected"] = corrected
    result["is_valid"] = False
    result["correction_applied"] = False
    result["correction_type"] = "checksum_invalid_review_required"
    logger.warning(f"VIN checksum invalide après toutes corrections, révision requise: {vin}")
    
    return result


# ============ DÉCODAGE VIN ============

# Codes année VIN (position 10)
YEAR_CODES = {
    'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 'E': 2014,
    'F': 2015, 'G': 2016, 'H': 2017, 'J': 2018, 'K': 2019,
    'L': 2020, 'M': 2021, 'N': 2022, 'P': 2023, 'R': 2024,
    'S': 2025, 'T': 2026, 'V': 2027, 'W': 2028, 'X': 2029,
    'Y': 2030, '1': 2031, '2': 2032, '3': 2033, '4': 2034,
    '5': 2035, '6': 2036, '7': 2037, '8': 2038, '9': 2039
}

# WMI → Marque (positions 1-3)
WMI_BRANDS = {
    "1C4": "Jeep",
    "1C6": "Ram",
    "1J4": "Jeep",
    "1J8": "Jeep",
    "2C3": "Chrysler",
    "3C4": "Chrysler",
    "3C6": "Ram",
    "3D4": "Dodge",
    "3D7": "Ram",
    "1B3": "Dodge",
    "2B3": "Dodge",
    "2D7": "Ram"
}


def decode_vin_year(vin: str) -> Optional[int]:
    """Décode l'année depuis le VIN (position 10)"""
    if not vin or len(vin) < 10:
        return None
    
    year_char = vin[9].upper()
    return YEAR_CODES.get(year_char)


def is_year_plausible(year: int) -> bool:
    """Vérifie si l'année du VIN est plausible (véhicules actuels)"""
    from datetime import datetime
    current_year = datetime.now().year
    # Plausible: année actuelle -5 à +2 (véhicules neufs et récents)
    return (current_year - 5) <= year <= (current_year + 2)


def decode_vin_brand(vin: str) -> Optional[str]:
    """Décode la marque depuis le VIN (positions 1-3)"""
    if not vin or len(vin) < 3:
        return None
    
    # Cas spécial: Jeep Gladiator
    if vin.upper().startswith("1C6PJ"):
        return "Jeep"
    
    wmi = vin[0:3].upper()
    return WMI_BRANDS.get(wmi)


def decode_vin_info(vin: str) -> Dict[str, any]:
    """
    Décode les informations complètes du VIN.
    
    Returns:
        {
            "vin": VIN original
            "year": Année
            "brand": Marque
            "is_valid": Checksum valide
        }
    """
    return {
        "vin": vin,
        "year": decode_vin_year(vin),
        "brand": decode_vin_brand(vin),
        "is_valid": validate_vin_checksum(vin) if vin else False
    }


# ============ VALIDATION COMPLÈTE ============

def validate_and_correct_vin(vin: str) -> Dict[str, any]:
    """
    Validation et correction complète du VIN.
    
    Pipeline:
    1. Nettoyage
    2. Correction OCR
    3. Validation checksum
    4. Décodage info
    
    Returns:
        {
            "original": VIN original
            "corrected": VIN corrigé
            "is_valid": Bool
            "was_corrected": Bool
            "correction_type": str
            "year": Année décodée
            "brand": Marque décodée
            "confidence": 0-100
        }
    """
    result = {
        "original": vin,
        "corrected": None,
        "is_valid": False,
        "was_corrected": False,
        "correction_type": None,
        "year": None,
        "brand": None,
        "confidence": 0
    }
    
    if not vin:
        return result
    
    # Nettoyage
    vin_clean = re.sub(r'[^A-HJ-NPR-Z0-9]', '', vin.upper())
    
    if len(vin_clean) != 17:
        return result
    
    # Correction intelligente
    correction = smart_vin_correction(vin_clean)
    
    result["corrected"] = correction["corrected"]
    result["is_valid"] = correction["is_valid"]
    result["was_corrected"] = correction["correction_applied"]
    result["correction_type"] = correction["correction_type"]
    
    # Décodage
    final_vin = correction["corrected"]
    result["year"] = decode_vin_year(final_vin)
    result["brand"] = decode_vin_brand(final_vin)
    
    # Vérification année plausible - si l'année est impossible (ex: 2038), essayer de corriger position 10
    if result["year"] and not is_year_plausible(result["year"]):
        logger.warning(f"Année {result['year']} non plausible pour VIN {final_vin}")
        
        # Essayer de remplacer position 10 par des alternatives probables
        # 5 ou 8 sont souvent confondus avec S (2025)
        pos10 = final_vin[9]
        alternatives = {'5': 'S', '8': 'S', '3': 'R', '4': 'R'}
        
        if pos10 in alternatives:
            new_pos10 = alternatives[pos10]
            test_vin = final_vin[:9] + new_pos10 + final_vin[10:]
            
            # Vérifier si le nouveau VIN est valide
            if validate_vin_checksum(test_vin):
                new_year = decode_vin_year(test_vin)
                if new_year and is_year_plausible(new_year):
                    logger.info(f"Année corrigée: {pos10}→{new_pos10}, {result['year']}→{new_year}")
                    result["corrected"] = test_vin
                    result["year"] = new_year
                    result["was_corrected"] = True
                    result["correction_type"] = f"year_fix_{pos10}→{new_pos10}"
    
    # Calcul confiance
    confidence = 50  # Base
    if result["is_valid"]:
        confidence += 30
    if result["year"] and is_year_plausible(result["year"]):
        confidence += 10
    elif result["year"]:
        confidence -= 10  # Pénalité si année non plausible
    if result["brand"]:
        confidence += 10
    if result["was_corrected"]:
        confidence -= 10  # Pénalité si correction appliquée
    
    result["confidence"] = min(100, max(0, confidence))
    
    return result
