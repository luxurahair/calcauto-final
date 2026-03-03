"""
Test SCI Cascade Dropdowns - Iteration 7
Tests:
1. GET /api/sci/vehicle-hierarchy endpoint returns correct hierarchy
2. POST /api/inventory creates vehicle with body_style field
3. Verify cascading logic: brand->model->trim->body_style
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')

def unique_stock():
    """Generate unique stock number"""
    return f"TEST_{int(time.time()*1000)}"

def unique_vin():
    """Generate unique VIN (17 chars)"""
    import random
    import string
    # Keep some fixed prefix for valid VIN structure
    return f"1C4TEST{random.randint(10000000, 99999999)}"

class TestSciVehicleHierarchy:
    """Tests for /api/sci/vehicle-hierarchy endpoint"""
    
    def test_vehicle_hierarchy_returns_200(self):
        """Test endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/sci/vehicle-hierarchy returns 200")
    
    def test_hierarchy_contains_expected_brands(self):
        """Test hierarchy contains all 5 expected Stellantis brands"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        assert response.status_code == 200
        data = response.json()
        
        expected_brands = ["Chrysler", "Dodge", "Fiat", "Jeep", "Ram"]
        actual_brands = list(data.keys())
        
        for brand in expected_brands:
            assert brand in actual_brands, f"Brand '{brand}' not found in hierarchy"
        
        print(f"✓ All expected brands found: {expected_brands}")
    
    def test_hierarchy_has_models_for_jeep(self):
        """Test Jeep has models with proper structure"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        assert "Jeep" in data
        jeep_models = data["Jeep"]
        
        # Check expected Jeep models
        expected_models = ["Cherokee", "Compass", "Grand Wagoneer"]
        for model in expected_models:
            assert model in jeep_models, f"Jeep model '{model}' not found"
        
        # Check model structure has years and trims
        for model_name, model_data in jeep_models.items():
            assert "years" in model_data, f"Model '{model_name}' missing years"
            assert "trims" in model_data, f"Model '{model_name}' missing trims"
            assert isinstance(model_data["years"], list), "Years should be a list"
            assert isinstance(model_data["trims"], dict), "Trims should be a dict"
        
        print(f"✓ Jeep has proper model structure with years and trims")
    
    def test_hierarchy_has_body_styles_for_trims(self):
        """Test trims have body_style arrays"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        # Check Ram 1500 for body styles
        assert "Ram" in data
        assert "1500" in data["Ram"], "Ram 1500 not found"
        
        ram_1500 = data["Ram"]["1500"]
        assert "trims" in ram_1500
        
        # Find Sport trim and check body_styles
        trims = ram_1500["trims"]
        assert len(trims) > 0, "Ram 1500 should have trims"
        
        # At least one trim should have body styles
        has_body_styles = False
        for trim_name, body_styles in trims.items():
            if len(body_styles) > 0:
                has_body_styles = True
                print(f"  Ram 1500 {trim_name}: {body_styles}")
        
        assert has_body_styles, "Ram 1500 should have body styles for trims"
        print(f"✓ Ram 1500 trims have body_style arrays")
    
    def test_chrysler_pacifica_structure(self):
        """Test Chrysler Pacifica has expected trims and body styles"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        assert "Chrysler" in data
        assert "Pacifica" in data["Chrysler"]
        
        pacifica = data["Chrysler"]["Pacifica"]
        trims = pacifica["trims"]
        
        # Pacifica should have Limited and Select trims
        assert "Limited" in trims or "Select" in trims, "Pacifica should have Limited or Select trim"
        
        # Check body styles exist (4D Wagon, AWD, etc)
        for trim_name, body_styles in trims.items():
            if len(body_styles) > 0:
                assert any("Wagon" in bs for bs in body_styles), f"Pacifica {trim_name} should have Wagon body style"
        
        print(f"✓ Chrysler Pacifica has correct structure")


class TestInventoryWithBodyStyle:
    """Tests for inventory CRUD with body_style field"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "danielgiroux007@gmail.com",
            "password": "Liana2018$"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["token"]
    
    def test_create_vehicle_with_body_style(self, auth_token):
        """Test creating vehicle with body_style field"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create test vehicle with body_style
        vehicle_data = {
            "stock_no": unique_stock(),
            "vin": unique_vin(),
            "brand": "Jeep",
            "model": "Grand Wagoneer",
            "trim": "Summit Obsidian",
            "body_style": "4D Utility",
            "year": 2026,
            "type": "neuf",
            "pdco": 95000,
            "ep_cost": 85000,
            "holdback": 1200,
            "msrp": 95000,
            "asking_price": 93000,
            "km": 0,
            "color": "Diamond Black"
        }
        
        response = requests.post(f"{BASE_URL}/api/inventory", json=vehicle_data, headers=headers)
        assert response.status_code in [200, 201], f"Create failed: {response.status_code} - {response.text}"
        
        result = response.json()
        # API returns {"success": true, "vehicle": {...}}
        created = result.get("vehicle", result)
        
        assert created["body_style"] == "4D Utility", f"body_style not saved correctly: {created.get('body_style')}"
        assert created["trim"] == "Summit Obsidian", f"trim not saved: {created.get('trim')}"
        assert created["brand"] == "Jeep"
        assert created["model"] == "Grand Wagoneer"
        
        vehicle_id = created["id"]
        stock_no = created["stock_no"]
        print(f"✓ Created vehicle with body_style: {created['brand']} {created['model']} {created['trim']} - {created['body_style']}")
        
        # Verify with GET (API uses stock_no not id)
        get_response = requests.get(f"{BASE_URL}/api/inventory/{stock_no}", headers=headers)
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["body_style"] == "4D Utility", "body_style not persisted"
        print(f"✓ GET verified body_style is persisted")
        
        # Cleanup
        delete_response = requests.delete(f"{BASE_URL}/api/inventory/{stock_no}", headers=headers)
        assert delete_response.status_code in [200, 204]
        print(f"✓ Cleanup: deleted test vehicle")
    
    def test_create_vehicle_ram_1500_with_body_style(self, auth_token):
        """Test creating Ram 1500 with proper cascade values"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        vehicle_data = {
            "stock_no": unique_stock(),
            "vin": unique_vin(),
            "brand": "Ram",
            "model": "1500",
            "trim": "Sport",
            "body_style": "Crew Cab 4WD",
            "year": 2026,
            "type": "neuf",
            "pdco": 70300,
            "ep_cost": 65000,
            "holdback": 900,
            "msrp": 71580,
            "asking_price": 70300,
            "km": 0,
            "color": "Hydro Blue"
        }
        
        response = requests.post(f"{BASE_URL}/api/inventory", json=vehicle_data, headers=headers)
        assert response.status_code in [200, 201], f"Create failed: {response.text}"
        
        result = response.json()
        created = result.get("vehicle", result)
        stock_no = created["stock_no"]
        
        # Verify all cascade fields
        assert created["brand"] == "Ram"
        assert created["model"] == "1500"
        assert created["trim"] == "Sport"
        assert created["body_style"] == "Crew Cab 4WD"
        
        print(f"✓ Created Ram 1500 Sport - Crew Cab 4WD")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/inventory/{stock_no}", headers=headers)
        print(f"✓ Cleanup: deleted Ram test vehicle")
    
    def test_update_vehicle_body_style(self, auth_token):
        """Test updating body_style field"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create vehicle first
        vehicle_data = {
            "stock_no": unique_stock(),
            "brand": "Dodge",
            "model": "Durango",
            "trim": "GT",
            "body_style": "4D Utility AWD",
            "year": 2026,
            "type": "neuf",
            "pdco": 55000,
            "msrp": 58000,
        }
        
        create_response = requests.post(f"{BASE_URL}/api/inventory", json=vehicle_data, headers=headers)
        assert create_response.status_code in [200, 201]
        result = create_response.json()
        created = result.get("vehicle", result)
        stock_no = created["stock_no"]
        
        # Update body_style (API uses stock_no)
        update_response = requests.put(
            f"{BASE_URL}/api/inventory/{stock_no}",
            json={"trim": "R/T", "body_style": "4D Utility AWD"},
            headers=headers
        )
        assert update_response.status_code == 200
        
        # Verify update
        get_response = requests.get(f"{BASE_URL}/api/inventory/{stock_no}", headers=headers)
        updated = get_response.json()
        assert updated["trim"] == "R/T"
        assert updated["body_style"] == "4D Utility AWD"
        
        print(f"✓ Updated vehicle trim/body_style successfully")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/inventory/{stock_no}", headers=headers)


class TestCascadingLogic:
    """Test the cascading dropdown logic through the API"""
    
    def test_cascade_brand_to_models(self):
        """Verify selecting a brand filters to correct models"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        # Select Chrysler
        chrysler_models = list(data["Chrysler"].keys())
        assert "Grand Caravan" in chrysler_models
        assert "Pacifica" in chrysler_models
        
        # Chrysler should NOT have Wrangler (that's Jeep)
        assert "Wrangler" not in chrysler_models
        assert "1500" not in chrysler_models  # That's Ram
        
        print(f"✓ Chrysler models: {chrysler_models}")
    
    def test_cascade_model_to_trims(self):
        """Verify selecting a model shows correct trims"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        # Select Dodge Durango
        durango_trims = list(data["Dodge"]["Durango"]["trims"].keys())
        
        # Durango should have GT, R/T, SXT, etc
        expected_trims = ["GT", "R/T", "SXT"]
        for trim in expected_trims:
            assert trim in durango_trims, f"Durango missing {trim} trim"
        
        print(f"✓ Dodge Durango trims: {durango_trims}")
    
    def test_cascade_trim_to_body_styles(self):
        """Verify selecting a trim shows correct body styles"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        # Select Dodge Charger R/T
        charger_rt_bodies = data["Dodge"]["Charger"]["trims"].get("R/T", [])
        
        assert len(charger_rt_bodies) > 0, "Charger R/T should have body styles"
        
        # Charger should have Coupe and/or Sedan body styles
        has_valid_body = any("Coupe" in bs or "Sedan" in bs for bs in charger_rt_bodies)
        assert has_valid_body, f"Charger R/T body styles unexpected: {charger_rt_bodies}"
        
        print(f"✓ Dodge Charger R/T body styles: {charger_rt_bodies}")
    
    def test_full_cascade_path(self):
        """Test complete cascade: Jeep -> Cherokee -> Laredo -> body_style"""
        response = requests.get(f"{BASE_URL}/api/sci/vehicle-hierarchy")
        data = response.json()
        
        # Step 1: Select brand = Jeep
        assert "Jeep" in data
        jeep = data["Jeep"]
        
        # Step 2: Select model = Cherokee
        assert "Cherokee" in jeep
        cherokee = jeep["Cherokee"]
        
        # Step 3: Select trim = Laredo
        assert "trims" in cherokee
        trims = cherokee["trims"]
        assert "Laredo" in trims, f"Cherokee trims: {list(trims.keys())}"
        
        # Step 4: Get body styles for Laredo
        laredo_bodies = trims["Laredo"]
        assert len(laredo_bodies) > 0, "Laredo should have body styles"
        
        print(f"✓ Full cascade: Jeep -> Cherokee -> Laredo -> {laredo_bodies}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
