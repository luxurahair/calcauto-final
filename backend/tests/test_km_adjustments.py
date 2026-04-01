"""
Tests pour l'extraction dynamique des ajustements de kilométrage (km_adjustments)
depuis la section General Rules des PDFs mensuels Stellantis.
"""

import pytest
import json
from pathlib import Path

# ── Helpers ──

def _load_pdf(name: str) -> bytes:
    """Load a test PDF by name."""
    path = Path("/app") / name
    if not path.exists():
        pytest.skip(f"PDF not found: {path}")
    return path.read_bytes()


# ── Unit Tests: utility functions ──

class TestTermExpansion:
    """Tests for _expand_term_range."""

    def test_24_27(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("24 – 27 months") == ["24", "27"]

    def test_36_42(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("36 – 42 months") == ["36", "39", "42"]

    def test_48_54(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("48 – 54 months") == ["48", "51", "54"]

    def test_60_single(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("60 months") == ["60"]

    def test_60_no_suffix(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("60") == ["60"]

    def test_dash_variant(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("24-27 months") == ["24", "27"]

    def test_empty(self):
        from services.pdfplumber_parser import _expand_term_range
        assert _expand_term_range("") == []


class TestEnhancementParsing:
    """Tests for _parse_enhancement_value."""

    def test_plus_1(self):
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("+1") == 1

    def test_plus_5(self):
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("+5") == 5

    def test_no_plus(self):
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("3") == 3

    def test_empty(self):
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value("") is None

    def test_none(self):
        from services.pdfplumber_parser import _parse_enhancement_value
        assert _parse_enhancement_value(None) is None


# ── Integration Tests: full PDF parsing ──

class TestParseGeneralRules:
    """Tests for parse_general_rules on real PDFs."""

    @pytest.fixture
    def feb_pdf(self):
        return _load_pdf("pdf_source.pdf")

    @pytest.fixture
    def march_pdf(self):
        return _load_pdf("march_2026.pdf")

    def test_feb_extraction_source(self, feb_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        assert result["source"] == "extracted"

    def test_feb_has_both_km_types(self, feb_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        adj = result["adjustments"]
        assert "18000" in adj
        assert "12000" in adj

    def test_feb_18k_values(self, feb_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        low = result["adjustments"]["18000"]
        assert low["24"] == 1
        assert low["27"] == 1
        assert low["36"] == 2
        assert low["39"] == 2
        assert low["42"] == 2
        assert low["48"] == 3
        assert low["51"] == 3
        assert low["54"] == 3
        assert low["60"] == 4

    def test_feb_12k_values(self, feb_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        super_low = result["adjustments"]["12000"]
        assert super_low["24"] == 2
        assert super_low["27"] == 2
        assert super_low["36"] == 3
        assert super_low["39"] == 3
        assert super_low["42"] == 3
        assert super_low["48"] == 4
        assert super_low["51"] == 4
        assert super_low["54"] == 4
        assert super_low["60"] == 5

    def test_feb_standard_km(self, feb_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(feb_pdf)
        assert result["standard_km"] == 24000

    def test_march_extraction_source(self, march_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(march_pdf)
        assert result["source"] == "extracted"

    def test_march_all_terms_covered(self, march_pdf):
        from services.pdfplumber_parser import parse_general_rules
        result = parse_general_rules(march_pdf)
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        assert set(result["adjustments"]["18000"].keys()) == expected_terms
        assert set(result["adjustments"]["12000"].keys()) == expected_terms


class TestDefaultFallback:
    """Tests that DEFAULT_KM_ADJUSTMENTS is valid."""

    def test_defaults_structure(self):
        from services.pdfplumber_parser import DEFAULT_KM_ADJUSTMENTS
        assert "18000" in DEFAULT_KM_ADJUSTMENTS
        assert "12000" in DEFAULT_KM_ADJUSTMENTS
        expected_terms = {"24", "27", "36", "39", "42", "48", "51", "54", "60"}
        assert set(DEFAULT_KM_ADJUSTMENTS["18000"].keys()) == expected_terms
        assert set(DEFAULT_KM_ADJUSTMENTS["12000"].keys()) == expected_terms
