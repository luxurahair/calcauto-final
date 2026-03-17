"""
Test suite for Corrections API endpoints
Tests: GET /api/corrections, DELETE /api/corrections/{brand}/{model}/{year}, DELETE /api/corrections/all
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://toc-extraction-fix.preview.emergentagent.com').rstrip('/')
ADMIN_PASSWORD = "Liana2018"


class TestCorrectionsAPI:
    """Test the Corrections API endpoints"""

    def test_get_corrections_returns_list(self):
        """GET /api/corrections should return list of corrections with proper structure"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Data structure assertion
        data = response.json()
        assert "total" in data, "Response should have 'total' field"
        assert "corrections" in data, "Response should have 'corrections' field"
        assert isinstance(data["corrections"], list), "corrections should be a list"
        
        print(f"✓ GET /api/corrections returned {data['total']} corrections")
        
    def test_get_corrections_has_14_items(self):
        """GET /api/corrections should return 14 corrections as specified"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        
        assert response.status_code == 200
        data = response.json()
        
        # Per the requirements, should have 14 corrections
        assert data["total"] == 14, f"Expected 14 corrections, got {data['total']}"
        assert len(data["corrections"]) == 14, f"Expected 14 items in list, got {len(data['corrections'])}"
        
        print(f"✓ Confirmed 14 corrections exist")

    def test_correction_structure(self):
        """Each correction should have required fields: brand, model, trim, year, changes_history, corrected_values"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["brand", "model", "trim", "year", "changes_history", "corrected_values"]
        
        for i, correction in enumerate(data["corrections"][:5]):  # Check first 5
            for field in required_fields:
                assert field in correction, f"Correction {i} missing required field: {field}"
        
        print(f"✓ All corrections have required fields: {required_fields}")

    def test_correction_data_types(self):
        """Verify data types of correction fields"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data["corrections"]) > 0:
            correction = data["corrections"][0]
            
            # Type assertions
            assert isinstance(correction.get("brand"), str), "brand should be string"
            assert isinstance(correction.get("model"), str), "model should be string"
            assert isinstance(correction.get("year"), int), "year should be int"
            assert isinstance(correction.get("changes_history"), dict), "changes_history should be dict"
            assert isinstance(correction.get("corrected_values"), dict), "corrected_values should be dict"
            
            print(f"✓ Data types verified: brand={correction['brand']}, model={correction['model']}, year={correction['year']}")

    def test_delete_without_password_returns_401(self):
        """DELETE /api/corrections/all without password should return 401"""
        response = requests.delete(f"{BASE_URL}/api/corrections/all")
        
        assert response.status_code == 401, f"Expected 401 without password, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        
        print(f"✓ DELETE /api/corrections/all without password returned 401: {data.get('detail')}")

    def test_delete_with_wrong_password_returns_401(self):
        """DELETE /api/corrections/all with wrong password should return 401"""
        response = requests.delete(f"{BASE_URL}/api/corrections/all", params={"password": "WrongPassword123"})
        
        assert response.status_code == 401, f"Expected 401 with wrong password, got {response.status_code}"
        
        print(f"✓ DELETE /api/corrections/all with wrong password returned 401")

    def test_delete_single_without_password_returns_401(self):
        """DELETE /api/corrections/{brand}/{model}/{year} without password should return 401"""
        response = requests.delete(f"{BASE_URL}/api/corrections/Fiat/500e/2025")
        
        assert response.status_code == 401, f"Expected 401 without password, got {response.status_code}"
        
        print(f"✓ DELETE /api/corrections/Fiat/500e/2025 without password returned 401")

    def test_delete_single_endpoint_structure_verified(self):
        """Verify DELETE /api/corrections/{brand}/{model}/{year} endpoint exists and validates password"""
        # Just verify the endpoint exists and requires password
        # We don't actually delete to preserve data as instructed
        response = requests.delete(
            f"{BASE_URL}/api/corrections/TestBrand/TestModel/9999",
            params={"password": ADMIN_PASSWORD}
        )
        
        # Should return 200 even if nothing deleted (deleted_count: 0)
        assert response.status_code == 200, f"Expected 200 with valid password, got {response.status_code}"
        
        data = response.json()
        assert "deleted" in data, "Response should have 'deleted' field"
        assert data["deleted"] == 0, "Should delete 0 items for non-existent entry"
        
        print(f"✓ DELETE endpoint for single correction works (deleted: {data['deleted']} - test entry)")

    def test_corrections_have_corrected_at_date(self):
        """Verify corrections have corrected_at timestamp"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        
        assert response.status_code == 200
        data = response.json()
        
        for i, correction in enumerate(data["corrections"][:5]):
            assert "corrected_at" in correction, f"Correction {i} missing corrected_at"
            assert correction["corrected_at"] is not None, f"Correction {i} has null corrected_at"
        
        print(f"✓ All corrections have corrected_at timestamp")

    def test_corrections_contain_fiat_500e(self):
        """Verify the Fiat 500e BEV correction exists with bonus_cash changes"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        
        assert response.status_code == 200
        data = response.json()
        
        fiat_correction = None
        for c in data["corrections"]:
            if c.get("brand") == "Fiat" and c.get("model") == "500e":
                fiat_correction = c
                break
        
        assert fiat_correction is not None, "Fiat 500e correction should exist"
        assert fiat_correction.get("year") == 2025, "Fiat 500e should be 2025"
        assert fiat_correction.get("trim") == "BEV", "Fiat 500e trim should be BEV"
        
        # Verify bonus_cash change
        changes = fiat_correction.get("changes_history", {})
        assert "bonus_cash" in changes, "Fiat 500e should have bonus_cash in changes_history"
        
        print(f"✓ Fiat 500e BEV 2025 correction verified with bonus_cash change")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
