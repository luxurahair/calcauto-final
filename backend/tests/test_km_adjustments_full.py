"""
Comprehensive tests for km_adjustments dynamic extraction feature.
Tests backend parsing, API endpoints, and integration.
"""

import pytest
import requests
import json
import os
from pathlib import Path

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://toc-extraction-fix.preview.emergentagent.com')

# ── Helpers ──

def _load_pdf(name: str) -> bytes:
    """Load a test PDF by name."""
    path = Path("/app") / name
    if not path.exists():
        pytest.skip(f"PDF not found: {path}")
    return path.read_bytes()


# ══════════════════════════════════════════════════════════════
# UNIT TESTS: _expand_term_range utility
# ══════════════════════════════════════════════════════════════

class TestExpandTermRange:
    """Tests for _expand_term_range utility function."""

    def test_24_27_range(self):
        """24-27 should expand to ['24', '27']"""
        from services.pdfplumber_parser import _expand_term_range
        result = _expand_term_range("24 – 27 months")
        assert result == ["24", "27"], f"Expected ['24', '27'], got {result}"

    def test_36_42_range(self):
        """36-42 should expand to ['36', '39', '42']"""
        from services.pdfplumber_parser import _expand_term_range
        result = _expand_term_range("36 – 42 months")
        assert result == ["36", "39", "42"], f"Expected ['36', '39', '42'], got {result}"

    def test_48_54_range(self):
        """48-54 should expand to ['48', '51', '54']"""
        from services.pdfplumber_parser import _expand_term_range
        result = _expand_term_range("48 – 54 months")
        assert result == ["48", "51", "54"], f"Expected ['48', '51', '54'], got {result}"

    def test_60_single(self):
        """60 months should return ['60']"""
        from services.pdfplumber_parser import _expand_term_range
        result = _expand_term_range("60 months")
        assert result == ["60"], f"Expected ['60'], got {result}"

    def test_dash_variant(self):
        """24-27 with regular dash should also work"""
        from services.pdfplumber_parser import _expand_term_range
        result = _expand_term_range("24-27 months")
        assert result == ["24", "27"], f"Expected ['24', '27'], got {result}"


# ══════════════════════════════════════════════════════════════
# UNIT TESTS: _parse_enhancement_value utility
# ══════════════════════════════════════════════════════════════

class TestParseEnhancementValue:
    """Tests for _parse_enhancement_value utility function."""

    def test_plus_1(self):
        """+1 should parse to 1"""
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("+1") == 1

    def test_plus_5(self):
        """+5 should parse to 5"""
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("+5") == 5

    def test_no_plus_sign(self):
        """3 without plus should parse to 3"""
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("3") == 3

    def test_empty_string(self):
        """Empty string should return None"""
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("") is None

    def test_none_input(self):
        """None input should return None"""
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value(None) is None


# ══════════════════════════════════════════════════════════════
# INTEGRATION TESTS: parse_general_rules on February PDF
# ══════════════════════════════════════════════════════════════

class TestParseGeneralRulesFebruary:
    """Tests for parse_general_rules on February 2026 PDF (pdf_source.pdf)."""

    @pytest.fixture
    def feb_pdf(self):
        return _load_pdf("pdf_source.pdf")

    def test_extraction_source_is_extracted(self, feb_pdf):
        """Source should be 'extracted' not 'default'"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        assert result["source"] == "extracted", f"Expected 'extracted', got {result['source']}"

    def test_has_18000_and_12000_adjustments(self, feb_pdf):
        """Should have both 18000 and 12000 km adjustments"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        adj = result["adjustments"]
        assert "18000" in adj, "Missing 18000 km adjustments"
        assert "12000" in adj, "Missing 12000 km adjustments"

    def test_18k_has_all_9_terms(self, feb_pdf):
        """18000 km should have all 9 terms: 24,27,36,39,42,48,51,54,60"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(result["adjustments"]["18000"].keys())
        assert actual_terms == expected_terms, f"Expected {expected_terms}, got {actual_terms}"

    def test_12k_has_all_9_terms(self, feb_pdf):
        """12000 km should have all 9 terms: 24,27,36,39,42,48,51,54,60"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(result["adjustments"]["12000"].keys())
        assert actual_terms == expected_terms, f"Expected {expected_terms}, got {actual_terms}"

    def test_18k_correct_values(self, feb_pdf):
        """18000 km values should match expected: 24:1, 27:1, 36:2, 39:2, 42:2, 48:3, 51:3, 54:3, 60:4"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        low = result["adjustments"]["18000"]
        expected = {"24": 1, "27": 1, "36": 2, "39": 2, "42": 2, "48": 3, "51": 3, "54": 3, "60": 4}
        for term, val in expected.items():
            assert low[term] == val, f"18k term {term}: expected {val}, got {low[term]}"

    def test_12k_correct_values(self, feb_pdf):
        """12000 km values should match expected: 24:2, 27:2, 36:3, 39:3, 42:3, 48:4, 51:4, 54:4, 60:5"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        super_low = result["adjustments"]["12000"]
        expected = {"24": 2, "27": 2, "36": 3, "39": 3, "42": 3, "48": 4, "51": 4, "54": 4, "60": 5}
        for term, val in expected.items():
            assert super_low[term] == val, f"12k term {term}: expected {val}, got {super_low[term]}"


# ══════════════════════════════════════════════════════════════
# INTEGRATION TESTS: parse_general_rules on March PDF
# ══════════════════════════════════════════════════════════════

class TestParseGeneralRulesMarch:
    """Tests for parse_general_rules on March 2026 PDF (march_2026.pdf)."""

    @pytest.fixture
    def march_pdf(self):
        return _load_pdf("march_2026.pdf")

    def test_extraction_source_is_extracted(self, march_pdf):
        """Source should be 'extracted' not 'default'"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(march_pdf)
        assert result["source"] == "extracted", f"Expected 'extracted', got {result['source']}"

    def test_march_has_all_9_terms_18k(self, march_pdf):
        """March PDF 18000 km should have all 9 terms"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(march_pdf)
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(result["adjustments"]["18000"].keys())
        assert actual_terms == expected_terms, f"Expected {expected_terms}, got {actual_terms}"

    def test_march_has_all_9_terms_12k(self, march_pdf):
        """March PDF 12000 km should have all 9 terms"""
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(march_pdf)
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(result["adjustments"]["12000"].keys())
        assert actual_terms == expected_terms, f"Expected {expected_terms}, got {actual_terms}"


# ══════════════════════════════════════════════════════════════
# API TESTS: GET /api/sci/residuals
# ══════════════════════════════════════════════════════════════

class TestSciResidualsAPI:
    """Tests for GET /api/sci/residuals endpoint."""

    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_response_has_km_adjustments(self):
        """Response should contain km_adjustments key"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        assert "km_adjustments" in data, "Missing km_adjustments in response"

    def test_km_adjustments_has_adjustments_key(self):
        """km_adjustments should have 'adjustments' sub-key"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        km_adj = data.get("km_adjustments", {})
        assert "adjustments" in km_adj, f"Missing 'adjustments' in km_adjustments: {km_adj.keys()}"

    def test_adjustments_has_18000(self):
        """adjustments should have '18000' key"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        adj = data.get("km_adjustments", {}).get("adjustments", {})
        assert "18000" in adj, f"Missing '18000' in adjustments: {adj.keys()}"

    def test_adjustments_has_12000(self):
        """adjustments should have '12000' key"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        adj = data.get("km_adjustments", {}).get("adjustments", {})
        assert "12000" in adj, f"Missing '12000' in adjustments: {adj.keys()}"

    def test_18000_has_9_terms(self):
        """18000 km adjustments should have 9 terms"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        adj_18k = data.get("km_adjustments", {}).get("adjustments", {}).get("18000", {})
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(adj_18k.keys())
        assert actual_terms == expected_terms, f"Expected {expected_terms}, got {actual_terms}"

    def test_12000_has_9_terms(self):
        """12000 km adjustments should have 9 terms"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        adj_12k = data.get("km_adjustments", {}).get("adjustments", {}).get("12000", {})
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(adj_12k.keys())
        assert actual_terms == expected_terms, f"Expected {expected_terms}, got {actual_terms}"

    def test_18k_60_months_equals_4(self):
        """18000 km at 60 months should equal 4"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        val = data.get("km_adjustments", {}).get("adjustments", {}).get("18000", {}).get("60")
        assert val == 4, f"Expected 4, got {val}"

    def test_12k_60_months_equals_5(self):
        """12000 km at 60 months should equal 5"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        val = data.get("km_adjustments", {}).get("adjustments", {}).get("12000", {}).get("60")
        assert val == 5, f"Expected 5, got {val}"


# ══════════════════════════════════════════════════════════════
# DEFAULT FALLBACK TESTS
# ══════════════════════════════════════════════════════════════

class TestDefaultKmAdjustments:
    """Tests for DEFAULT_KM_ADJUSTMENTS fallback values."""

    def test_defaults_have_18000(self):
        """DEFAULT_KM_ADJUSTMENTS should have 18000"""
        from services.pdfplumber_parser import DEFAULT_KM_ADJUSTMENTS
        assert "18000" in DEFAULT_KM_ADJUSTMENTS

    def test_defaults_have_12000(self):
        """DEFAULT_KM_ADJUSTMENTS should have 12000"""
        from services.pdfplumber_parser import DEFAULT_KM_ADJUSTMENTS
        assert "12000" in DEFAULT_KM_ADJUSTMENTS

    def test_defaults_18k_has_all_terms(self):
        """DEFAULT_KM_ADJUSTMENTS 18000 should have all 9 terms"""
        from services.pdfplumber_parser import DEFAULT_KM_ADJUSTMENTS
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(DEFAULT_KM_ADJUSTMENTS["18000"].keys())
        assert actual_terms == expected_terms

    def test_defaults_12k_has_all_terms(self):
        """DEFAULT_KM_ADJUSTMENTS 12000 should have all 9 terms"""
        from services.pdfplumber_parser import DEFAULT_KM_ADJUSTMENTS
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        actual_terms = set(DEFAULT_KM_ADJUSTMENTS["12000"].keys())
        assert actual_terms == expected_terms
