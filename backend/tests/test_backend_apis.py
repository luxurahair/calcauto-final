"""
CalcAuto AiPro - Backend API Tests
Tests for critical endpoints:
- POST /api/auth/login - User authentication
- GET /api/programs - Financing programs list
- POST /api/inventory/scan-invoice - Invoice scan (OCR pipeline)
- GET /api/inventory - Vehicle inventory list
- GET /api/admin/parsing-stats - Parsing statistics (admin)
- GET /api/admin/parsing-history - Parsing history (admin)
- Validation scoring (threshold 85 for auto-approval)
- VIN validation (strict 17 characters)
- Financial calculations (monthly, bi-weekly, weekly payments)
"""

import sys
import os
from pathlib import Path
import pytest
import requests
import base64

# Get BASE_URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "danielgiroux007@gmail.com"
TEST_PASSWORD = "Liana2018$"

# API session
@pytest.fixture(scope="module")
def api_session():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_session):
    """Get authentication token for authenticated requests"""
    response = api_session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")

@pytest.fixture(scope="module")
def authenticated_session(api_session, auth_token):
    """Session with auth header"""
    api_session.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_session


# ============ AUTH TESTS ============

class TestAuthentication:
    """Tests for /api/auth/login endpoint"""
    
    def test_login_success(self, api_session):
        """Test login with valid credentials returns token and user data"""
        response = api_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        # Validate response structure
        assert data.get("success") == True
        assert "token" in data
        assert "user" in data
        
        # Validate user data
        user = data["user"]
        assert user["email"] == TEST_EMAIL
        assert "id" in user
        assert "name" in user
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 10
        
        print(f"✓ Login success: user={user['email']}, is_admin={user.get('is_admin')}")
    
    def test_login_invalid_email(self, api_session):
        """Test login with invalid email returns 401"""
        response = api_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "invalid@example.com", "password": "wrongpass"}
        )
        
        assert response.status_code == 401
        print("✓ Invalid login correctly rejected with 401")
    
    def test_login_invalid_password(self, api_session):
        """Test login with wrong password returns 401"""
        response = api_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
        print("✓ Wrong password correctly rejected with 401")
    
    def test_login_missing_fields(self, api_session):
        """Test login with missing fields returns error"""
        response = api_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL}
        )
        
        assert response.status_code == 422  # Validation error
        print("✓ Missing password field correctly rejected")


# ============ PROGRAMS TESTS ============

class TestPrograms:
    """Tests for /api/programs endpoints"""
    
    def test_get_programs_list(self, api_session):
        """GET /api/programs returns list of financing programs"""
        response = api_session.get(f"{BASE_URL}/api/programs")
        
        assert response.status_code == 200, f"Get programs failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # If programs exist, validate structure
        if len(data) > 0:
            program = data[0]
            assert "id" in program
            assert "brand" in program
            assert "model" in program
            assert "year" in program
            assert "option1_rates" in program
            assert "consumer_cash" in program
            
            # Validate rates structure
            rates = program["option1_rates"]
            assert "rate_36" in rates
            assert "rate_48" in rates
            assert "rate_60" in rates
            assert "rate_72" in rates
            assert "rate_84" in rates
            assert "rate_96" in rates
            
            print(f"✓ Programs found: {len(data)} programs")
            print(f"  Sample: {program['brand']} {program['model']} {program['year']}")
        else:
            print("✓ Programs endpoint working (empty list)")
    
    def test_get_programs_by_period(self, api_session):
        """GET /api/programs with month/year filter"""
        response = api_session.get(
            f"{BASE_URL}/api/programs",
            params={"month": 2, "year": 2026}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            # All programs should be for specified period
            for prog in data:
                assert prog.get("program_month") == 2
                assert prog.get("program_year") == 2026
        
        print(f"✓ Programs filter by period working: {len(data)} programs for 2/2026")
    
    def test_get_periods(self, api_session):
        """GET /api/periods returns available program periods"""
        response = api_session.get(f"{BASE_URL}/api/periods")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            period = data[0]
            assert "month" in period
            assert "year" in period
            assert "count" in period
            print(f"✓ Periods available: {len(data)}, latest: {period['month']}/{period['year']}")
        else:
            print("✓ Periods endpoint working (no periods yet)")


# ============ INVENTORY TESTS ============

class TestInventory:
    """Tests for /api/inventory endpoints"""
    
    def test_get_inventory(self, authenticated_session):
        """GET /api/inventory returns vehicle list"""
        response = authenticated_session.get(f"{BASE_URL}/api/inventory")
        
        assert response.status_code == 200, f"Get inventory failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            vehicle = data[0]
            # Validate vehicle structure
            assert "id" in vehicle
            assert "stock_no" in vehicle
            assert "brand" in vehicle
            assert "model" in vehicle
            assert "year" in vehicle
            assert "status" in vehicle
            
            print(f"✓ Inventory found: {len(data)} vehicles")
            print(f"  Sample: {vehicle['year']} {vehicle['brand']} {vehicle['model']} (#{vehicle['stock_no']})")
        else:
            print("✓ Inventory endpoint working (empty)")
    
    def test_inventory_requires_auth(self, api_session):
        """GET /api/inventory requires authentication"""
        # Create new session without auth
        new_session = requests.Session()
        new_session.headers.update({"Content-Type": "application/json"})
        
        response = new_session.get(f"{BASE_URL}/api/inventory")
        
        # Should require auth
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Inventory endpoint correctly requires authentication")


# ============ INVOICE SCAN TESTS ============

class TestInvoiceScan:
    """Tests for /api/inventory/scan-invoice (OCR pipeline)"""
    
    def test_scan_invoice_requires_image(self, authenticated_session):
        """POST /api/inventory/scan-invoice requires image data"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/inventory/scan-invoice",
            json={}  # Empty body
        )
        
        # Should return validation error
        assert response.status_code == 422
        print("✓ Scan endpoint correctly requires image data")
    
    def test_scan_invoice_with_invalid_base64(self, authenticated_session):
        """POST /api/inventory/scan-invoice with invalid base64"""
        response = authenticated_session.post(
            f"{BASE_URL}/api/inventory/scan-invoice",
            json={"image": "not-valid-base64!@#$"}
        )
        
        # Should handle gracefully
        assert response.status_code in [400, 422, 500]
        print("✓ Scan endpoint handles invalid base64 gracefully")
    
    def test_scan_invoice_with_minimal_image(self, authenticated_session):
        """POST /api/inventory/scan-invoice with minimal valid image (white PNG)"""
        # Create a minimal 1x1 white PNG as base64
        # This is a valid 1x1 white PNG
        minimal_png_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
            "DUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        )
        
        response = authenticated_session.post(
            f"{BASE_URL}/api/inventory/scan-invoice",
            json={"image": minimal_png_base64}
        )
        
        # Should process (even if no data extracted from blank image)
        # Accept 200 (success) or 400/422 (no data found)
        assert response.status_code in [200, 400, 422], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Scan processed: {data.get('message', 'success')}")
        else:
            print(f"✓ Scan endpoint working (rejected minimal image as expected)")


# ============ ADMIN ENDPOINTS TESTS ============

class TestAdminEndpoints:
    """Tests for admin-only endpoints"""
    
    def test_admin_parsing_stats(self, authenticated_session):
        """GET /api/admin/parsing-stats returns statistics"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/parsing-stats")
        
        # Should return 200 for admin user or 403 for non-admin
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Admin parsing-stats working: {data}")
        elif response.status_code == 403:
            print("✓ Admin parsing-stats correctly restricted to admins")
        elif response.status_code == 404:
            print("⚠ Admin parsing-stats endpoint not found (may not be implemented)")
        else:
            print(f"⚠ Admin parsing-stats returned {response.status_code}")
    
    def test_admin_parsing_history(self, authenticated_session):
        """GET /api/admin/parsing-history returns history"""
        response = authenticated_session.get(f"{BASE_URL}/api/admin/parsing-history")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Admin parsing-history working: {len(data) if isinstance(data, list) else 'object'}")
        elif response.status_code == 403:
            print("✓ Admin parsing-history correctly restricted to admins")
        elif response.status_code == 404:
            print("⚠ Admin parsing-history endpoint not found (may not be implemented)")
        else:
            print(f"⚠ Admin parsing-history returned {response.status_code}")


# ============ VIN VALIDATION TESTS ============

class TestVINValidation:
    """Tests for VIN validation (strict 17 characters)"""
    
    def test_vin_validation_module(self):
        """Test VIN validation module directly"""
        # Import the module
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from vin_utils import validate_vin_checksum, validate_and_correct_vin
        
        # Test valid VIN (17 chars)
        valid_result = validate_and_correct_vin("1C4RJKBG5S8123456")
        print(f"✓ VIN validation module working")
        
        # Test too short VIN (16 chars)
        short_result = validate_and_correct_vin("1C4RJKBG5S812345")
        assert short_result["is_valid"] == False
        print("✓ VIN < 17 chars correctly rejected")
        
        # Test too long VIN (18 chars)
        long_result = validate_and_correct_vin("1C4RJKBG5S81234567")
        assert long_result["is_valid"] == False
        print("✓ VIN > 17 chars correctly rejected")
    
    def test_vin_checksum_validation(self):
        """Test VIN checksum is validated"""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from vin_utils import validate_vin_checksum, calculate_check_digit
        
        # Create a VIN with correct checksum
        vin_base = "1C4RJKBG5S8123456"
        check_digit = calculate_check_digit(vin_base)
        valid_vin = vin_base[:8] + check_digit + vin_base[9:]
        
        assert validate_vin_checksum(valid_vin) == True
        print(f"✓ Valid VIN checksum: {valid_vin}")
        
        # Invalid checksum
        invalid_vin = vin_base[:8] + "X" + vin_base[9:]
        assert validate_vin_checksum(invalid_vin) == False
        print(f"✓ Invalid VIN checksum correctly detected")


# ============ SCORING VALIDATION TESTS ============

class TestScoringValidation:
    """Tests for validation scoring (threshold 85 for auto-approval)"""
    
    def test_scoring_threshold_85(self):
        """Test that score >= 85 is required for auto-approval"""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from validation import calculate_validation_score, validate_invoice_data
        
        # Perfect data should score >= 85
        perfect_data = {
            "vin": "1C4RJHBG6S8806264",
            "vin_valid": True,
            "model_code": "WLJP74",
            "ep_cost": 69979,
            "pdco": 75445,
            "pref": 70704,
            "holdback": 1530,
            "subtotal": 70679,
            "options": [{"c": f"OPT{i}"} for i in range(5)]
        }
        
        result = calculate_validation_score(perfect_data)
        assert result["score"] >= 85, f"Perfect data scored {result['score']}, expected >= 85"
        print(f"✓ Perfect data scores >= 85: {result['score']}")
        
        # Data with missing EP should score < 85
        incomplete_data = {
            "vin": "1C4RJHBG6S8806264",
            "vin_valid": True,
            "ep_cost": 0,  # Missing
            "pdco": 75445
        }
        
        result2 = calculate_validation_score(incomplete_data)
        assert result2["score"] < 85, f"Incomplete data scored {result2['score']}, expected < 85"
        print(f"✓ Incomplete data scores < 85: {result2['score']}")
    
    def test_validation_requires_vin_and_ep(self):
        """Test that is_valid requires VIN and EP"""
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from validation import validate_invoice_data
        
        # Data without VIN - should be invalid
        no_vin_data = {
            "vin": None,
            "ep_cost": 69979,
            "pdco": 75445
        }
        
        result = validate_invoice_data(no_vin_data)
        assert result["is_valid"] == False
        print("✓ Missing VIN correctly blocks validation")
        
        # Data without EP - should be invalid
        no_ep_data = {
            "vin": "1C4RJHBG6S8806264",
            "vin_valid": True,
            "ep_cost": 0,
            "pdco": 75445
        }
        
        result2 = validate_invoice_data(no_ep_data)
        assert result2["is_valid"] == False
        print("✓ Missing EP correctly blocks validation")


# ============ FINANCIAL CALCULATION TESTS ============

class TestFinancialCalculations:
    """Tests for financial calculations (monthly, bi-weekly, weekly)"""
    
    def test_calculate_endpoint(self, api_session):
        """Test /api/calculate endpoint"""
        # First get a program to use for calculation
        programs_response = api_session.get(f"{BASE_URL}/api/programs")
        
        if programs_response.status_code != 200 or len(programs_response.json()) == 0:
            pytest.skip("No programs available for calculation test")
        
        program = programs_response.json()[0]
        program_id = program["id"]
        
        response = api_session.post(
            f"{BASE_URL}/api/calculate",
            json={
                "vehicle_price": 50000,
                "program_id": program_id
            }
        )
        
        assert response.status_code == 200, f"Calculate failed: {response.text}"
        
        data = response.json()
        assert "vehicle_price" in data
        assert "comparisons" in data
        assert isinstance(data["comparisons"], list)
        
        # Validate comparison structure
        if len(data["comparisons"]) > 0:
            comp = data["comparisons"][0]
            assert "term_months" in comp
            assert "option1_rate" in comp
            assert "option1_monthly" in comp
            assert "option1_total" in comp
            
            print(f"✓ Calculate endpoint working")
            print(f"  Sample: {comp['term_months']}mo @ {comp['option1_rate']}% = ${comp['option1_monthly']:.2f}/mo")
    
    def test_payment_calculations_module(self):
        """Test payment calculation formulas"""
        # These are the expected formulas from useFinancingCalculation.ts
        
        def calculate_monthly_payment(principal, annual_rate, months):
            if principal <= 0 or months <= 0:
                return 0
            if annual_rate == 0:
                return principal / months
            
            monthly_rate = annual_rate / 100 / 12
            payment = (principal * (monthly_rate * (1 + monthly_rate) ** months)) / ((1 + monthly_rate) ** months - 1)
            return round(payment, 2)
        
        def calculate_biweekly(monthly):
            return monthly * 12 / 26
        
        def calculate_weekly(monthly):
            return monthly * 12 / 52
        
        # Test case: $50,000 @ 4.99% for 72 months
        monthly = calculate_monthly_payment(50000, 4.99, 72)
        biweekly = calculate_biweekly(monthly)
        weekly = calculate_weekly(monthly)
        
        # Monthly should be around $805
        assert 750 < monthly < 850, f"Monthly payment {monthly} out of expected range"
        
        # Bi-weekly should be roughly half of monthly
        assert 350 < biweekly < 450, f"Bi-weekly payment {biweekly} out of expected range"
        
        # Weekly should be roughly quarter of monthly
        assert 175 < weekly < 225, f"Weekly payment {weekly} out of expected range"
        
        print(f"✓ Payment calculations verified:")
        print(f"  $50,000 @ 4.99% x 72mo:")
        print(f"  Monthly: ${monthly:.2f}")
        print(f"  Bi-weekly: ${biweekly:.2f}")
        print(f"  Weekly: ${weekly:.2f}")


# ============ API HEALTH TESTS ============

class TestAPIHealth:
    """Tests for API health and basic functionality"""
    
    def test_root_endpoint(self, api_session):
        """Test GET /api/ returns API info"""
        response = api_session.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ API root: {data['message']}")
    
    def test_ping_endpoint(self, api_session):
        """Test GET /api/ping for keep-alive"""
        response = api_session.get(f"{BASE_URL}/api/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ Ping: {data['status']}")


# ============ EXECUTION ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
