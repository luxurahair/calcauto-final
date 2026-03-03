"""
Test Suite for Trim Sort Order Feature - Iteration 14
Tests the logical trim sorting (manufacturer hierarchy) instead of alphabetical sorting.
Validates: brand order, model order within brands, and trim hierarchy for Compass/Ram 1500.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')

class TestTrimSortOrder:
    """Tests for the trim sort_order feature"""
    
    def test_api_ping(self):
        """Test API is alive"""
        response = requests.get(f"{BASE_URL}/api/ping")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("API ping successful")
    
    def test_programs_endpoint_returns_programs(self):
        """Test GET /api/programs returns programs with sort_order field"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        assert len(programs) > 0, "Should return programs"
        
        # Check that programs have sort_order field
        for p in programs[:5]:
            assert "sort_order" in p, f"Program {p.get('brand')} {p.get('model')} missing sort_order"
        
        print(f"GET /api/programs returned {len(programs)} programs with sort_order field")
    
    def test_programs_sorted_by_sort_order(self):
        """Test that programs are returned sorted by sort_order (not alphabetically)"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        
        # Verify sort_order is monotonically increasing
        prev_order = -1
        for p in programs:
            curr_order = p.get("sort_order", 999999)
            assert curr_order >= prev_order, \
                f"Programs not sorted: {p['brand']} {p['model']} {p.get('trim')} has sort_order {curr_order} but prev was {prev_order}"
            prev_order = curr_order
        
        print("Programs are correctly sorted by sort_order")
    
    def test_brand_order(self):
        """Test brand ordering: Chrysler -> Jeep -> Dodge -> Ram -> Fiat"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        
        # Extract brand order from response
        brands_in_order = []
        for p in programs:
            if p['brand'] not in brands_in_order:
                brands_in_order.append(p['brand'])
        
        expected_order = ['Chrysler', 'Jeep', 'Dodge', 'Ram', 'Fiat']
        
        # Verify order matches (for brands that exist in data)
        for i, brand in enumerate(brands_in_order):
            if brand in expected_order:
                expected_idx = expected_order.index(brand)
                # All previous brands should come before this one
                for prev_brand in brands_in_order[:i]:
                    if prev_brand in expected_order:
                        prev_expected_idx = expected_order.index(prev_brand)
                        assert prev_expected_idx < expected_idx, \
                            f"Brand order incorrect: {prev_brand} should come before {brand}"
        
        print(f"Brand order correct: {brands_in_order}")
    
    def test_jeep_model_order(self):
        """Test Jeep model ordering: Compass before Cherokee before Wrangler etc."""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        
        # Get Jeep models in order
        jeep_programs = [p for p in programs if p['brand'] == 'Jeep']
        jeep_models_in_order = []
        for p in jeep_programs:
            if p['model'] not in jeep_models_in_order:
                jeep_models_in_order.append(p['model'])
        
        expected_model_order = [
            "Compass", "Cherokee", "Wrangler", "Gladiator",
            "Grand Cherokee", "Grand Cherokee L", "Grand Cherokee/L",
            "Wagoneer", "Grand Wagoneer"
        ]
        
        # Verify Compass comes before Cherokee if both exist
        if "Compass" in jeep_models_in_order and "Cherokee" in jeep_models_in_order:
            assert jeep_models_in_order.index("Compass") < jeep_models_in_order.index("Cherokee"), \
                "Compass should come before Cherokee"
        
        # Verify Cherokee comes before Wrangler if both exist
        if "Cherokee" in jeep_models_in_order and "Wrangler" in jeep_models_in_order:
            assert jeep_models_in_order.index("Cherokee") < jeep_models_in_order.index("Wrangler"), \
                "Cherokee should come before Wrangler"
        
        print(f"Jeep model order: {jeep_models_in_order}")
    
    def test_compass_trim_order_2026(self):
        """Test Jeep Compass 2026 trim order: Sport -> North -> Trailhawk -> Limited"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        
        # Filter for Jeep Compass 2026
        compass_2026 = [p for p in programs if p['brand'] == 'Jeep' and p['model'] == 'Compass' and p['year'] == 2026]
        compass_2026.sort(key=lambda x: x.get('sort_order', 999999))
        
        assert len(compass_2026) > 0, "Should have Jeep Compass 2026 programs"
        
        # Extract trim order
        trims_in_order = [p.get('trim', 'N/A') for p in compass_2026]
        print(f"Compass 2026 trims in order: {trims_in_order}")
        
        # Validate expected order
        expected_order = ["Sport", "North", "North w/ Altitude Package (ADZ)", "Trailhawk", "Limited"]
        
        # Find indices in the response
        trim_positions = {}
        for t in expected_order:
            for i, actual_trim in enumerate(trims_in_order):
                if actual_trim and (t.lower() in actual_trim.lower() or actual_trim.lower() in t.lower()):
                    if t not in trim_positions:  # Take first match
                        trim_positions[t] = i
        
        # Sport should come before North
        if "Sport" in trim_positions and "North" in trim_positions:
            assert trim_positions["Sport"] <= trim_positions["North"], \
                f"Sport ({trim_positions['Sport']}) should come before North ({trim_positions['North']})"
        
        # North should come before Trailhawk
        if "North" in trim_positions and "Trailhawk" in trim_positions:
            assert trim_positions["North"] <= trim_positions["Trailhawk"], \
                f"North ({trim_positions['North']}) should come before Trailhawk ({trim_positions['Trailhawk']})"
        
        # Trailhawk should come before Limited
        if "Trailhawk" in trim_positions and "Limited" in trim_positions:
            assert trim_positions["Trailhawk"] <= trim_positions["Limited"], \
                f"Trailhawk ({trim_positions['Trailhawk']}) should come before Limited ({trim_positions['Limited']})"
        
        print("Compass 2026 trim order validated: Sport -> North -> Trailhawk -> Limited")
    
    def test_ram_1500_trim_order_2026(self):
        """Test Ram 1500 2026 trim order: Tradesman -> Big Horn -> Sport/Rebel -> Laramie -> Limited"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        
        # Filter for Ram 1500 2026
        ram_2026 = [p for p in programs if p['brand'] == 'Ram' and p['model'] == '1500' and p['year'] == 2026]
        ram_2026.sort(key=lambda x: x.get('sort_order', 999999))
        
        assert len(ram_2026) > 0, "Should have Ram 1500 2026 programs"
        
        # Extract trim order
        trims_in_order = [p.get('trim', 'N/A') for p in ram_2026]
        print(f"Ram 1500 2026 trims in order: {trims_in_order}")
        
        # Validate Tradesman comes first
        tradesman_idx = None
        big_horn_idx = None
        sport_idx = None
        laramie_idx = None
        
        for i, trim in enumerate(trims_in_order):
            if trim and 'tradesman' in trim.lower():
                if tradesman_idx is None:
                    tradesman_idx = i
            if trim and 'big horn' in trim.lower():
                if big_horn_idx is None:
                    big_horn_idx = i
            if trim and 'sport' in trim.lower():
                if sport_idx is None:
                    sport_idx = i
            if trim and 'laramie' in trim.lower():
                if laramie_idx is None:
                    laramie_idx = i
        
        # Tradesman should come before Big Horn
        if tradesman_idx is not None and big_horn_idx is not None:
            assert tradesman_idx < big_horn_idx, \
                f"Tradesman ({tradesman_idx}) should come before Big Horn ({big_horn_idx})"
        
        # Big Horn should come before Sport
        if big_horn_idx is not None and sport_idx is not None:
            assert big_horn_idx < sport_idx, \
                f"Big Horn ({big_horn_idx}) should come before Sport ({sport_idx})"
        
        # Sport should come before Laramie
        if sport_idx is not None and laramie_idx is not None:
            assert sport_idx < laramie_idx, \
                f"Sport ({sport_idx}) should come before Laramie ({laramie_idx})"
        
        print("Ram 1500 2026 trim order validated: Tradesman -> Big Horn -> Sport -> Laramie")
    
    def test_trim_orders_endpoint(self):
        """Test GET /api/trim-orders returns stored trim orders"""
        response = requests.get(f"{BASE_URL}/api/trim-orders")
        assert response.status_code == 200
        trim_orders = response.json()
        
        assert len(trim_orders) > 0, "Should return trim orders"
        
        # Check structure
        for to in trim_orders[:3]:
            assert "brand" in to, "Trim order should have brand"
            assert "model" in to, "Trim order should have model"
            assert "trims" in to, "Trim order should have trims list"
        
        # Find Compass trim order
        compass_order = next((to for to in trim_orders if to['brand'] == 'Jeep' and to['model'] == 'Compass'), None)
        assert compass_order is not None, "Should have Jeep Compass in trim_orders"
        
        compass_trims = compass_order.get('trims', [])
        assert 'Sport' in compass_trims, "Compass trims should include Sport"
        assert 'Limited' in compass_trims, "Compass trims should include Limited"
        
        # Sport should come before Limited in the list
        sport_idx = compass_trims.index('Sport')
        limited_idx = compass_trims.index('Limited')
        assert sport_idx < limited_idx, "Sport should come before Limited in trim_orders"
        
        print(f"GET /api/trim-orders returned {len(trim_orders)} entries with correct structure")


class TestLoginAndAuth:
    """Tests for authentication with provided credentials"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "danielgiroux007@gmail.com",
            "password": "Liana2018$"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Login should return token"
        assert "user" in data, "Login should return user info"
        print(f"Login successful for {data['user'].get('email')}")
        return data.get("token")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, "Invalid credentials should return 401"
        print("Invalid credentials correctly rejected with 401")


class TestFilteringWithSortOrder:
    """Test that filters work correctly with sort_order"""
    
    def test_filter_by_year_maintains_sort(self):
        """Test filtering by year still returns sorted results"""
        response = requests.get(f"{BASE_URL}/api/programs?year=2026")
        assert response.status_code == 200
        programs = response.json()
        
        # Verify still sorted by sort_order
        prev_order = -1
        for p in programs:
            curr_order = p.get("sort_order", 999999)
            assert curr_order >= prev_order, "Filtered results should still be sorted"
            prev_order = curr_order
        
        print(f"Year filter returned {len(programs)} programs, correctly sorted")
    
    def test_filter_by_period_maintains_sort(self):
        """Test filtering by month/year period maintains sort"""
        response = requests.get(f"{BASE_URL}/api/programs?month=2&year=2026")
        assert response.status_code == 200
        programs = response.json()
        
        # Verify still sorted by sort_order
        prev_order = -1
        for p in programs:
            curr_order = p.get("sort_order", 999999)
            assert curr_order >= prev_order, "Period filtered results should still be sorted"
            prev_order = curr_order
        
        print(f"Period filter (Feb 2026) returned {len(programs)} programs, correctly sorted")


class TestSortOrderValues:
    """Test the sort_order value calculation"""
    
    def test_sort_order_structure(self):
        """Test sort_order follows brand*10000 + model*100 + trim structure"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        programs = response.json()
        
        # Check Chrysler programs have sort_order < 10000 (brand_order=0)
        chrysler_programs = [p for p in programs if p['brand'] == 'Chrysler']
        for p in chrysler_programs:
            assert p.get('sort_order', 99999) < 10000, \
                f"Chrysler program should have sort_order < 10000: {p.get('sort_order')}"
        
        # Check Jeep programs have sort_order between 10000 and 20000 (brand_order=1)
        jeep_programs = [p for p in programs if p['brand'] == 'Jeep']
        for p in jeep_programs:
            so = p.get('sort_order', 0)
            assert 10000 <= so < 20000, \
                f"Jeep program should have 10000 <= sort_order < 20000: {so}"
        
        # Check Dodge programs have sort_order between 20000 and 30000 (brand_order=2)
        dodge_programs = [p for p in programs if p['brand'] == 'Dodge']
        for p in dodge_programs:
            so = p.get('sort_order', 0)
            assert 20000 <= so < 30000, \
                f"Dodge program should have 20000 <= sort_order < 30000: {so}"
        
        # Check Ram programs have sort_order between 30000 and 40000 (brand_order=3)
        ram_programs = [p for p in programs if p['brand'] == 'Ram']
        for p in ram_programs:
            so = p.get('sort_order', 0)
            assert 30000 <= so < 40000, \
                f"Ram program should have 30000 <= sort_order < 40000: {so}"
        
        # Check Fiat programs have sort_order >= 40000 (brand_order=4)
        fiat_programs = [p for p in programs if p['brand'] == 'Fiat']
        for p in fiat_programs:
            so = p.get('sort_order', 0)
            assert so >= 40000, \
                f"Fiat program should have sort_order >= 40000: {so}"
        
        print("Sort order structure validated (brand*10000 + model*100 + trim)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
