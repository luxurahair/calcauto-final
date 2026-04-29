"""
Helpers robustes pour le parsing des PDFs FCA Canada.
Normalisation, clés stables, parsing de montants, matching intelligent.
"""
import re
from typing import Any, Dict, List, Optional, Tuple


def get_model_key(model_text: str) -> str:
    """
    Cree une cle unique et stable pour chaque vehicule.
    Utilisee pour le matching noms<->taux sans dependance a l'index.
    """
    if not model_text:
        return ""
    text = str(model_text).strip().upper()
    text = re.sub(r'\s+', ' ', text)
    # Nettoyer: enlever exclusions entre parentheses pour la base
    base = re.sub(r'\s*\([^)]*\)', '', text).strip()
    # Enlever annee au debut si presente
    base = re.sub(r'^\d{4}\s+', '', base).strip()
    # Enlever prefixes "ALL-NEW", "NEW"
    base = re.sub(r'^(ALL[- ]NEW|NEW)\s+', '', base).strip()
    return base


def normalize_model_name(name: str) -> str:
    """Normalisation legere pour affichage (conserve les details)."""
    if not name:
        return ""
    return re.sub(r'\s+', ' ', str(name).replace('\n', ' ')).strip()


def merge_multiline_names(raw_names: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """
    Fusionne les noms de vehicules qui sont splites sur 2 lignes du PDF.
    Ex: ligne 1 = "Grand Cherokee L (excludes Laredo"
        ligne 2 = "(WLJH75 2*A & 2*B) and Overland (WLJS75))"
    -> fusionne en une seule entree.
    """
    if not raw_names:
        return []
    merged = []
    for ri, name in raw_names:
        # Si la ligne commence par ( ou est tres courte ET qu'on a un precedent
        if merged and (
            name.startswith('(') or
            name.startswith(')') or
            (len(name) < 20 and not any(kw in name for kw in ['Ram', 'Jeep', 'Dodge', 'Chrysler', 'Fiat', 'Grand', 'Wrangler', 'Compass', 'Cherokee', 'Charger', 'Durango', 'Hornet', 'Gladiator', 'Pacifica', 'Wagoneer', 'ProMaster', '500e', 'Daytona', 'Caravan']))
        ):
            prev_ri, prev_name = merged[-1]
            merged[-1] = (prev_ri, f"{prev_name} {name}")
        else:
            merged.append((ri, name))
    return merged


def match_names_to_rates(
    vehicle_names: List[Tuple[int, str]],
    rate_data_rows: List[Tuple[int, Any]],
) -> List[Tuple[Tuple[int, str], Tuple[int, Any]]]:
    """
    Matching intelligent noms<->taux.
    Si les comptes sont egaux -> zip direct (le cas le plus courant, rapide).
    Si mismatch -> matching par proximite de row_index dans le tableau.
    """
    if len(vehicle_names) == len(rate_data_rows):
        # Cas ideal: meme nombre = zip direct (fiable car les tables sont alignees)
        return list(zip(vehicle_names, rate_data_rows))

    # Mismatch: utiliser la proximite des indices de ligne
    matched = []
    used_rates = set()

    for vi, (name_ri, vname) in enumerate(vehicle_names):
        best_rate_idx = None
        best_distance = float('inf')

        for ri_idx, (rate_ri, rr) in enumerate(rate_data_rows):
            if ri_idx in used_rates:
                continue
            distance = abs(rate_ri - name_ri)
            if distance < best_distance:
                best_distance = distance
                best_rate_idx = ri_idx

        if best_rate_idx is not None and best_distance <= 15:
            matched.append(
                (vehicle_names[vi], rate_data_rows[best_rate_idx])
            )
            used_rates.add(best_rate_idx)

    return matched
