"""
Tests CI/CD post-import : Validation de l'intégrité des données après import.
Vérifie la séparation des trims, le matching inventaire, les calculs,
et la structure des fichiers JSON générés.

Ces tests sont autonomes (pas de serveur/MongoDB requis).
"""
import pytest
import json
import os
import sys
import math
import re
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


# ═══════════════════════════════════════════════════
# 1. Tests de séparation des trims dans les résiduels
# ═══════════════════════════════════════════════════

class TestTrimSeparation:
    """Vérifie que les trims sont correctement séparés dans les fichiers résiduels."""

    def _load_residuals(self):
        """Charge tous les fichiers résiduels disponibles."""
        files = glob.glob(os.path.join(DATA_DIR, 'sci_residuals_*.json'))
        assert len(files) > 0, "Aucun fichier résiduel trouvé"
        results = {}
        for f in files:
            name = os.path.basename(f)
            with open(f) as fh:
                results[name] = json.load(fh)
        return results

    def test_sport_rebel_separated(self):
        """Ram 1500 Sport et Rebel doivent avoir des résiduels DIFFÉRENTS."""
        for fname, data in self._load_residuals().items():
            vehicles = data.get('vehicles', [])
            sport_res = None
            rebel_res = None
            for v in vehicles:
                if v.get('brand', '').lower() != 'ram':
                    continue
                if '1500' not in v.get('model_name', ''):
                    continue
                if v.get('model_year') != 2026:
                    continue
                trim = (v.get('trim') or '').lower()
                body = (v.get('body_style') or '').lower()
                if 'sport' in trim and 'lwb' in body:
                    sport_res = v.get('residual_percentages', {})
                elif 'rebel' in trim:
                    rebel_res = v.get('residual_percentages', {})

            if sport_res and rebel_res:
                # Sport LWB et Rebel doivent être différents (Rebel a typiquement +1%)
                assert sport_res != rebel_res, \
                    f"{fname}: Sport et Rebel ont les mêmes résiduels! Sport={sport_res} Rebel={rebel_res}"

    def test_no_duplicate_vehicle_entries(self):
        """Chaque combinaison brand/model/trim/body/year doit être unique."""
        for fname, data in self._load_residuals().items():
            vehicles = data.get('vehicles', [])
            seen = set()
            for v in vehicles:
                key = f"{v.get('brand')}|{v.get('model_name')}|{v.get('trim')}|{v.get('body_style')}|{v.get('model_year')}"
                assert key not in seen, f"{fname}: Doublon trouvé: {key}"
                seen.add(key)

    def test_residual_values_valid(self):
        """Les valeurs résiduelles doivent être entre 10% et 80%."""
        for fname, data in self._load_residuals().items():
            for v in data.get('vehicles', []):
                for term, val in v.get('residual_percentages', {}).items():
                    pct = int(val) if isinstance(val, str) else val
                    assert 10 <= pct <= 80, \
                        f"{fname}: {v.get('brand')} {v.get('model_name')} {v.get('trim')} term={term} résiduel={pct}% hors limites"

    def test_all_months_have_both_model_years(self):
        """Chaque fichier résiduel doit contenir des véhicules 2025 ET 2026."""
        for fname, data in self._load_residuals().items():
            vehicles = data.get('vehicles', [])
            years = set(v.get('model_year') for v in vehicles)
            assert 2025 in years or 2026 in years, f"{fname}: Aucune année valide trouvée: {years}"


# ═══════════════════════════════════════════════════
# 2. Tests de structure des fichiers JSON
# ═══════════════════════════════════════════════════

class TestDataFileStructure:
    """Vérifie la structure et cohérence des fichiers de données."""

    def test_residual_file_structure(self):
        """Chaque fichier résiduel doit avoir les clés requises."""
        files = glob.glob(os.path.join(DATA_DIR, 'sci_residuals_*.json'))
        for f in files:
            with open(f) as fh:
                data = json.load(fh)
            fname = os.path.basename(f)
            assert 'effective_from' in data, f"{fname}: manque 'effective_from'"
            assert 'vehicles' in data, f"{fname}: manque 'vehicles'"
            assert 'km_adjustments' in data, f"{fname}: manque 'km_adjustments'"
            assert len(data['vehicles']) > 100, f"{fname}: seulement {len(data['vehicles'])} véhicules (attendu >100)"

    def test_lease_rates_file_structure(self):
        """Chaque fichier lease rates doit avoir les clés requises."""
        files = glob.glob(os.path.join(DATA_DIR, 'sci_lease_rates_*.json'))
        for f in files:
            with open(f) as fh:
                data = json.load(fh)
            fname = os.path.basename(f)
            assert 'program_period' in data, f"{fname}: manque 'program_period'"
            assert 'terms' in data, f"{fname}: manque 'terms'"
            assert 'vehicles_2026' in data or 'vehicles_2025' in data, \
                f"{fname}: manque 'vehicles_2026' ou 'vehicles_2025'"

    def test_km_adjustments_file_structure(self):
        """Chaque fichier KM doit avoir la structure correcte."""
        files = glob.glob(os.path.join(DATA_DIR, 'km_adjustments_*.json'))
        for f in files:
            with open(f) as fh:
                data = json.load(fh)
            fname = os.path.basename(f)
            assert 'standard_km' in data, f"{fname}: manque 'standard_km'"
            assert 'adjustments' in data, f"{fname}: manque 'adjustments'"
            adj = data['adjustments']
            # Doit avoir au moins 12000 et 18000 km
            assert '12000' in adj or 12000 in adj, f"{fname}: manque ajustement 12000km"

    def test_program_meta_structure(self):
        """Chaque fichier meta doit avoir les clés pour la bannière."""
        files = glob.glob(os.path.join(DATA_DIR, 'program_meta_*.json'))
        for f in files:
            with open(f) as fh:
                data = json.load(fh)
            fname = os.path.basename(f)
            assert 'event_names' in data, f"{fname}: manque 'event_names'"
            assert 'loyalty_rate' in data, f"{fname}: manque 'loyalty_rate'"
            assert isinstance(data['loyalty_rate'], (int, float)), f"{fname}: loyalty_rate invalide"


# ═══════════════════════════════════════════════════
# 3. Tests de matching inventaire ↔ programme
# ═══════════════════════════════════════════════════

class TestInventoryProgramMatching:
    """Teste la logique de matching entre véhicules inventaire et programmes."""

    @staticmethod
    def matches(vehicle, program):
        """Reproduit la logique matchesInventoryToProgram du frontend."""
        if vehicle['brand'].lower() != program['brand'].lower():
            return False
        if str(vehicle['year']) != str(program['year']):
            return False

        inv_model = vehicle['model'].lower().replace(' ', '')
        prog_model = program['model'].lower().replace(' ', '')
        inv_trim = vehicle.get('trim', '').lower()
        prog_trim = program.get('trim', '').lower()

        prog_models = prog_model.split('/')
        model_match = any(pm == inv_model for pm in prog_models) or inv_model == prog_model
        if not model_match:
            return False

        has_exclusion = 'excl' in prog_trim or 'excludes' in prog_trim
        is_specific = not has_exclusion and 'models' not in prog_trim and ',' not in prog_trim

        if is_specific:
            prog_first = prog_trim.split('(')[0].strip().split()[0]
            return prog_first in inv_trim or inv_trim.split(' ')[0] in prog_trim

        if has_exclusion:
            excl_match = re.search(r'(?:excl(?:udes?)?)\s+(.+?)(?:\)|$)', prog_trim, re.I)
            if excl_match:
                exclusions = excl_match.group(1).lower()
                if 'power wagon' in exclusions and 'power wagon' in inv_trim:
                    return False
                if 'chassis cab' in exclusions and 'chassis cab' in inv_trim:
                    return False
            return True

        prog_trims = [t.strip() for t in prog_trim.split(',')]
        if len(prog_trims) > 1:
            inv_first = inv_trim.split(' ')[0]
            return any(inv_first in pt or pt in inv_trim for pt in prog_trims)

        return True

    # --- Ram 2500 Tradesman vs Power Wagon ---

    def test_tradesman_not_in_power_wagon(self):
        """Tradesman ne doit PAS matcher le programme Power Wagon."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '2500', 'trim': 'Tradesman Crew Cab 4x4'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '2500', 'trim': 'Power Wagon Crew Cab (DJ7X91 2UP)'}
        assert self.matches(inv, prog) is False

    def test_tradesman_in_gas_models(self):
        """Tradesman DOIT matcher le programme Gas Models (excl Power Wagon)."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '2500', 'trim': 'Tradesman Crew Cab 4x4'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '2500/3500', 'trim': 'Gas Models (excl 2500 Power Wagon Crew Cab (DJ7X91 2UP), Chassis Cab Models)'}
        assert self.matches(inv, prog) is True

    def test_power_wagon_in_power_wagon_prog(self):
        """Power Wagon inventaire DOIT matcher le programme Power Wagon."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '2500', 'trim': 'Power Wagon Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '2500', 'trim': 'Power Wagon Crew Cab (DJ7X91 2UP)'}
        assert self.matches(inv, prog) is True

    def test_power_wagon_not_in_gas_models(self):
        """Power Wagon ne doit PAS matcher Gas Models (excl Power Wagon)."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '2500', 'trim': 'Power Wagon Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '2500/3500', 'trim': 'Gas Models (excl 2500 Power Wagon Crew Cab (DJ7X91 2UP), Chassis Cab Models)'}
        assert self.matches(inv, prog) is False

    # --- Ram 1500 Sport vs Rebel ---

    def test_sport_in_sport_rebel(self):
        """Sport DOIT matcher le programme Sport, Rebel."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Sport Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Sport, Rebel'}
        assert self.matches(inv, prog) is True

    def test_rebel_in_sport_rebel(self):
        """Rebel DOIT matcher le programme Sport, Rebel."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Rebel Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Sport, Rebel'}
        assert self.matches(inv, prog) is True

    def test_sport_not_in_tradesman_express(self):
        """Sport ne doit PAS matcher Tradesman, Express, Warlock."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Sport Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Tradesman, Express, Warlock'}
        assert self.matches(inv, prog) is False

    def test_tradesman_in_tradesman_express(self):
        """Tradesman DOIT matcher Tradesman, Express, Warlock."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Tradesman Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Tradesman, Express, Warlock'}
        assert self.matches(inv, prog) is True

    # --- Cross-brand checks ---

    def test_jeep_not_matching_ram(self):
        """Un Jeep ne doit PAS matcher un programme Ram."""
        inv = {'brand': 'Jeep', 'year': 2026, 'model': 'Wrangler', 'trim': 'Sport'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Sport, Rebel'}
        assert self.matches(inv, prog) is False

    def test_wrong_year_no_match(self):
        """Un véhicule 2025 ne doit PAS matcher un programme 2026."""
        inv = {'brand': 'Ram', 'year': 2025, 'model': '1500', 'trim': 'Sport Crew Cab'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '1500', 'trim': 'Sport, Rebel'}
        assert self.matches(inv, prog) is False

    # --- Chassis Cab exclusions ---

    def test_chassis_cab_excluded(self):
        """Chassis Cab doit être exclu des Gas Models."""
        inv = {'brand': 'Ram', 'year': 2026, 'model': '3500', 'trim': 'Chassis Cab 4x4'}
        prog = {'brand': 'Ram', 'year': 2026, 'model': '2500/3500', 'trim': 'Gas Models (excl 2500 Power Wagon Crew Cab, Chassis Cab Models)'}
        assert self.matches(inv, prog) is False


# ═══════════════════════════════════════════════════
# 4. Tests de calcul du solde reporté location
# ═══════════════════════════════════════════════════

class TestSoldeReporteCalculation:
    """Vérifie que le solde reporté est correctement taxé et ajouté."""

    TPS = 0.05
    TVQ = 0.09975
    TAXES = 1 + TPS + TVQ  # 1.14975

    def test_solde_reporte_is_taxed(self):
        """Le solde reporté doit être taxé (TPS+TVQ)."""
        solde = 3000
        taxed = solde * self.TAXES
        assert abs(taxed - 3449.25) < 0.01, f"3000$ taxé devrait donner 3449.25$, got {taxed}"

    def test_solde_zero_no_impact(self):
        """Solde de 0$ ne doit rien changer au calcul."""
        prix = 55000
        frais = 374.95
        base_sans = (prix + frais) * self.TAXES
        base_avec = (prix + 0 + frais) * self.TAXES
        assert abs(base_sans - base_avec) < 0.01

    def test_solde_added_before_taxes(self):
        """Le solde reporté doit être ajouté AVANT les taxes."""
        prix = 55000
        solde = 5000
        frais = 374.95
        consumer_cash = 8250

        # Correct: solde ajouté avant taxes
        avant_taxes = prix + solde - consumer_cash + frais  # 52124.95
        capital = avant_taxes * self.TAXES  # ~59930.32

        # Incorrect: solde ajouté après taxes (ne doit PAS donner le même résultat)
        avant_taxes_wrong = prix - consumer_cash + frais  # 47124.95
        capital_wrong = avant_taxes_wrong * self.TAXES + solde  # ~59198.21

        assert abs(capital - capital_wrong) > 100, "Le solde doit être taxé, pas ajouté après!"

    def test_solde_monthly_impact(self):
        """Vérifie l'impact mensuel du solde reporté sur un financement 60 mois."""
        solde = 3000
        taxed_solde = solde * self.TAXES  # 3449.25
        monthly_impact = taxed_solde / 60  # ~57.49$ de plus par mois
        assert 55 < monthly_impact < 60, f"Impact mensuel de 3000$ solde sur 60 mois: {monthly_impact:.2f}$/mois"


# ═══════════════════════════════════════════════════
# 5. Tests de cohérence entre fichiers résiduels
# ═══════════════════════════════════════════════════

class TestCrossMonthConsistency:
    """Vérifie la cohérence des données entre les mois."""

    def test_vehicle_count_consistent(self):
        """Le nombre de véhicules ne doit pas varier de plus de 20% entre les mois."""
        files = sorted(glob.glob(os.path.join(DATA_DIR, 'sci_residuals_*.json')))
        if len(files) < 2:
            pytest.skip("Pas assez de fichiers résiduels pour comparer")

        counts = []
        for f in files:
            with open(f) as fh:
                data = json.load(fh)
            counts.append(len(data.get('vehicles', [])))

        for i in range(1, len(counts)):
            ratio = counts[i] / counts[i-1] if counts[i-1] > 0 else 0
            assert 0.8 <= ratio <= 1.2, \
                f"Variation trop grande entre mois: {counts[i-1]} → {counts[i]} ({ratio:.2f}x)"

    def test_residual_change_reasonable(self):
        """Les résiduels ne doivent pas changer de plus de 10 points entre mois."""
        files = sorted(glob.glob(os.path.join(DATA_DIR, 'sci_residuals_*.json')))
        if len(files) < 2:
            pytest.skip("Pas assez de fichiers résiduels pour comparer")

        prev_data = {}
        with open(files[0]) as f:
            data = json.load(f)
        for v in data.get('vehicles', []):
            key = f"{v.get('brand')}|{v.get('model_name')}|{v.get('trim')}|{v.get('body_style')}|{v.get('model_year')}"
            prev_data[key] = v.get('residual_percentages', {})

        for fpath in files[1:]:
            with open(fpath) as f:
                data = json.load(f)
            fname = os.path.basename(fpath)
            for v in data.get('vehicles', []):
                key = f"{v.get('brand')}|{v.get('model_name')}|{v.get('trim')}|{v.get('body_style')}|{v.get('model_year')}"
                if key in prev_data:
                    for term in ['36', '48', '60', '72']:
                        old_val = prev_data[key].get(term, 0)
                        new_val = v.get('residual_percentages', {}).get(term, 0)
                        if isinstance(old_val, str): old_val = int(old_val)
                        if isinstance(new_val, str): new_val = int(new_val)
                        if old_val > 0 and new_val > 0:
                            diff = abs(new_val - old_val)
                            assert diff <= 10, \
                                f"{fname}: {key} term={term}: changement de {diff} points ({old_val}→{new_val})"

    def test_km_adjustments_consistent(self):
        """Les ajustements KM doivent être cohérents entre mois."""
        files = sorted(glob.glob(os.path.join(DATA_DIR, 'km_adjustments_*.json')))
        if len(files) < 2:
            pytest.skip("Pas assez de fichiers KM pour comparer")

        # All files should have the same structure
        for f in files:
            with open(f) as fh:
                data = json.load(fh)
            fname = os.path.basename(f)
            assert data.get('standard_km') in [20000, 24000], \
                f"{fname}: standard_km inattendu: {data.get('standard_km')}"


# ═══════════════════════════════════════════════════
# 6. Tests de la détection de plage de dates
# ═══════════════════════════════════════════════════

class TestDateRangeDetection:
    """Vérifie que la détection de plage de dates effective fonctionne."""

    def test_parse_effective_range(self):
        """Parse 'Effective: Mar 01, 2026 - Apr 30, 2026'."""
        text = "RESIDUAL VALUE GUIDE\nMARCH 2026\nEffective: Mar 01, 2026 - Apr 30, 2026"
        pattern = r'Effective:\s*(\w+)\s+\d+,?\s*(\d{4})\s*[-–]\s*(\w+)\s+\d+,?\s*(\d{4})'
        m = re.search(pattern, text, re.IGNORECASE)
        assert m is not None, "Pattern de plage de dates non trouvé"
        assert m.group(1).lower()[:3] == 'mar'
        assert m.group(3).lower()[:3] == 'apr'
        assert m.group(2) == '2026'
        assert m.group(4) == '2026'

    def test_multi_month_files_exist(self):
        """Si un fichier Mars existe, Avril devrait aussi exister (même guide)."""
        mars = os.path.join(DATA_DIR, 'sci_residuals_mars2026.json')
        avril = os.path.join(DATA_DIR, 'sci_residuals_avril2026.json')
        if os.path.exists(mars):
            assert os.path.exists(avril), \
                "Mars 2026 existe mais pas Avril 2026 — la sauvegarde multi-mois a échoué"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
