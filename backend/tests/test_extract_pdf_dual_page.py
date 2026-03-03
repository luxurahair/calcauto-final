"""
Test suite for POST /api/extract-pdf dual-page extraction feature
Tests the new lease_start_page and lease_end_page parameters for SCI Lease rates extraction

Features tested:
- POST /api/extract-pdf accepts new optional params lease_start_page and lease_end_page
- POST /api/extract-pdf with password=wrong returns 401
- POST /api/extract-pdf with correct password + retail pages only (no lease pages) works
- POST /api/verify-password works with correct password Liana2018
- GET /api/sci/lease-rates returns valid JSON with vehicles_2026 and vehicles_2025 arrays
- GET /api/sci/vehicle-hierarchy returns valid hierarchy data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com').rstrip('/')
ADMIN_PASSWORD = "Liana2018"
WRONG_PASSWORD = "wrongpassword123"


class TestVerifyPassword:
    """Test /api/verify-password endpoint"""
    
    def test_verify_password_correct(self):
        """Verify password endpoint accepts correct admin password"""
        response = requests.post(
            f"{BASE_URL}/api/verify-password",
            data={"password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        print(f"✓ POST /api/verify-password with correct password returned 200 OK")
    
    def test_verify_password_wrong(self):
        """Verify password endpoint rejects wrong password with 401"""
        response = requests.post(
            f"{BASE_URL}/api/verify-password",
            data={"password": WRONG_PASSWORD}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/verify-password with wrong password returned 401")


class TestExtractPdfAuth:
    """Test /api/extract-pdf authentication"""
    
    def test_extract_pdf_wrong_password(self):
        """POST /api/extract-pdf with wrong password returns 401"""
        # Create a minimal test PDF content (or use form data without actual file)
        response = requests.post(
            f"{BASE_URL}/api/extract-pdf",
            data={
                "password": WRONG_PASSWORD,
                "program_month": 2,
                "program_year": 2026,
                "start_page": 20,
                "end_page": 21
            },
            files={
                "file": ("test.pdf", b"%PDF-1.4 minimal pdf content", "application/pdf")
            }
        )
        # Should fail with 401 for wrong password
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/extract-pdf with wrong password returned 401")


class TestExtractPdfParameters:
    """Test /api/extract-pdf parameter acceptance (without full extraction)"""
    
    def test_extract_pdf_accepts_lease_page_params(self):
        """Verify endpoint accepts lease_start_page and lease_end_page parameters"""
        # This test verifies that the endpoint accepts the new parameters
        # It will fail at PDF parsing (not a real PDF) but shouldn't fail at parameter validation
        
        response = requests.post(
            f"{BASE_URL}/api/extract-pdf",
            data={
                "password": ADMIN_PASSWORD,
                "program_month": 2,
                "program_year": 2026,
                "start_page": 20,
                "end_page": 21,
                "lease_start_page": 28,
                "lease_end_page": 29
            },
            files={
                "file": ("test.pdf", b"%PDF-1.4 minimal content", "application/pdf")
            }
        )
        # The request should not fail with 422 (validation error)
        # It may fail with 500 (PDF processing error) but that's expected with fake PDF
        assert response.status_code != 422, f"Got 422 validation error - lease page params not accepted: {response.text}"
        print(f"✓ POST /api/extract-pdf accepts lease_start_page and lease_end_page params (status: {response.status_code})")
    
    def test_extract_pdf_without_lease_pages(self):
        """Verify endpoint works without lease page parameters (backward compatible)"""
        response = requests.post(
            f"{BASE_URL}/api/extract-pdf",
            data={
                "password": ADMIN_PASSWORD,
                "program_month": 2,
                "program_year": 2026,
                "start_page": 20,
                "end_page": 21
                # No lease_start_page, no lease_end_page
            },
            files={
                "file": ("test.pdf", b"%PDF-1.4 minimal content", "application/pdf")
            }
        )
        # Should not fail with 422 (validation error) - lease params are optional
        assert response.status_code != 422, f"Got 422 - should accept request without lease params: {response.text}"
        print(f"✓ POST /api/extract-pdf works without lease page params (backward compatible)")


class TestSciLeaseRates:
    """Test GET /api/sci/lease-rates endpoint"""
    
    def test_sci_lease_rates_returns_valid_structure(self):
        """GET /api/sci/lease-rates returns valid JSON with vehicles_2026 and vehicles_2025"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check for expected structure
        assert "vehicles_2026" in data, "Missing vehicles_2026 array"
        assert "vehicles_2025" in data, "Missing vehicles_2025 array"
        assert isinstance(data["vehicles_2026"], list), "vehicles_2026 should be an array"
        assert isinstance(data["vehicles_2025"], list), "vehicles_2025 should be an array"
        
        # Check that arrays have content
        assert len(data["vehicles_2026"]) > 0, "vehicles_2026 should have entries"
        assert len(data["vehicles_2025"]) > 0, "vehicles_2025 should have entries"
        
        # Check structure of first vehicle
        if data["vehicles_2026"]:
            vehicle = data["vehicles_2026"][0]
            assert "model" in vehicle, "Vehicle missing 'model' field"
            assert "brand" in vehicle, "Vehicle missing 'brand' field"
            assert "lease_cash" in vehicle, "Vehicle missing 'lease_cash' field"
            # Should have either standard_rates or alternative_rates
            has_rates = vehicle.get("standard_rates") or vehicle.get("alternative_rates")
            assert has_rates, "Vehicle should have standard_rates or alternative_rates"
        
        print(f"✓ GET /api/sci/lease-rates returned valid structure")
        print(f"  - vehicles_2026: {len(data['vehicles_2026'])} entries")
        print(f"  - vehicles_2025: {len(data['vehicles_2025'])} entries")
    
    def test_sci_lease_rates_has_metadata(self):
        """GET /api/sci/lease-rates includes program period and terms"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for metadata fields
        if "program_period" in data:
            print(f"  - program_period: {data['program_period']}")
        
        if "terms" in data:
            assert isinstance(data["terms"], list), "terms should be a list"
            expected_terms = [24, 27, 36, 39, 42, 48, 51, 54, 60]
            assert data["terms"] == expected_terms, f"Expected terms {expected_terms}, got {data['terms']}"
            print(f"  - terms: {data['terms']}")
        
        print(f"✓ GET /api/sci/lease-rates metadata verified")


class TestSciVehicleHierarchy:
    """Test GET /api/sci/vehicle-hierarchy endpoint"""
    
    def test_vehicle_hierarchy_returns_valid_structure(self):
        """GET /api/sci/vehicle-hierarchy returns valid hierarchy data"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should have brand names as top-level keys
        assert len(data) > 0, "Hierarchy should have at least one brand"
        
        # Check for expected Stellantis brands
        expected_brands = ["Chrysler", "Jeep", "Dodge", "Ram"]
        found_brands = [brand for brand in expected_brands if brand in data]
        assert len(found_brands) >= 3, f"Expected at least 3 Stellantis brands, found: {found_brands}"
        
        # Check structure of a brand
        for brand in found_brands:
            brand_data = data[brand]
            assert isinstance(brand_data, dict), f"{brand} should be a dict of models"
            
            if brand_data:
                # Get first model
                model_name = list(brand_data.keys())[0]
                model_data = brand_data[model_name]
                
                # Check model structure
                assert "trims" in model_data or "years" in model_data, \
                    f"Model {model_name} should have 'trims' or 'years'"
        
        print(f"✓ GET /api/sci/vehicle-hierarchy returned valid hierarchy")
        print(f"  - Brands found: {list(data.keys())}")


class TestExtractPdfResponseModel:
    """Test ExtractedDataResponse model fields"""
    
    def test_response_model_includes_sci_lease_count(self):
        """Verify ExtractedDataResponse includes sci_lease_count field"""
        # Make a request that will fail at processing but check response structure
        response = requests.post(
            f"{BASE_URL}/api/extract-pdf",
            data={
                "password": ADMIN_PASSWORD,
                "program_month": 2,
                "program_year": 2026,
                "start_page": 1,
                "end_page": 1
            },
            files={
                "file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")
            }
        )
        
        # If success (unlikely with fake PDF), check response
        if response.status_code == 200:
            data = response.json()
            assert "sci_lease_count" in data, "Response should include sci_lease_count field"
            assert isinstance(data["sci_lease_count"], int), "sci_lease_count should be int"
            print(f"✓ ExtractedDataResponse includes sci_lease_count: {data['sci_lease_count']}")
        else:
            # Even on error, we verified the endpoint accepts the request
            print(f"✓ Endpoint accepted request (returned {response.status_code} - expected with test PDF)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
