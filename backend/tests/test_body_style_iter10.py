"""
Test iteration 10 - body_style feature tests
Tests for body_style-based matching in residual lookups and scan-invoice response
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')


class TestResidualEndpoint:
    """Tests for /api/sci/residuals endpoint - verify body_style field is present"""
    
    def test_residuals_endpoint_returns_200(self):
        """Verify /api/sci/residuals returns 200"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /api/sci/residuals returns 200")
    
    def test_residuals_contain_vehicles(self):
        """Verify response contains vehicles array"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        assert "vehicles" in data, "Response must contain 'vehicles' field"
        assert isinstance(data["vehicles"], list), "vehicles must be a list"
        assert len(data["vehicles"]) > 0, "vehicles list should not be empty"
        print(f"✓ Found {len(data['vehicles'])} vehicles in residuals")
    
    def test_residuals_vehicles_have_body_style(self):
        """Verify vehicles have body_style field"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        vehicles = data["vehicles"]
        
        # Check at least some vehicles have body_style
        vehicles_with_body_style = [v for v in vehicles if v.get("body_style")]
        assert len(vehicles_with_body_style) > 0, "At least some vehicles should have body_style"
        
        # Sample body_style values
        sample_body_styles = [v["body_style"] for v in vehicles_with_body_style[:5]]
        print(f"✓ Found {len(vehicles_with_body_style)} vehicles with body_style")
        print(f"  Sample body_styles: {sample_body_styles}")
    
    def test_residuals_vehicle_structure(self):
        """Verify vehicle objects have expected structure"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        vehicles = data["vehicles"]
        
        required_fields = ["brand", "model_name", "residual_percentages"]
        sample_vehicle = vehicles[0]
        
        for field in required_fields:
            assert field in sample_vehicle, f"Vehicle must have '{field}' field"
        
        # Verify residual_percentages is a dict with term keys
        residual_pcts = sample_vehicle["residual_percentages"]
        assert isinstance(residual_pcts, dict), "residual_percentages must be a dict"
        
        print(f"✓ Vehicle structure validated: {sample_vehicle.get('brand')} {sample_vehicle.get('model_name')}")


class TestInventoryEndpointAuth:
    """Tests for /api/inventory endpoint - requires auth"""
    
    def test_inventory_requires_auth(self):
        """Verify /api/inventory returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/inventory")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ /api/inventory correctly requires authentication")


class TestLeaseRatesEndpoint:
    """Tests for /api/sci/lease-rates endpoint"""
    
    def test_lease_rates_returns_200(self):
        """Verify /api/sci/lease-rates returns 200"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /api/sci/lease-rates returns 200")
    
    def test_lease_rates_structure(self):
        """Verify lease rates response structure"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        data = response.json()
        
        # Should have vehicles_2025 and vehicles_2026
        assert "vehicles_2025" in data or "vehicles_2026" in data, "Response should have vehicle arrays"
        
        if "vehicles_2026" in data:
            assert isinstance(data["vehicles_2026"], list), "vehicles_2026 must be a list"
            if len(data["vehicles_2026"]) > 0:
                print(f"✓ Found {len(data['vehicles_2026'])} vehicles in 2026 lease rates")
        
        if "vehicles_2025" in data:
            assert isinstance(data["vehicles_2025"], list), "vehicles_2025 must be a list"
            if len(data["vehicles_2025"]) > 0:
                print(f"✓ Found {len(data['vehicles_2025'])} vehicles in 2025 lease rates")


class TestLoginAndInventory:
    """Test login and inventory with authentication"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token via login"""
        login_data = {
            "email": "danielgiroux007@gmail.com",
            "password": "Liana2018$"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Login failed with status {response.status_code}")
    
    def test_login_success(self):
        """Test login with valid credentials"""
        login_data = {
            "email": "danielgiroux007@gmail.com",
            "password": "Liana2018$"
        }
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "token" in data, "Response should contain token"
        print(f"✓ Login successful, token received")
        return data["token"]
    
    def test_inventory_with_auth(self, auth_token):
        """Test /api/inventory with authentication"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Inventory response should be a list"
        print(f"✓ /api/inventory returned {len(data)} items")
        
        # Check if any inventory items have body_style
        if len(data) > 0:
            items_with_body_style = [item for item in data if item.get("body_style")]
            print(f"  Items with body_style: {len(items_with_body_style)}/{len(data)}")


class TestProgramsEndpoint:
    """Tests for /api/programs endpoint - financing programs"""
    
    def test_programs_returns_200(self):
        """Verify /api/programs returns 200"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ /api/programs returns 200")
    
    def test_programs_structure(self):
        """Verify programs response structure"""
        response = requests.get(f"{BASE_URL}/api/programs")
        data = response.json()
        
        assert isinstance(data, list), "Programs response should be a list"
        assert len(data) > 0, "Programs list should not be empty"
        
        sample = data[0]
        expected_fields = ["brand", "model", "year"]
        for field in expected_fields:
            assert field in sample, f"Program must have '{field}' field"
        
        print(f"✓ Found {len(data)} programs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
