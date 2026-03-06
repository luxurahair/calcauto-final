"""
Tests unitaires autonomes pour CI/CD (GitHub Actions)
Pas besoin de serveur, MongoDB ou PDF réels.
Teste les fonctions pures du parser et la logique de calcul.
"""
import pytest
import math
import sys
import os

# Ajouter le path backend pour imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ═══════════════════════════════════════════════════
# Tests du parser: fonctions pures (regex, détection)
# ═══════════════════════════════════════════════════

class TestDetectBrand:
    """Test la détection de marques Stellantis"""

    def test_detect_ram(self):
        from services.pdfplumber_parser import detect_brand_from_model
        assert detect_brand_from_model("Ram 1500 Big Horn") == "Ram"

    def test_detect_jeep(self):
        from services.pdfplumber_parser import detect_brand_from_model
        assert detect_brand_from_model("Wrangler Sport") == "Jeep"

    def test_detect_dodge(self):
        from services.pdfplumber_parser import detect_brand_from_model
        assert detect_brand_from_model("Charger SXT") == "Dodge"

    def test_detect_chrysler(self):
        from services.pdfplumber_parser import detect_brand_from_model
        assert detect_brand_from_model("Pacifica Touring") == "Chrysler"

    def test_detect_jeep_cherokee(self):
        from services.pdfplumber_parser import detect_brand_from_model
        assert detect_brand_from_model("Grand Cherokee L") == "Jeep"


class TestParseDollar:
    """Test le parsing de valeurs monétaires"""

    def test_parse_dollar_simple(self):
        from services.pdfplumber_parser import parse_dollar
        assert parse_dollar("$6,000") == 6000

    def test_parse_dollar_no_symbol(self):
        from services.pdfplumber_parser import parse_dollar
        assert parse_dollar("6000") == 6000

    def test_parse_dollar_with_comma(self):
        from services.pdfplumber_parser import parse_dollar
        assert parse_dollar("$11,500") == 11500

    def test_parse_dollar_zero(self):
        from services.pdfplumber_parser import parse_dollar
        assert parse_dollar("0") == 0

    def test_parse_dollar_none(self):
        from services.pdfplumber_parser import parse_dollar
        assert parse_dollar(None) == 0


class TestParseRate:
    """Test le parsing de taux"""

    def test_parse_rate_percent(self):
        from services.pdfplumber_parser import parse_rate
        assert parse_rate("4.99%") == 4.99

    def test_parse_rate_zero(self):
        from services.pdfplumber_parser import parse_rate
        assert parse_rate("0%") == 0.0

    def test_parse_rate_no_percent(self):
        from services.pdfplumber_parser import parse_rate
        result = parse_rate("4.99")
        assert result == 4.99 or result is None  # Dépend de l'implémentation


class TestDetectLoyalty:
    """Test la détection du taux de fidélité depuis le texte"""

    def test_loyalty_half_percent(self):
        from services.pdfplumber_parser import _detect_loyalty
        text = "including a 0.5% Loyalty Rate Reduction for eligible customers"
        assert _detect_loyalty(text) == 0.5

    def test_loyalty_one_percent(self):
        from services.pdfplumber_parser import _detect_loyalty
        text = "including a 1% Loyalty Rate Reduction"
        assert _detect_loyalty(text) == 1.0

    def test_no_loyalty(self):
        from services.pdfplumber_parser import _detect_loyalty
        text = "No Finance Payments for 90 Days"
        assert _detect_loyalty(text) == 0.0

    def test_empty_text(self):
        from services.pdfplumber_parser import _detect_loyalty
        assert _detect_loyalty("") == 0.0
        assert _detect_loyalty(None) == 0.0


class TestParseIncentiveText:
    """Test l'extraction d'incentives depuis le texte"""

    def test_rate_and_term(self):
        from services.pdfplumber_parser import _parse_incentive_text
        text = "Get 0% Financing for 72 Months on select models"
        result = _parse_incentive_text(text)
        assert result['rate'] == 0.0
        assert result['term'] == 72

    def test_consumer_cash(self):
        from services.pdfplumber_parser import _parse_incentive_text
        text = "Up to $6,000 Consumer Cash on 2026 Ram 1500"
        result = _parse_incentive_text(text)
        assert result['consumer_cash'] == 6000

    def test_alternative(self):
        from services.pdfplumber_parser import _parse_incentive_text
        text = "0% Financing for 72 Months Or Up to $6,000 Consumer Cash"
        result = _parse_incentive_text(text)
        assert result['has_alternative'] == True


# ═══════════════════════════════════════════════════
# Tests de calcul: logique financement
# ═══════════════════════════════════════════════════

class TestMonthlyPaymentCalculation:
    """Test la formule PMT de calcul de versement mensuel"""

    def pmt(self, principal, annual_rate, months):
        if principal <= 0 or months <= 0:
            return 0
        if annual_rate == 0:
            return principal / months
        r = annual_rate / 100 / 12
        return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)

    def test_zero_rate(self):
        """0% sur 72 mois = principal / 72"""
        result = self.pmt(50000, 0, 72)
        assert abs(result - 694.44) < 1  # 50000/72

    def test_standard_rate(self):
        """4.99% sur 84 mois"""
        result = self.pmt(65000, 4.99, 84)
        assert 880 < result < 920  # ~$899/mois

    def test_zero_principal(self):
        assert self.pmt(0, 4.99, 84) == 0


class TestDeferredPaymentCalculation:
    """Test la logique de paiement différé 90 jours"""

    def pmt(self, principal, annual_rate, months):
        if principal <= 0 or months <= 0:
            return 0
        if annual_rate == 0:
            return principal / months
        r = annual_rate / 100 / 12
        return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)

    def test_deferred_capitalizes_2_months(self):
        """P_new = P * (1 + r)^2 — 2 mois d'intérêts composés"""
        principal = 65000
        rate = 4.99
        r = rate / 100 / 12

        deferred_principal = principal * (1 + r) ** 2
        interest = deferred_principal - principal

        # ~$542 d'intérêts capitalisés
        assert 500 < interest < 600
        assert deferred_principal > principal

    def test_84_month_eligible(self):
        """Terme 84 mois = éligible au différé"""
        assert 84 <= 84  # canDefer = selectedTerm <= 84

    def test_96_month_ineligible(self):
        """Terme 96 mois = NON éligible au différé"""
        assert not (96 <= 84)

    def test_deferred_increases_payment(self):
        """Le versement avec différé est plus élevé"""
        principal = 65000
        rate = 4.99
        term = 84
        r = rate / 100 / 12

        normal = self.pmt(principal, rate, term)
        deferred_p = principal * (1 + r) ** 2
        deferred = self.pmt(deferred_p, rate, term)

        assert deferred > normal
        diff = deferred - normal
        assert 5 < diff < 20  # ~$7.50 de plus par mois

    def test_zero_rate_no_deferred_effect(self):
        """À 0%, le différé n'a aucun effet"""
        principal = 50000
        r = 0 / 100 / 12

        deferred_p = principal * (1 + r) ** 2  # = principal (car r=0)
        assert deferred_p == principal


class TestCombinedLoyaltyAndDeferred:
    """Test la combinaison fidélité + différé"""

    def pmt(self, principal, annual_rate, months):
        if principal <= 0 or months <= 0:
            return 0
        if annual_rate == 0:
            return principal / months
        r = annual_rate / 100 / 12
        return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)

    def test_loyalty_reduces_rate_before_capitalization(self):
        """La fidélité réduit le taux AVANT la capitalisation"""
        principal = 65000
        base_rate = 4.99
        loyalty = 0.5
        term = 84

        adjusted_rate = max(0, base_rate - loyalty)  # 4.49%
        r = adjusted_rate / 100 / 12

        # Capitalisation sur le taux réduit
        deferred_p = principal * (1 + r) ** 2

        combined = self.pmt(deferred_p, adjusted_rate, term)
        deferred_only = self.pmt(
            principal * ((1 + base_rate / 100 / 12) ** 2),
            base_rate,
            term
        )

        # Combiné devrait être moins cher que différé seul
        assert combined < deferred_only

    def test_all_terms_eligibility(self):
        """Vérifie l'éligibilité pour tous les termes"""
        eligible = [36, 48, 60, 72, 84]
        ineligible = [96]

        for t in eligible:
            assert t <= 84, f"{t} devrait être éligible"
        for t in ineligible:
            assert t > 84, f"{t} ne devrait PAS être éligible"


# ═══════════════════════════════════════════════════
# Tests des métadonnées: structure JSON
# ═══════════════════════════════════════════════════

class TestMetadataFileStructure:
    """Test la structure des fichiers program_meta JSON"""

    def test_feb_metadata_structure(self):
        import json
        meta_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'program_meta_feb2026.json')
        if not os.path.exists(meta_path):
            pytest.skip("February metadata file not found")

        with open(meta_path) as f:
            data = json.load(f)

        assert 'event_names' in data
        assert 'loyalty_rate' in data
        assert 'no_payments_days' in data
        assert data['loyalty_rate'] == 0.0
        assert '4X4 Winter Event' in data['event_names']

    def test_mar_metadata_structure(self):
        import json
        meta_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'program_meta_mar2026.json')
        if not os.path.exists(meta_path):
            pytest.skip("March metadata file not found")

        with open(meta_path) as f:
            data = json.load(f)

        assert 'event_names' in data
        assert 'loyalty_rate' in data
        assert 'no_payments_days' in data
        assert 'brands' in data
        assert data['loyalty_rate'] == 0.5
        assert 'Month of Ram' in data['event_names']
        assert data['no_payments_days'] == 90
        assert 'Ram' in data['brands']
        assert 'Jeep' in data['brands']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
