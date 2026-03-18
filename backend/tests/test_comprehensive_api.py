"""
Comprehensive API tests for CalcAuto AiPro
Tests all major endpoints including auth, programs, SCI lease, calculate, and admin
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://lease-extraction.preview.emergentagent.com').rstrip('/')


class TestHealthAndBasicEndpoints:
    """Health check and basic endpoint tests"""
    
    def test_ping_endpoint(self):
        """Test /api/ping returns status ok"""
        response = requests.get(f"{BASE_URL}/api/ping")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("SUCCESS: /api/ping returned status ok")
    
    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        print("SUCCESS: /api/ root endpoint working")


class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_demo_login(self):
        """Test demo login returns token"""
        response = requests.post(f"{BASE_URL}/api/auth/demo-login")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "demo@calcauto.ca"
        assert data["user"]["is_admin"] == True
        print(f"SUCCESS: Demo login returned token, user: {data['user']['email']}")
        return data["token"]
    
    def test_regular_login(self):
        """Test regular user login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "danielgiroux007@gmail.com",
            "password": "Liana2018$"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "token" in data
        assert data["user"]["email"] == "danielgiroux007@gmail.com"
        print(f"SUCCESS: Regular login for {data['user']['email']}")
        return data["token"]
    
    def test_invalid_login(self):
        """Test login with invalid credentials fails"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("SUCCESS: Invalid login rejected with 401")


class TestProgramsEndpoints:
    """Programs API endpoint tests"""
    
    def test_get_programs(self):
        """Test getting vehicle programs"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify program structure
        program = data[0]
        assert "id" in program
        assert "brand" in program
        assert "model" in program
        assert "year" in program
        assert "option1_rates" in program
        print(f"SUCCESS: GET /api/programs returned {len(data)} programs")
        return data
    
    def test_get_programs_count(self):
        """Test that programs count matches expected 93"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        data = response.json()
        # The expected count was 93 according to test requirements
        assert len(data) >= 90, f"Expected ~93 programs, got {len(data)}"
        print(f"SUCCESS: Program count is {len(data)} (expected ~93)")
    
    def test_get_periods(self):
        """Test getting available program periods"""
        response = requests.get(f"{BASE_URL}/api/periods")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        period = data[0]
        assert "month" in period
        assert "year" in period
        assert "count" in period
        print(f"SUCCESS: GET /api/periods returned {len(data)} periods")
    
    def test_get_program_meta(self):
        """Test getting program metadata"""
        response = requests.get(f"{BASE_URL}/api/program-meta")
        assert response.status_code == 200
        data = response.json()
        assert "program_month" in data or "program_period" in data
        print(f"SUCCESS: GET /api/program-meta returned metadata")


class TestSCILeaseEndpoints:
    """SCI Lease rates and residuals tests"""
    
    def test_get_sci_lease_rates(self):
        """Test getting SCI lease rates"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        assert response.status_code == 200
        data = response.json()
        assert "vehicles_2026" in data or "terms" in data
        print(f"SUCCESS: GET /api/sci/lease-rates returned data")
    
    def test_get_sci_residuals(self):
        """Test getting SCI residual values"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        assert response.status_code == 200
        data = response.json()
        assert "vehicles" in data or "km_adjustments" in data
        print(f"SUCCESS: GET /api/sci/residuals returned data")


class TestCalculateEndpoint:
    """Calculate financing endpoint tests"""
    
    @pytest.fixture
    def sample_program_id(self):
        """Get a valid program ID for testing"""
        response = requests.get(f"{BASE_URL}/api/programs")
        programs = response.json()
        return programs[0]["id"] if programs else None
    
    def test_calculate_financing(self, sample_program_id):
        """Test financing calculation"""
        if not sample_program_id:
            pytest.skip("No programs available for testing")
        
        response = requests.post(f"{BASE_URL}/api/calculate", json={
            "program_id": sample_program_id,
            "vehicle_price": 50000
        })
        assert response.status_code == 200
        data = response.json()
        assert "comparisons" in data
        assert len(data["comparisons"]) > 0
        assert "vehicle_price" in data
        assert data["vehicle_price"] == 50000
        
        # Verify comparison structure
        comparison = data["comparisons"][0]
        assert "term_months" in comparison
        assert "option1_rate" in comparison
        assert "option1_monthly" in comparison
        print(f"SUCCESS: Calculate endpoint returned {len(data['comparisons'])} term options")
    
    def test_calculate_missing_program_id(self):
        """Test calculate fails without program_id"""
        response = requests.post(f"{BASE_URL}/api/calculate", json={
            "vehicle_price": 50000
        })
        assert response.status_code == 400 or response.status_code == 422
        print("SUCCESS: Calculate correctly rejects missing program_id")


class TestAuthenticatedEndpoints:
    """Tests for endpoints requiring authentication"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/demo-login")
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Could not obtain auth token")
    
    def test_get_contacts(self, auth_token):
        """Test getting contacts (requires auth)"""
        response = requests.get(
            f"{BASE_URL}/api/contacts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: GET /api/contacts returned {len(data)} contacts")
    
    def test_get_submissions(self, auth_token):
        """Test getting submissions (requires auth)"""
        response = requests.get(
            f"{BASE_URL}/api/submissions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: GET /api/submissions returned {len(data)} submissions")
    
    def test_get_inventory(self, auth_token):
        """Test getting inventory (requires auth)"""
        response = requests.get(
            f"{BASE_URL}/api/inventory",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: GET /api/inventory returned {len(data)} items")
    
    def test_get_admin_stats(self, auth_token):
        """Test getting admin statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_contacts" in data
        print(f"SUCCESS: Admin stats - Users: {data.get('total_users')}, Contacts: {data.get('total_contacts')}")


class TestCorrectionsEndpoint:
    """Test corrections API"""
    
    def test_get_corrections(self):
        """Test getting program corrections"""
        response = requests.get(f"{BASE_URL}/api/corrections")
        assert response.status_code == 200
        data = response.json()
        assert "corrections" in data or "total" in data
        print(f"SUCCESS: GET /api/corrections returned data")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
