"""
Parser Structuré FCA Canada - Extraction Regex
Parse le texte OCR en données structurées

Appliqué après le pipeline OCR par zones.
"""

import re
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


def clean_fca_price(raw_value: str) -> int:
    """
    Décode le format prix FCA Canada:
    - Enlever le premier 0
    - Enlever les deux derniers chiffres
    
    Exemple: 05662000 → 5662000 → 56620 → 56620$
    """
    raw_value = str(raw_value).strip()
    raw_value = re.sub(r'[^\d]', '', raw_value)
    
    if not raw_value or len(raw_value) < 4:
        return 0
    
    # Enlever le premier 0
    if raw_value.startswith("0"):
        raw_value = raw_value[1:]
    
    # Enlever les deux derniers chiffres
    if len(raw_value) >= 2:
        raw_value = raw_value[:-2]
    
    try:
        return int(raw_value)
    except:
        return 0


def parse_vin(text: str) -> Optional[str]:
    """
    Extrait le VIN depuis le texte.
    
    Formats supportés:
    - VIN standard 17 caractères
    - VIN FCA avec tirets: XXXXX-XX-XXXXXX (format 5-2-X)
    - VIN avec erreurs OCR courantes (I/1, O/0, K/J, S/5, B/8)
    - VIN partiellement espacé par l'OCR
    """
    text = text.upper()
    
    # Pattern VIN FCA spécifique (1C4R..., 2C4R..., 3C4R..., 3C6UR...)
    # Tolère K au lieu de J (erreur OCR courante)
    vin_fca_patterns = [
        r'[123]C4R[IJKL][JK]AG[0-9][-\s]*[A-Z0-9]{2}[-\s]*[A-Z0-9]{6}',  # Jeep (1C4R)
        r'[123]C6[A-Z]{2}[A-Z0-9]{2}[-\s]*[A-Z0-9]{2}[-\s]*[A-Z0-9]{6}',  # Ram HD (3C6UR)
        r'[123]C[0-9A-Z]{4}[A-Z0-9]{2}[-\s]*[A-Z0-9]{2}[-\s]*[A-Z0-9]{6}', # FCA générique
    ]
    
    for pattern in vin_fca_patterns:
        vin_match = re.search(pattern, text)
        if vin_match:
            vin = re.sub(r'[-\s]', '', vin_match.group())
            # Corriger K→J si nécessaire (position 5 devrait être J pour Jeep)
            if len(vin) >= 5 and vin[4] == 'K' and vin.startswith('1C4R'):
                vin = vin[:4] + 'J' + vin[5:]
            if len(vin) >= 17:
                return vin[:17]
    
    # VIN avec tirets FCA générique (5-2-X chars)
    vin_dash_match = re.search(
        r'([0-9A-HJ-NPR-Z]{5,9})[-\s]([A-HJ-NPR-Z0-9]{2})[-\s]([A-HJ-NPR-Z0-9]{6,10})',
        text
    )
    if vin_dash_match:
        vin = vin_dash_match.group(1) + vin_dash_match.group(2) + vin_dash_match.group(3)
        if len(vin) >= 17:
            return vin[:17]
    
    # VIN standard 17 caractères (sans tirets)
    vin_match = re.search(r'\b([0-9A-HJ-NPR-Z]{17})\b', text)
    if vin_match:
        return vin_match.group(1)
    
    # FALLBACK: VIN avec espaces/erreurs OCR - Recherche aggressive
    # Chercher patterns commençant par 1C, 2C, 3C (FCA/Stellantis)
    aggressive_patterns = [
        r'([123]C[0-9A-Z\s]{15,20})',  # FCA avec espaces possibles
        r'([WJKM][A-Z0-9\s]{15,20})',  # Autres patterns VIN
    ]
    for pattern in aggressive_patterns:
        match = re.search(pattern, text)
        if match:
            # Nettoyer: enlever espaces, garder alphanumériques
            candidate = re.sub(r'[\s\-]', '', match.group(1))
            candidate = ''.join(c for c in candidate if c.isalnum())
            # Corriger erreurs OCR courantes
            candidate = candidate.replace('O', '0').replace('I', '1')
            if len(candidate) >= 17:
                vin = candidate[:17]
                # Valider que c'est un VIN vraisemblable (pas de I, O, Q)
                if not re.search(r'[IOQ]', vin):
                    return vin
    
    return None


def parse_model_code(text: str, master_codes: dict = None) -> Optional[str]:
    """
    Extrait le code modèle FCA avec validation contre la base de données.
    
    Stratégie:
    1. D'abord, chercher les codes connus avec patterns regex
    2. Ensuite, chercher TOUS les candidats de 6 caractères alphanumériques
    3. Valider chaque candidat contre la base master_codes
    
    Patterns connus:
    - WL**** (Grand Cherokee), WS**** (Wagoneer)
    - JT**** (Gladiator), JL**** (Wrangler)
    - DT**** (Ram 1500), DJ**** (Ram 2500), D2*/D3* (Ram 3500)
    - MP**** (Compass), KM**** (Cherokee)
    - WD**** (Durango), LB**** (Charger)
    - RU**** (Pacifica), VF**** (ProMaster)
    - GG**** (Hornet), FG**** (Fiat), EJ**** (Jeep EV)
    - DP**** (Ram 4500/5500), DD**** (Ram 3500 Chassis)
    """
    text_upper = text.upper()
    
    # Patterns prioritaires (les plus courants d'abord)
    patterns = [
        # Ram Heavy Duty (les plus courants)
        r'\b(DJ[0-9][A-Z][0-9]{2})\b',  # Ram 2500 (DJ7L92, DJ7H91)
        r'\b(D[23][0-9][A-Z][0-9]{2})\b',  # Ram 3500 (D23L91, D28H92)
        r'\b(DD[0-9][A-Z][0-9]{2})\b',  # Ram 3500 Chassis
        r'\b(DP[0-9][A-Z][0-9]{2})\b',  # Ram 4500/5500
        
        # Ram 1500
        r'\b(DT[0-9][A-Z][0-9]{2})\b',  # Ram 1500 (DT6H98, DT6L91)
        
        # Jeep SUVs
        r'\b(WL[A-Z]{2}[0-9]{2})\b',  # Grand Cherokee
        r'\b(WS[A-Z]{2}[0-9]{2})\b',  # Wagoneer
        r'\b(KM[A-Z]{2}[0-9]{2})\b',  # Cherokee new
        r'\b(MP[A-Z]{2}[0-9]{2})\b',  # Compass
        
        # Jeep Wrangler/Gladiator
        r'\b(JL[A-Z]{2}[0-9]{2})\b',  # Wrangler
        r'\b(JT[A-Z]{2}[0-9]{2})\b',  # Gladiator
        r'\b(EJ[A-Z]{2}[0-9]{2})\b',  # Jeep EV
        
        # Dodge
        r'\b(WD[A-Z]{2}[0-9]{2})\b',  # Durango
        r'\b(LB[A-Z]{2}[0-9]{2})\b',  # Charger
        r'\b(GG[A-Z]{2}[0-9]{2})\b',  # Hornet
        
        # Chrysler
        r'\b(RU[A-Z]{2}[0-9]{2})\b',  # Pacifica
        
        # Ram Commercial
        r'\b(VF[0-9A-Z]{2}[0-9]{2})\b',  # ProMaster
        
        # Fiat
        r'\b(FG[A-Z]{2}[0-9]{2})\b',  # Fiat 500
    ]
    
    # Étape 1: Chercher avec les patterns connus
    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            code = match.group(1)
            # Si on a la base master, vérifier que le code existe
            if master_codes and code in master_codes:
                return code
            elif not master_codes:
                # Pas de base master, retourner quand même
                return code
    
    # Étape 2: Si on a la base master, chercher TOUS les codes de 6 caractères
    # et vérifier lesquels sont dans la base
    if master_codes:
        # Trouver tous les mots de 6 caractères alphanumériques
        all_6char = re.findall(r'\b([A-Z0-9]{6})\b', text_upper)
        for candidate in all_6char:
            if candidate in master_codes:
                return candidate
    
    # Étape 3: Fallback - pattern générique pour 6 caractères (sans validation)
    generic_match = re.search(r'\b([A-Z]{2}[A-Z0-9]{2}[0-9]{2})\b', text_upper)
    if generic_match:
        return generic_match.group(1)
    
    return None


def parse_trim_from_description(text: str) -> Optional[str]:
    """
    Extrait le trim depuis la ligne DESCRIPTION de la facture FCA.
    
    Trims connus Stellantis (extrait du guide SCI Lease Corp):
    - FIAT: Giorgio Armani, La Prima, Red
    - Chrysler: SXT, Select, Limited, Limited S PHEV, Pinnacle, Pinnacle PHEV
    - Dodge: R/T, R/T Plus, Scat Pack, Scat Pack Plus, GT, GT Plus, GT Hemi, SXT, SRT Hellcat
    - Jeep: Sport, Sport S, North, Altitude, Limited, Trailhawk, Trailhawk Elite, Laredo, Laredo Altitude, 
            Overland, Summit, Summit Reserve, Rubicon, Rubicon X, Sahara, Willys, Mojave, Mojave X,
            Nighthawk, Base, Upland, Series I/II/III, Moab 392
    - Ram: Express, Black Express, Tradesman, Big Horn, Bighorn, Sport, Rebel, RHO, Laramie, 
           Limited, Limited Longhorn, Longhorn, Powerwagon, Tungsten, Warlock
    """
    # Liste des trims connus (ordre de priorité - du plus spécifique au moins)
    known_trims = [
        # Trims spécifiques longs d'abord
        "Limited Reserve", "Summit Reserve", "Limited Longhorn", "Laredo Altitude",
        "Limited Altitude", "Summit Obsidian", "Series II Obsidian", "Series II Carbide",
        "GT Hemi Plus", "GT Hemi Premium", "SRT Hellcat Hammerhead", "SRT Hellcat Silver Bullet",
        "Scat Pack Plus", "R/T Plus", "R/T 20th Anniv", "Trailhawk Elite",
        "Limited S PHEV", "Pinnacle PHEV", "Select PHEV", "Moab 392",
        "Rubicon X", "Mojave X", "Sport S", "Willys 41", "Black Express",
        
        # Trims Ram
        "Big Horn", "Bighorn", "Laramie", "Rebel", "Tradesman", "Express",
        "Powerwagon", "Power Wagon", "Tungsten", "Warlock", "Longhorn", "RHO",
        
        # Trims Jeep
        "Limited", "Trailhawk", "Altitude", "Summit", "Overland",
        "Laredo", "North", "Sport", "Sahara", "Rubicon", "Willys", "Mojave", "Nighthawk",
        "Upland", "Series III", "Series II", "Series I", "Base",
        
        # Trims Dodge
        "SRT Hellcat", "Scat Pack", "R/T", "GT Plus", "GT",
        
        # Trims Chrysler/Fiat
        "Pinnacle", "Select", "SXT",
        "Giorgio Armani", "La Prima", "Red"
    ]
    
    # Chercher dans le texte
    for trim in known_trims:
        # Chercher le trim dans le texte (insensible à la casse)
        pattern = rf'\b{re.escape(trim)}\b'
        if re.search(pattern, text, re.IGNORECASE):
            return trim
    
    return None


def parse_model_from_description(text: str) -> Optional[str]:
    """
    Extrait le modèle depuis la ligne DESCRIPTION de la facture FCA.
    
    Patterns: "Ram 1500", "Ram 2500", "Ram 3500", "Grand Cherokee", etc.
    """
    # Patterns pour les modèles Ram avec numéro
    ram_patterns = [
        (r'\bRam\s*3500\b', 'Ram 3500'),
        (r'\bRam\s*2500\b', 'Ram 2500'),
        (r'\bRam\s*1500\b', 'Ram 1500'),
        (r'\b3500\b.*\bRam\b', 'Ram 3500'),
        (r'\b2500\b.*\bRam\b', 'Ram 2500'),
        (r'\b1500\b.*\bRam\b', 'Ram 1500'),
    ]
    
    for pattern, model in ram_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return model
    
    # Patterns pour autres modèles
    model_patterns = [
        (r'\bGrand\s*Cherokee\s*L\b', 'Grand Cherokee L'),
        (r'\bGrand\s*Cherokee\b', 'Grand Cherokee'),
        (r'\bCompass\b', 'Compass'),
        (r'\bWrangler\b', 'Wrangler'),
        (r'\bGladiator\b', 'Gladiator'),
        (r'\bCherokee\b', 'Cherokee'),
        (r'\bDurango\b', 'Durango'),
        (r'\bCharger\b', 'Charger'),
        (r'\bChallenger\b', 'Challenger'),
        (r'\bPacifica\b', 'Pacifica'),
        (r'\bHornet\b', 'Hornet'),
        (r'\bProMaster\b', 'ProMaster'),
    ]
    
    for pattern, model in model_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return model
    
    return None


def parse_financial_data(text: str) -> Dict[str, Optional[int]]:
    """
    Extrait EP, PDCO, PREF, Holdback depuis le texte.
    Amélioré pour supporter les variations de format Google Vision OCR.
    """
    data = {
        "ep_cost": None,
        "pdco": None,
        "pref": None,
        "holdback": None
    }
    
    # Normaliser le texte (remplacer les séparateurs courants)
    normalized = text.upper()
    
    # E.P. (Employee Price / Coût réel) - Patterns améliorés
    ep_patterns = [
        r"E\.P\.?\s*(\d{7,10})",      # E.P. ou E.P suivi de chiffres
        r"E\.?P\.?\s*(\d{7,10})",     # EP. ou E.P ou EP
        r"EP\s*(\d{7,10})",           # EP sans point
        r"\bEP[\.\s]*(\d{7,10})",     # EP avec . ou espace optionnel
    ]
    for pattern in ep_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            data["ep_cost"] = clean_fca_price(match.group(1))
            break
    
    # PDCO (Prix Dealer) - Patterns améliorés
    # Note: Certaines factures utilisent "GKRP" au lieu de "PDCO"
    pdco_patterns = [
        r"PDCO\s*(\d{7,10})",         # PDCO standard
        r"PDC0\s*(\d{7,10})",         # PDC0 (OCR confusion O/0)
        r"P\.?D\.?C\.?O\.?\s*(\d{7,10})",  # Avec points
        r"\bPDCO?(\d{7,10})",         # PDCO collé aux chiffres
        r"GKRP\s*(\d{7,10})",         # GKRP (alias utilisé sur certaines factures FCA)
        r"G\.?K\.?R\.?P\.?\s*(\d{7,10})",  # GKRP avec points
    ]
    for pattern in pdco_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            data["pdco"] = clean_fca_price(match.group(1))
            break
    
    # PREF (Prix de référence)
    pref_patterns = [
        r"PREF\*?\s*(\d{7,10})",
        r"P\.?R\.?E\.?F\.?\*?\s*(\d{7,10})",
        r"\bPREF\*?(\d{7,10})",       # PREF collé aux chiffres
    ]
    for pattern in pref_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            data["pref"] = clean_fca_price(match.group(1))
            break
    
    # ===== HOLDBACK: Format FCA spécial =====
    # Le holdback apparaît en bas à gauche de la facture, dans la même colonne que les codes
    # Format: 0XXXXX0 ou 0XXXXX00 où XXXXX est le montant
    # Exemple: 070000 = $700.00 (enlever le premier 0 et les deux derniers 0)
    # Exemple: 0280000 = $2800.00
    
    holdback_patterns = [
        # Format principal: 0XXXXX00 en bas de la colonne des codes (6-7 chiffres commençant par 0)
        r'\n\s*(0\d{5,6})\s*(?:GVW|KG|$|\n)',
        # Après PREF sur la même ligne ou ligne suivante
        r'PREF[*\s]*\d{7,9}\s*\n?\s*(0\d{5,6})\b',
        # Seul sur une ligne (format holdback FCA)
        r'^\s*(0\d{5}0{1,2})\s*$',
        # Fallback: chercher un nombre 0XXXXX près de GVW
        r'(0\d{5,6})\s*GVW',
    ]
    
    for pattern in holdback_patterns:
        holdback_match = re.search(pattern, normalized, re.IGNORECASE | re.MULTILINE)
        if holdback_match:
            raw_holdback = holdback_match.group(1)
            # Décoder le format FCA: enlever le premier 0 et les deux derniers 0
            # 070000 → 700.00, 0280000 → 2800.00
            if raw_holdback.startswith('0') and len(raw_holdback) >= 6:
                # Enlever le premier caractère (0) et les deux derniers (00)
                middle = raw_holdback[1:-2]
                try:
                    holdback_value = float(middle)
                    data["holdback"] = holdback_value
                    break
                except:
                    pass
    
    return data


def parse_totals(text: str) -> Dict[str, Optional[float]]:
    """
    Extrait subtotal et total depuis le texte.
    """
    data = {
        "subtotal": None,
        "invoice_total": None
    }
    
    # Subtotal patterns
    subtotal_patterns = [
        r"SUB\s*TOTAL\s*EXCLUDING\s*TAXES.*?([\d,]+\.\d{2})",
        r"SOMME\s*PARTIELLE\s*SANS\s*TAXES.*?([\d,]+\.\d{2})",
        r"SUB\s*TOTAL.*?([\d,]+\.\d{2})"
    ]
    for pattern in subtotal_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                data["subtotal"] = float(match.group(1).replace(',', ''))
            except:
                pass
            break
    
    # Total patterns
    total_patterns = [
        r"TOTAL\s+DE\s+LA\s+FACTURE\s*([\d,]+\.\d{2})",
        r"INVOICE\s*TOTAL.*?([\d,]+\.\d{2})",
        r"TOTAL\s*:?\s*([\d,]+\.\d{2})"
    ]
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                data["invoice_total"] = float(match.group(1).replace(',', ''))
            except:
                pass
            break
    
    return data


# =====================================
# CATÉGORIES FCA POUR DÉDUPLICATION
# =====================================

CATEGORY_GROUPS = {
    "transmission": {"DFT", "DFW", "DFM", "DFD", "DFL", "DFH", "DFR", "DC1"},
    "engine": {"ERB", "ERC", "ETM", "ETK", "EZH", "ESG", "EFC", "EC7"},
    "color": {"PXJ", "PW7", "PAU", "PBF", "PSC", "PX8", "PWL", "PGG", "PWZ", "PGE", "PRM", "PAR", "PYB", "PBJ", "PFQ", "PJ7", "PAS", "PDN"},
    "fuel": {"YGN", "YGV", "YGW"},  # YG4 retiré (skip)
    "fee": {"801"},  # 4CP retiré (skip)
    "package": {"23E", "24W", "2BZ", "2BX", "21D", "22B", "27A", "2TY", "22Y", "2C1", "2T1", "24Z"},  # 2TE et 2TZ retirés (skip)
    "interior": {"B6W7", "CLX9", "YLX9", "E7X9", "FLX7", "MJX9"},
    "towing": {"ABR", "AHU", "UAQ"},
    "floor_mats": {"CLF"},
    "lights": {"LNC", "LHL"},
    "wheel_protection": {"MWH"},
    "capacity": {"Z7H"},
    "night_edition": {"ASH"},
    "equipment_group": {"A6H", "A7H"},
}


def deduplicate_by_equivalence(options, equivalent_codes):
    """
    Supprime les doublons basés sur equivalent_codes.
    Priorité à l'option avec montant > 0 (OCR direct).
    """
    final = []

    for opt in options:
        code = opt.get("product_code")
        duplicate_found = False

        for existing in final:
            existing_code = existing.get("product_code")

            if (
                existing_code in equivalent_codes.get(code, set())
                or code in equivalent_codes.get(existing_code, set())
            ):
                duplicate_found = True
                if opt.get("amount", 0) > existing.get("amount", 0):
                    final.remove(existing)
                    final.append(opt)
                break

        if not duplicate_found:
            final.append(opt)

    return final


def parse_options(text: str) -> List[Dict[str, Any]]:
    """
    Extrait la liste des options depuis le texte OCR de factures FCA Canada.
    
    Le texte OCR de Google Vision peut avoir les codes et descriptions sur des lignes séparées.
    On construit un mapping code→description en analysant le texte.
    """
    options = []
    
    # Dictionnaire des descriptions FCA connues (code → description)
    # Utilisé pour le fallback quand l'OCR ne capture pas le code
    fca_descriptions = {
        # Couleurs
        'PXJ': 'Couche nacrée cristal noir étincelant',
        'PW7': 'Blanc éclatant',
        'PWZ': 'Blanc ivoire 3 couches',
        'PWL': 'Blanc perle',
        'PX8': 'Noir diamant',
        'PAU': 'Rouge flamme',
        'PSC': 'Gris destroyer',
        'PGG': 'Gris granit cristal',
        'PBF': 'Bleu patriote',
        'PGE': 'Vert Sarge',  # Gladiator/Wrangler
        'PRM': 'Rouge velours',
        'PAR': 'Argent billet',
        'PYB': 'Jaune stinger',
        'PBJ': 'Bleu hydro',
        'PFQ': 'Granite cristal',
        'PJ7': 'Canyon Lake',
        'PAS': 'Gris de mer métallisé',  # Grand Cherokee
        'PDN': 'Gris céramique',  # Ram
        # Intérieur / Sièges
        'B6W7': 'Sièges en similicuir capri',
        'CLX9': 'Cuir Nappa ventilé',
        'YLX9': 'Premium Leather Bucket Seats',
        'CU2': 'Red Interior Accents',
        'E7X9': 'Sièges baq dossier bas tissu',  # Gladiator
        'FLX7': 'Sièges dessus en cuir Nappa',  # Grand Cherokee
        'MJX9': 'Baquets avant tissu catégorie sup',  # Ram
        # Équipements - RAM 1500 RHO
        'ANT': 'Bed Utility Group',
        'A6H': 'RHO Level 1 Equipment Group',
        'CS7': 'Tri-Fold Soft Tonneau Cover',
        'DFR': '8-Speed Automatic Transmission',
        'EFC': '3.0L I-6 HO Twin-Turbo Engine',
        'GWJ': 'Dual-Pane Panoramic Sunroof',
        'MH7': 'MOPAR RHO Exterior Graphics',
        'MMB': 'MOPAR RHO Hood Graphics',
        'MTW': 'MOPAR Off-Road Style Running Boards',
        'YGV': '17 Additional Litres Of Gas',
        # Équipements - RAM 2500/3500
        'AHU': 'Prep remorq sellette/col-de-cygne',
        'ASH': 'Édition nuit',
        'A7H': 'Ensemble équip niveau 2 Big Horn',
        'CLF': 'Tapis protect avant/arr Mopar',
        'DFM': 'Transmission auto 8 vit ZF Powerline',
        'ETM': '6 cyl turbo diesel Cummins 6.7L',
        'LHL': 'Commandes auxiliaires tableau bord',
        'LNC': 'Feux de gabarit',
        'MWH': 'Doublures passage roue arrière',
        'Z7H': 'PNBV 4490 kg (9900 lb)',
        '24Z': 'Ensemble Éclair 24Z',
        # Équipements - Gladiator/Wrangler
        'AJK': 'Ensemble Commodités',
        'DFT': 'Transmission Automatique 8 Vitesses',
        'ERC': 'Moteur V6 Pentastar 3.6L',
        'HT1': 'Toit Rigide Freedom Top 3 Sect Noir',
        'YGN': '15L Supplémentaires Essence',
        '41G': 'Rabais',
        # Équipements généraux
        'ABR': 'Ensemble attelage de remorque',
        'ALC': 'Ensemble allure noire',
        'DFW': 'Transmission automatique 8 vitesses',
        'YGW': '20L supplémentaires essence',
        'ADE': 'Système de divertissement arrière',
        'ADG': 'Navigation et radio satellite',
        'UAQ': 'Groupe remorquage haute capacité',
        'RSD': 'Roues 20 pouces',
        'DMC': 'Climatisation 3 zones',
        'AHR': 'Volant chauffant',
        'AWL': 'Système audio premium Alpine',
        # Équipements - Grand Cherokee
        'ACX': 'Ensemble finition Mopar',
        'ADT': 'Ensemble Premium',
        'DC1': 'Transmission automatique 8 vitesses',
        'EC7': 'Mot 4cyl ligne 2,0L GME Evo A/A-D',
        # Packages / Ensembles
        '2TE': 'Ensemble Éclair 2TE',
        '23E': 'Ensemble Éclair 23E',
        '2TW': 'Ensemble Éclair 2TW',  # Gladiator
        '24W': 'Ensemble Éclair 24W',  # Gladiator
        '2C1': 'Ensemble Éclair 2C1',  # Grand Cherokee
        '2T1': 'Ensemble Éclair 2T1',  # Grand Cherokee
        '2BZ': 'Groupe luxe',
        '2BX': 'Groupe technologie',
        '21D': 'Groupe remorquage',
        '22B': 'Groupe commodité',
        '27A': 'Groupe apparence',
        '3CC': 'Groupe 3CC',
        '2TY': 'Customer Preferred Package 2TY',
        '22Y': 'Customer Preferred Package 22Y',
        '2T1': 'Ensemble Éclair 2T1',
        # Taxes/Frais (gardés pour affichage mais pas comme options)
        '801': 'Frais de Transport',
        # NOTE: 999, 92HC1, 92HC2 sont exclus via skip_codes (codes administratifs)
    }
    
    # Dictionnaire inversé: description partielle → code
    # Pour quand l'OCR capture la description mais pas le code
    # IMPORTANT: Ces mappings doivent correspondre aux descriptions EXACTES des factures FCA
    description_to_code = {
        # Couleurs
        'CANYON LAKE': 'PJ7',
        'COUCHE NACREE CRISTAL NOIR': 'PXJ',
        'NACREE CRISTAL NOIR ETINCEL': 'PXJ',
        'CRISTAL NOIR ETINCEL': 'PXJ',
        'BLANC ECLATANT': 'PW7',
        'NOIR DIAMANT': 'PX8',
        'ROUGE FLAMME': 'PAU',
        'GRIS DESTROYER': 'PSC',
        'GRIS GRANIT CRISTAL': 'PGG',
        'BLEU PATRIOTE': 'PBF',
        'VERT SARGE': 'PGE',
        'ROUGE VELOURS': 'PRM',
        'ARGENT BILLET': 'PAR',
        'GRIS DE MER METALLISE': 'PAS',  # Grand Cherokee
        'DE MER METALLISE': 'PAS',
        
        # Intérieur / Sièges
        'SIEGES EN SIMILICUIR CAPRI': 'B6W7',
        'SIMILICUIR CAPRI': 'B6W7',
        'CUIR NAPPA VENTILE': 'CLX9',
        'PREMIUM LEATHER BUCKET': 'YLX9',
        'LEATHER BUCKET SEATS': 'YLX9',
        'RED INTERIOR ACCENTS': 'CU2',
        'SIEGES BAQ DOSSIER BAS TISSU': 'E7X9',  # Gladiator
        'BAQ DOSSIER BAS TISSU': 'E7X9',
        'DOSSIER BAS TISSU': 'E7X9',
        'SIEGES DESSUS EN CUIR NAPPA': 'FLX7',  # Grand Cherokee
        'DESSUS EN CUIR NAPPA': 'FLX7',
        'CUIR NAPPA': 'FLX7',
        
        # Équipements
        'BED UTILITY GROUP': 'ANT',
        'RHO LEVEL 1': 'A6H',
        'LEVEL 1 EQUIPMENT': 'A6H',
        'TRI-FOLD SOFT TONNEAU': 'CS7',
        'SOFT TONNEAU COVER': 'CS7',
        'ENSEMBLE ATTELAGE DE REMORQUE': 'ABR',
        'ATTELAGE DE REMORQUE': 'ABR',
        'ENSEMBLE ALLURE NOIRE': 'ALC',
        'ALLURE NOIRE': 'ALC',
        'ENSEMBLE COMMODITES': 'AJK',  # Gladiator
        'COMMODITES': 'AJK',
        'TOIT RIGIDE FREEDOM TOP': 'HT1',  # Gladiator
        'FREEDOM TOP 3 SECT': 'HT1',
        'FREEDOM TOP': 'HT1',
        
        # Transmission/Moteur
        '8-SPEED AUTOMATIC': 'DFR',
        '8 SPEED AUTOMATIC': 'DFR',
        'AUTOMATIC TRANSMISSION': 'DFR',
        'TRANSMISSION AUTOMATIQUE 8 VITESSES': 'DFW',
        'AUTOMATIQUE 8 VITESSES': 'DFT',  # Gladiator (DFT pas DFW)
        '3.0L I-6': 'EFC',
        'TWIN-TURBO ENGINE': 'EFC',
        'MOTEUR V6 PENTASTAR': 'ERC',
        'V6 PENTASTAR 3,6': 'ERC',
        'V6 PENTASTAR 3.6': 'ERC',
        'PENTASTAR 3,6 L': 'ERC',
        
        # Toit/Extérieur
        'DUAL-PANE PANORAMIC': 'GWJ',
        'PANORAMIC SUNROOF': 'GWJ',
        'TOIT OUVR PANO': 'GWJ',
        'OUVR PANO 2 PANN': 'GWJ',
        'PANO 2 PANN COMMANDVIEW': 'GWJ',
        '2 PANN COMMANDVIEW': 'GWJ',
        'RHO EXTERIOR GRAPHICS': 'MH7',
        'EXTERIOR GRAPHICS': 'MH7',
        'RHO HOOD GRAPHICS': 'MMB',
        'HOOD GRAPHICS': 'MMB',
        'OFF-ROAD STYLE RUNNING': 'MTW',
        'RUNNING BOARDS': 'MTW',
        
        # Équipements Grand Cherokee
        'ENSEMBLE FINITION MOPAR': 'ACX',
        'FINITION MOPAR': 'ACX',
        # NOTE: Ne pas mapper 'MOPAR' seul car MOPARMD = CLF (tapis), pas ACX
        'ENSEMBLE PREMIUM': 'ADT',
        'PREMIUM': 'ADT',
        'TRANSMISSION AUTOMATIQUE 8VITESSES': 'DC1',
        'TRANSMISSION AUTOMATIQUE 8 VITESSES': 'DC1',
        'AUTOMATIQUE 8VITESSES': 'DC1',
        'MOT 4CYL LIGNE 2,0L GME EVO': 'EC7',
        'MOT 4CYL LIGNE': 'EC7',
        '4CYL LIGNE 2,0L': 'EC7',
        'GME EVO': 'EC7',
        'ENSEMBLE ECLAIR 2C1': '2C1',
        'ECLAIR 2C1': '2C1',
        'ENSEMBLE ECLAIR 2T1': '2T1',
        'ECLAIR 2T1': '2T1',
        
        # Carburant
        'ADDITIONAL LITRES': 'YGV',
        'LITRES OF GAS': 'YGV',
        '17 ADDITIONAL LITRES': 'YGV',
        '20L SUPPLEMENTAIRES ESSENCE': 'YGW',
        'SUPPLEMENTAIRES ESSENCE': 'YGW',
        '15 L SUPPLEMENTAIRES': 'YGN',  # Gladiator
        '15L SUPPLEMENTAIRES': 'YGN',
        # Diesel - Ram 2500/3500 (YG4 bloqué)
        
        # Packages/Ensembles
        'CUSTOMER PREFERRED PACKAGE 2TY': '2TY',
        'PREFERRED PACKAGE 2TY': '2TY',
        'CUSTOMER PREFERRED PACKAGE 22Y': '22Y',
        'PREFERRED PACKAGE 22Y': '22Y',
        'ENSEMBLE ECLAIR 2TE': '2TE',
        'ECLAIR 2TE': '2TE',
        'ENSEMBLE ECLAIR 23E': '23E',
        'ECLAIR 23E': '23E',
        'ENSEMBLE ECLAIR 2TW': '2TW',  # Gladiator
        'ECLAIR 2TW': '2TW',
        'ENSEMBLE ECLAIR 24W': '24W',  # Gladiator
        'ECLAIR 24W': '24W',
        'GROUPE LUXE': '2BZ',
        'GROUPE TECHNOLOGIE': '2BX',
        'GROUPE REMORQUAGE': '21D',
        'GROUPE COMMODITE': '22B',
        'GROUPE APPARENCE': '27A',
        
        # Taxes/Frais (4CP bloqué)
        'DESTINATION CHARGE': '801',
        'FRAIS DE TRANSPORT': '801',
        # NOTE: 999, 92HC1, 92HC2 sont exclus via skip_codes (codes administratifs)
        'ALLOCATION MARKETING': '92HC2',
    }
    
    # Codes à ignorer (pas des options)
    invalid_codes = {
        'VIN', 'GST', 'TPS', 'QUE', 'INC', 'PDCO', 'PREF', 'MODEL', 'MODELE',
        'TOTAL', 'MSRP', 'SUB', 'EP', 'HST', 'TVQ', 'GVW', 'KG', 'FCA',
        'DIST', 'DEALER', 'SHIP', 'TERMS', 'KEY', 'OPT', 'SOLD', 'DATE',
        'INVOICE', 'VEHICLE', 'NUMBER', 'FACTURE', 'AMOUNT', 'MONTANT',
        'CE', 'DU', 'DE', 'LA', 'LE', 'AU', 'EN', 'ET', 'OU', 'UN', 'IF',
        'NO', 'SEE', 'PAGE', 'VOIR', 'PAS', 'SHOWN', 'CANADA', 'FOR',
        'ORIGINAL', 'WINDSOR', 'ONTARIO', 'BOULEVARD', 'STREET', 'SAND',
        'SOMME', 'TOIT', '20L', 'SANS', 'FRAIS', 'ACCISE', 'ALLURE',
        'AUX', 'BEAU', 'ECLAIR', 'ATTELAGE', 'OUVR', 'PANO', 'TAXES',
        'NACREE', 'CRISTAL', 'NOIR', 'ETINCEL', 'ENSEMBLE', 'GROUPE',
        'REMORQUE', 'TRANSMISSION', 'AUTOMATIQUE', 'MOTEUR', 'PENTASTAR',
        'SUPPLEMENTAIRES', 'ESSENCE', 'TRANSPORT', 'COTISATION', 'MARKETING',
        'ALLOCATION', 'FINANCE', 'EXPEDIE', 'FEDERALE', 'CLIMATISEUR',
        'SIEGES', 'SIMILICUIR', 'CAPRI', 'COMMANDVIEW', 'VITESSES',
        'NOIRE', 'EST', 'FABRIQUE', 'POUR', 'REPONDRE', 'EXIGENCES',
        'CANADIENNES', 'SPECIFIQUES', 'VEHICULE', 'VENTE', 'IMMATRICULATION',
        'HORS', 'LIMITED', 'DESCRIPTION', 'CONC', 'VENDU', 'KENNEBEC',
        'DODGE', 'CHRYSLER', 'LACROIX', 'GEORGES', 'REG', 'INS', 'AUTOMOTIVE',
        'LEE', 'HIM', 'WELLINGTON', 'TORONTO', 'ORDER', 'COMMANDE', 'CLEF',
        'COUCHE', 'C08', 'C4564', 'G5Y', '1K1', 'M5J', '1J1', 'FL', 'ON',
        '1C4', 'S8', '806264', 'R100963941', 'GFBR', 'RETING', 'II', 'III',
        'IV', 'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'NI', 'TAX', 'TAUX',
        'PAN', 'PANN',  # Fragments de descriptions (YGW retiré - c'est une option valide)
        # En-tête facture - noms concessionnaires, banques, adresses
        'ELITE', 'BANQUE', 'DOMINION', 'AVENUE', 'OUELETTE', 'TAN', 'HURRIC',
        'AQUA', 'AQUESTA', 'GRANIT', 'RAPPORT', 'PONT', 'BITUR', 'EXPRESS',
    }
    
    text_upper = text.upper()
    
    # ====== NOUVELLE LOGIQUE: EXTRAIRE TOUTES LES OPTIONS DANS L'ORDRE DE LA FACTURE ======
    # 
    # Les options sur une facture FCA apparaissent sous MODEL/OPT avec ce format:
    # CODE    DESCRIPTION                              MONTANT
    # PW7     BLANC ECLATANT                           SANS FRAIS
    # TXX8    BANQ AVANT 40-20-40 VINYLE RENFORCE      
    # ETM     6 CYL LI TURB DIESEL HR CUMMINS 6,7L    8,800.00
    
    # Pattern pour extraire les codes d'options FCA (2-5 caractères alphanumériques)
    # Format: CODE suivi d'une description ou d'un montant
    option_pattern = r'^([A-Z0-9]{2,5})\s+([A-Z][A-Z0-9\s\-,\.\(\)\/\']+?)(?:\s+[\d,]+\.\d{2}|\s+SANS\s+FRAIS|\s*\*|\s*$)'
    
    lines = text_upper.split('\n')
    found_options = []
    seen_codes = set()
    
    # Codes à ignorer (pas des options, mais des données financières/système)
    skip_codes = {
        'VIN', 'GST', 'TPS', 'QUE', 'INC', 'PDCO', 'PREF', 'MODEL', 'MODELE',
        'TOTAL', 'MSRP', 'SUB', 'EP', 'HST', 'TVQ', 'GVW', 'KG', 'FCA', 'RAM',
        'DIST', 'DEALER', 'SHIP', 'TERMS', 'KEY', 'OPT', 'SOLD', 'DATE', 'JEEP',
        'INVOICE', 'VEHICLE', 'NUMBER', 'FACTURE', 'AMOUNT', 'MONTANT', 'DODGE',
        'CE', 'DU', 'DE', 'LA', 'LE', 'AU', 'EN', 'ET', 'OU', 'UN', 'IF', 'NO',
        'SEE', 'PAGE', 'VOIR', 'SHOWN', 'CANADA', 'FOR', 'ORIGINAL', 'NI',
        'WINDSOR', 'ONTARIO', 'BOULEVARD', 'STREET', 'SOMME', 'TAXES', 'TPS',
        'TVH', 'PROV', 'NET', 'PRIX', 'SANS', 'CHRYSLER', 'GFBR', 'KENNEBEC',
        # GKRP est un prix (PDCO/MSRP), pas une option!
        'GKRP',
        # Codes administratifs FCA (pas des options réelles)
        '999', '92HC1', '92HC2',
        # Codes à ignorer (fallback incorrects ou non désirés)
        'YG4', '4CP', '2TZ',
        # Villes québécoises et canadiennes courantes
        'LAVAL', 'QUEBEC', 'MONTREAL', 'TORONTO', 'OTTAWA', 'CALGARY', 'VANCOUVER',
        'LONGUEUIL', 'GATINEAU', 'SHERBROOKE', 'LEVIS', 'TROIS', 'SAGUENAY',
        'DRUMMONDVILLE', 'RIMOUSKI', 'CHICOUTIMI', 'GRANBY', 'SAINT', 'SAINTE',
        # Autres mots à ignorer
        'SOLD', 'SHIP', 'BILL', 'ATTN', 'PHONE', 'FAX', 'EMAIL', 'WWW', 'HTTP',
        'LTEE', 'LTD', 'ENRG', 'INC', 'CORP', 'AUTO', 'AUTOS',
        # Codes modèles (pas des options)
        'DT6S98', 'DJ7L92', 'DJ7H91', 'DT6L98', 'WLJP74', 'WLJH74', 'WLJH75', 'VF1L13',
        # Fragments de descriptions OCR erronés (mots seuls, pas des codes FCA)
        'MODE', 'BED', 'RHO', 'RED', 'THIS', 'OR', '1F', '2F', '3F', '17', '20', '15',
        'THE', 'TO', 'IS', 'IT', 'OF', 'IN', 'ON', 'AT', 'BY', 'AN', 'AS', '20L',
        'MOPAR', 'LEVEL', 'GROUP', 'PACKAGE', 'INTERIOR', 'EXTERIOR',
        'ACCENTS', 'GRAPHICS', 'BOARDS', 'COVER', 'SEATS', 'ENGINE',
        'TRANSMISSION', 'SUNROOF', 'UTILITY', 'LAKE', 'STYLE', 'SPEED',
        'MANUFACTURED', 'MEET', 'REGISTRATION', 'OUTSIDE', 'SILOW',
        'VEHICLE', 'EQUIPMENT', 'TONNEAU', 'PANORAMIC', 'AUTOMATIC',
        'LEATHER', 'PREMIUM', 'BUCKET', 'SOFT', 'FOLD', 'DUAL', 'PANE',
        'TWIN', 'TURBO', 'ADDITIONAL', 'LITRES', 'GAS', 'FEDERAL',
        'EXCISE', 'DESTINATION', 'CHARGE', 'FINANCED', 'SHIPPED',
        'ASSESSMENT', 'ALLOWANCE', 'MARKETING', 'PPA', 'CUSTOMER',
        'PREFERRED', 'RUNNING', 'HOOD', 'OFF', 'ROAD',
        # Mots de l'en-tête facture (noms concessionnaires, banques, adresses)
        'ELITE', 'BANQUE', 'DOMINION', 'AVENUE', 'OUELETTE',
        'TAN', 'HURRIC', 'AQUA', 'AQUESTA', 'CRISTAL', 'GRANIT',
        'RAPPORT', 'PONT', 'BITUR', 'EXPRESS',
        'COMMANDE', 'FABRIQUE', 'REPONDRE', 'EXIGENCES', 'CANADIENNES',
        'SPECIFIQUES', 'CETTE', 'FABRIQUE',
        'ADIAN', 'NADIAN', 'CANAD',  # Fragments OCR de "CANADIENNES"
        # Fragments OCR erronés des factures Grand Cherokee
        'ACREE', 'COUCHE', 'NACREE', 'ETINCEL', 'SIEGES', 'SIMILICUIR', 'CAPRI',
        'MOTEUR', 'PENTASTAR', 'TOIT', 'OUVR', 'PANO', 'PANN', 'COMMANDVIEW',
        'SUPPLEMENTAIRES', 'ESSENCE', 'TAXE', 'ACCISE', 'FRAIS', 'TRANSPORT',
        'ENSEMBLE', 'ATTELAGE', 'REMORQUE', 'ALLURE', 'NOIRE', 'VITESSES',
        'AUTOMATIQUE', 'ECLAIR', 'COTISATION', 'ALLOCATION',
        # Fragments OCR erronés des factures ProMaster
        'PORTES', 'ARR', 'BATTANTES', 'BATTANTS', 'GLACE', 'FIXE', 'TION',
        'HORS', 'CANADA', 'IMMATRICULATION', 'VENTE', 'HIGH', 'ROOF', 'CARGO',
        'VAN', 'LOW', 'EXTENDED', 'SUPER', 'WB', '136WB', '159WB',
        # Fragments OCR erronés des factures Gladiator/Wrangler
        'BAQ', 'DOSSIER', 'BAS', 'TISSU', 'RIGIDE', 'FREEDOM', 'TOP', 'SECT',
        'NOIR', 'COMMODITES', 'CLIMATISEUR',
        # Fragments OCR erronés des factures Ram 2500/3500 - MOTS SEULS PAS DES CODES
        'GRIS', 'PREP', 'FEUX', 'PNBV', 'CERAMIQUE', 'REMORQ', 'SELLETTE', 
        'GABARIT', 'EDITION', 'NUIT', 'COMMANDES', 'AUXILIAIRES', 'TABLEAU',
        'BORD', 'DOUBLURES', 'PASSAGE', 'ROUE', 'ARRIERE', 'DIESEL',
        'BAQUETS', 'AVANT', 'CATEGORIE', 'SUP', 'NIVEAU', 'HORN', 'BIG',
        'TAPIS', 'PROTECT', 'MOPARMD', 'POWERLINE', 'TURB', 'CUMMINS',
        'COL', 'CYGNE', 'EQUIP'
    }
    
    # Mots-clés d'adresse à ignorer dans la description
    # Note: Utiliser des patterns avec espaces pour éviter faux positifs (ex: OFF-ROAD != ROAD)
    address_keywords = [
        'SOLD TO', 'SHIP TO', 'TERMS', 'DEALER NO', 'INVOICE DATE',
        ' STREET', ' AVENUE', ' BOULEVARD', ' ROAD ', ' DRIVE ', ' PLACE ',
        ' RUE ', ' CHEMIN ', ' ROUTE ', ' AUTOROUTE',
        ' QUEBEC', ' ONTARIO', ' ALBERTA', ' MANITOBA', ' SASKATCHEWAN',
        ' MONTREAL', ' TORONTO', ' VANCOUVER', ' CALGARY', ' OTTAWA',
        ' LAVAL', ' LONGUEUIL', ' GATINEAU', ' SHERBROOKE', ' LEVIS',
        'TROIS-RIVIERES', 'DRUMMONDVILLE', 'SAGUENAY', 'RIMOUSKI',
        'CANADA INC', ' LTEE', ' LTD', ' ENRG', 'AUTOMOBILES',
        'CONCESSIONNAIRE', ' DEALER', 'DEALERSHIP',
        # Adresses du dealer dans les captures
        'SOURCES', 'DOLLARD', 'ORMEAUX', 'WINDSOR'
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Ignorer les lignes qui ressemblent à des codes postaux canadiens (A1A 1A1)
        if re.match(r'^[A-Z]\d[A-Z]\s*\d[A-Z]\d', line):
            continue
        
        # Ignorer les lignes qui commencent par un numéro de rue (ex: "1234 RUE...")
        # Les codes FCA numériques sont 3 chiffres max (801, 999), les adresses ont 4+ chiffres
        if re.match(r'^\d{4,}\s+[A-Z]', line):
            continue
        
        # Ignorer les lignes qui sont des adresses courtes (3 chiffres + mot d'adresse)
        if re.match(r'^\d{3}\s+(AVENUE|RUE|CHEMIN|BOULEVARD|ROUTE|STREET|ROAD|DRIVE|PLACE|CH\s)', line, re.IGNORECASE):
            continue
        
        # Chercher un code au début de la ligne
        # Format: CODE + espace + description
        # Accepte codes de 2-6 caractères (pour 92HC1, 92HC2, DT6S98 etc.)
        match = re.match(r'^([A-Z0-9]{2,6})\s+(.+)$', line)
        if match:
            code = match.group(1)
            description_raw = match.group(2).strip()
            
            # Ignorer les codes dans la liste skip
            if code in skip_codes:
                continue
            
            # Ignorer les codes déjà vus
            if code in seen_codes:
                continue
            
            # Ignorer si le code ressemble EXACTEMENT à un code postal canadien  
            # Format: Lettre + Chiffre + Lettre (comme H2X, G1K, M5V)
            # Exceptions: Les codes FCA valides comme A6H, M5V ne doivent PAS être filtrés
            # Solution: Ne filtrer que les préfixes de codes postaux les plus courants au Québec/Ontario
            # qui ne sont PAS utilisés par FCA: G, H, J, K, L, M, N, P
            # Note: A (Terre-Neuve), B (N-É), etc. sont rares et les options FCA comme A6H sont valides
            if re.match(r'^[GHJKLMNP]\d[A-Z]$', code):
                continue
            
            # Ignorer si la description contient des mots-clés d'adresse
            if any(keyword in description_raw.upper() for keyword in address_keywords):
                continue
            
            # Ignorer si la description ressemble à un numéro de téléphone
            if re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', description_raw):
                continue
            
            # Ignorer si la description contient un code postal canadien (A1A 1A1)
            if re.search(r'[A-Z]\d[A-Z]\s*\d[A-Z]\d', description_raw):
                continue
            
            # Ignorer si la description est trop courte (probablement une abréviation de province)
            if len(description_raw) <= 3:
                continue
            
            # Nettoyer la description (enlever montants à la fin)
            description_clean = re.sub(r'\s+[\d,]+\.\d{2}\s*\*?$', '', description_raw)
            description_clean = re.sub(r'\s+SANS\s+FRAIS\s*$', '', description_clean)
            description_clean = description_clean.strip()
            
            # Vérifier que c'est un code d'option valide (pas trop long de description)
            if len(description_clean) > 2 and len(description_clean) < 80:
                # Vérifier si le code est connu OU si c'est un code FCA valide (2-6 chars alnum)
                # Si le "code" n'est pas valide mais la description l'est, chercher dans description_to_code
                real_code = code
                real_desc = description_clean
                
                # Si le code ressemble à un mot (pas un code FCA), chercher le vrai code
                if len(code) > 3 and code.isalpha():
                    # Le "code" est probablement un mot de la description
                    # Reconstruire: "CODE DESC..." où CODE est perdu
                    full_line = f"{code} {description_clean}".upper()
                    
                    # Chercher une description connue
                    for desc_key, real_code_value in description_to_code.items():
                        if desc_key in full_line:
                            real_code = real_code_value
                            # Garder la description complète
                            real_desc = full_line.replace(desc_key, '').strip() or fca_descriptions.get(real_code, full_line)
                            break
                
                # Éviter les doublons
                if real_code in seen_codes:
                    continue
                    
                seen_codes.add(real_code)
                
                # Format: "CODE - Description"
                formatted = f"{real_code} - {real_desc.title()}"
                
                found_options.append({
                    "product_code": real_code,
                    "description": formatted[:60],
                    "amount": 0
                })
    
    # ====== FALLBACK: Rechercher les descriptions connues dans le texte ======
    # Quand l'OCR ne capture pas le code mais capture la description
    # IMPORTANT: Les options fallback sont ajoutées À LA FIN pour préserver l'ordre des options OCR directes
    
    fallback_options = []  # Collecter séparément
    
    # Groupes de codes équivalents (ne pas ajouter si un code similaire existe déjà)
    equivalent_codes = {
        # Transmissions automatiques (toutes équivalentes entre elles)
        'DFT': {'DFR', 'DFW', 'DFM', 'DFD', 'DFL', 'DFH', 'DC1', 'DEX', 'DFQ', 'DF2', 'DF8'},
        'DFR': {'DFT', 'DFW', 'DFM', 'DFD', 'DFL', 'DFH', 'DC1', 'DEX', 'DFQ', 'DF2', 'DF8'},
        'DFW': {'DFT', 'DFR', 'DFM', 'DFD', 'DFL', 'DFH', 'DC1', 'DEX', 'DFQ', 'DF2', 'DF8'},
        'DFM': {'DFT', 'DFR', 'DFW', 'DFD', 'DFL', 'DFH', 'DC1', 'DEX', 'DFQ', 'DF2', 'DF8'},
        'DC1': {'DFT', 'DFR', 'DFW', 'DFM', 'DFD', 'DFL', 'DFH', 'DEX', 'DFQ', 'DF2', 'DF8'},
        'DFH': {'DFT', 'DFR', 'DFW', 'DFM', 'DFD', 'DFL', 'DC1', 'DEX', 'DFQ', 'DF2', 'DF8'},
        # Carburant supplémentaire
        'YGN': {'YGV', 'YGW'},
        'YGV': {'YGN', 'YGW'},
        'YGW': {'YGN', 'YGV'},
    }
    
    for desc_key, code in description_to_code.items():
        if code in seen_codes:
            continue
        if code in skip_codes:
            continue
        # Vérifier si un code équivalent existe déjà
        if code in equivalent_codes:
            if any(eq in seen_codes for eq in equivalent_codes[code]):
                continue
        if desc_key in text_upper:
            seen_codes.add(code)
            desc = fca_descriptions.get(code, desc_key.title())
            fallback_options.append({
                "product_code": code,
                "description": f"{code} - {desc}",
                "amount": 0,
                "source": "fallback"
            })
    
    # Fallback additionnel: chercher les codes connus directement
    for code, desc in fca_descriptions.items():
        if code in seen_codes:
            continue
        if code in invalid_codes:
            continue
        if code in skip_codes:
            continue
        # Vérifier si un code équivalent existe déjà
        if code in equivalent_codes:
            if any(eq in seen_codes for eq in equivalent_codes[code]):
                continue
        if re.search(rf'\b{re.escape(code)}\b', text_upper):
            seen_codes.add(code)
            # Essayer d'extraire la vraie description depuis le texte OCR
            actual_desc = desc
            ocr_desc_match = re.search(
                rf'\b{re.escape(code)}\s+([A-Z][A-Z\s\-/,\'\d]+?)(?:\s+\d{{3,}}|\s+SANS\s+FRAIS|\s*$)',
                text_upper,
                re.MULTILINE
            )
            if ocr_desc_match:
                raw_desc = ocr_desc_match.group(1).strip()
                if len(raw_desc) > 3:
                    actual_desc = raw_desc.title()
            fallback_options.append({
                "product_code": code,
                "description": f"{code} - {actual_desc}",
                "amount": 0,
                "source": "fallback"
            })
    
    # Ajouter les options fallback À LA FIN (après les options OCR directes)
    found_options.extend(fallback_options)
    
    # ====== DÉDUPLICATION FINALE ======
    # Par équivalence existante + priorité OCR (montant > 0)
    found_options = deduplicate_by_equivalence(found_options, equivalent_codes)
    
    # ====== LES OPTIONS SONT DÉJÀ DANS L'ORDRE DE LA FACTURE ======
    # Pas de tri! On garde l'ordre d'apparition
    
    # Limiter à 25 options max
    return found_options[:25]


def parse_stock_number(text: str) -> Optional[str]:
    """
    Extrait le numéro de stock (souvent écrit à la main, 5 chiffres)
    Le stock manuscrit est généralement le DERNIER nombre de 5 chiffres sur la facture
    (écrit en bas, au centre ou à droite)
    """
    # Patterns avec label explicite (priorité haute)
    patterns = [
        r"STOCK\s*#?\s*(\d{5})",
        r"INV\s*#?\s*(\d{5})",
        r"#(\d{5})\b",
        r"STOCK\s*NO\.?\s*(\d{5})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Codes à exclure (adresses, montants partiels, codes financiers)
    exclude_patterns = {
        '10240',  # Adresse dealer
        '07544', '07774', '06997', '07205', '07070', '07277',  # Codes financiers
        '72752', '76389', '64951',  # Montants
        '50000', '05000',  # GVW patterns
    }
    
    # Exclure les nombres qui font partie d'adresses (suivi de BOULEVARD, ST-, etc.)
    address_context = re.findall(r'(\d{5})[,\s]+(BOULEVARD|BLVD|AVENUE|AVE|RUE|ST-|STREET)', text, re.IGNORECASE)
    for addr_num, _ in address_context:
        exclude_patterns.add(addr_num)
    
    # Trouver TOUS les nombres de 5 chiffres isolés sur leur propre ligne
    # Le stock manuscrit est généralement le DERNIER (tout en bas de la facture)
    lines = text.split('\n')
    stock_candidates = []
    
    # D'abord chercher les lignes avec UNIQUEMENT un nombre 5 chiffres (manuscrit)
    for line in lines:
        line = line.strip()
        # Ligne contenant uniquement un nombre de 5 chiffres (ou avec quelques caractères)
        match = re.match(r'^[\s\W]*(\d{5})[\s\W]*$', line)
        if match:
            num = match.group(1)
            if num not in exclude_patterns and not num.startswith('0'):
                stock_candidates.append(num)
    
    # Prendre le DERNIER candidat (le plus en bas de la facture)
    if stock_candidates:
        return stock_candidates[-1]
    
    # Fallback: chercher le dernier nombre de 5 chiffres valide dans le texte
    # En commençant par la fin du texte (où le stock manuscrit se trouve souvent)
    all_five_digits = re.findall(r'\b(\d{5})\b', text)
    
    # Filtrer et prendre le dernier
    valid_candidates = []
    for num in all_five_digits:
        if num not in exclude_patterns and not num.startswith('0'):
            # Vérifier que ce n'est pas un montant ou partie d'une adresse
            if not re.search(rf'\${num}|{num}\.00|{num}\.60|{num}[,\s]+BOULEVARD|{num}[,\s]+BLVD', text, re.IGNORECASE):
                valid_candidates.append(num)
    
    if valid_candidates:
        return valid_candidates[-1]  # Retourner le DERNIER
    
    return None


def parse_invoice_text(ocr_result: Dict[str, str]) -> Dict[str, Any]:
    """
    Parse complet du texte OCR en données structurées.
    
    Prend le résultat du pipeline OCR par zones et extrait:
    - VIN
    - Model code
    - EP, PDCO, PREF, Holdback
    - Subtotal, Total
    - Options
    - Stock number
    """
    result = {
        "vin": None,
        "model_code": None,
        "model": None,  # Modèle extrait de la description (Ram 3500, etc.)
        "stock_no": None,
        "trim": None,  # Trim extrait de la facture
        "ep_cost": None,
        "pdco": None,
        "pref": None,
        "holdback": None,
        "subtotal": None,
        "invoice_total": None,
        "options": [],
        "fields_extracted": 0,
        "parse_method": "regex_zones"
    }
    
    # Parse VIN depuis zone VIN
    vin_text = ocr_result.get("vin_text", "")
    result["vin"] = parse_vin(vin_text)
    if result["vin"]:
        result["fields_extracted"] += 1
    
    # Chercher VIN dans full_text si pas trouvé
    if not result["vin"]:
        full_text = ocr_result.get("full_text", "")
        result["vin"] = parse_vin(full_text)
        if result["vin"]:
            result["fields_extracted"] += 1
    
    # Model code depuis zone VIN
    result["model_code"] = parse_model_code(vin_text)
    if not result["model_code"]:
        result["model_code"] = parse_model_code(ocr_result.get("full_text", ""))
    
    # Modèle et Trim depuis la description (full_text)
    full_text = ocr_result.get("full_text", "")
    result["model"] = parse_model_from_description(full_text)
    result["trim"] = parse_trim_from_description(full_text)
    
    # Données financières depuis zone finance
    finance_text = ocr_result.get("finance_text", "")
    financial = parse_financial_data(finance_text)
    
    # Si pas trouvé dans zone finance, chercher dans full_text
    if not financial["ep_cost"]:
        financial = parse_financial_data(ocr_result.get("full_text", ""))
    
    result["ep_cost"] = financial["ep_cost"]
    result["pdco"] = financial["pdco"]
    result["pref"] = financial["pref"]
    result["holdback"] = financial["holdback"]
    
    if result["ep_cost"]:
        result["fields_extracted"] += 1
    if result["pdco"]:
        result["fields_extracted"] += 1
    
    # Totaux depuis zone totals
    totals_text = ocr_result.get("totals_text", "")
    totals = parse_totals(totals_text)
    
    if not totals["subtotal"]:
        totals = parse_totals(ocr_result.get("full_text", ""))
    
    result["subtotal"] = totals["subtotal"]
    result["invoice_total"] = totals["invoice_total"]
    
    if result["subtotal"]:
        result["fields_extracted"] += 1
    
    # Options depuis zone options
    options_text = ocr_result.get("options_text", "")
    result["options"] = parse_options(options_text)
    
    if len(result["options"]) >= 3:
        result["fields_extracted"] += 1
    
    # Stock number
    result["stock_no"] = parse_stock_number(ocr_result.get("full_text", ""))
    
    logger.info(f"Parser: {result['fields_extracted']} fields extracted, VIN={result['vin']}, EP={result['ep_cost']}")
    
    return result
