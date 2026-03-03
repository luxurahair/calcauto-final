"""
Test SCI Lease Feature - CalcAuto AiPro
Tests for Location SCI (lease comparison) feature
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "danielgiroux007@gmail.com"
TEST_PASSWORD = "Liana2018$"


class TestSCILeaseAPIs:
    """Tests for SCI Lease endpoints"""
    
    def test_get_sci_residuals(self):
        """Test GET /api/sci/residuals returns residual data"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        assert response.status_code == 200
        
        data = response.json()
        assert "effective_from" in data
        assert "effective_to" in data
        assert "km_adjustments" in data
        assert "vehicles" in data
        assert len(data["vehicles"]) > 0
        
        # Verify km adjustment structure
        km_adj = data["km_adjustments"]
        assert "standard_km" in km_adj
        assert km_adj["standard_km"] == 24000
        assert "adjustments" in km_adj
        assert "12000" in km_adj["adjustments"]
        assert "18000" in km_adj["adjustments"]
        
        # Verify adjustment for 12k km at 48 months is +4%
        assert km_adj["adjustments"]["12000"]["48"] == 4
        print(f"SUCCESS: GET /api/sci/residuals - {len(data['vehicles'])} vehicles")
        
    def test_sci_residuals_vehicle_structure(self):
        """Test residual vehicle data structure"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        assert response.status_code == 200
        
        data = response.json()
        vehicles = data["vehicles"]
        
        # Check a sample vehicle has required fields
        sample = vehicles[0]
        assert "brand" in sample
        assert "model_year" in sample
        assert "model_name" in sample
        assert "trim" in sample
        assert "residual_percentages" in sample
        
        # Verify residual percentages for expected terms
        residuals = sample["residual_percentages"]
        expected_terms = ["24", "27", "36", "39", "42", "48", "51", "54", "60"]
        for term in expected_terms:
            assert term in residuals, f"Missing term {term} in residuals"
        print(f"SUCCESS: Vehicle structure verified - {sample['brand']} {sample['model_name']}")
        
    def test_get_sci_lease_rates(self):
        """Test GET /api/sci/lease-rates returns lease rate programs"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        assert response.status_code == 200
        
        data = response.json()
        assert "program_period" in data
        assert "program_code" in data
        assert "terms" in data
        assert "vehicles_2026" in data
        assert "vehicles_2025" in data
        
        # Verify terms
        assert data["terms"] == [24, 27, 36, 39, 42, 48, 51, 54, 60]
        
        print(f"SUCCESS: GET /api/sci/lease-rates - 2026:{len(data['vehicles_2026'])} 2025:{len(data['vehicles_2025'])} vehicles")
        
    def test_ram_1500_sport_rebel_lease_cash(self):
        """Test Ram 1500 Sport, Rebel has correct lease cash (8250)"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        assert response.status_code == 200
        
        data = response.json()
        vehicles_2026 = data["vehicles_2026"]
        
        # Find Ram 1500 Sport, Rebel entry
        ram_sport_rebel = None
        for v in vehicles_2026:
            if "Ram 1500 Sport, Rebel" in v["model"]:
                ram_sport_rebel = v
                break
        
        assert ram_sport_rebel is not None, "Ram 1500 Sport, Rebel not found in 2026 vehicles"
        assert ram_sport_rebel["lease_cash"] == 8250, f"Expected lease_cash 8250, got {ram_sport_rebel['lease_cash']}"
        assert ram_sport_rebel["brand"] == "Ram"
        assert ram_sport_rebel["standard_rates"] is not None
        assert ram_sport_rebel["alternative_rates"] is not None
        
        # Verify standard rate at 48 months
        assert ram_sport_rebel["standard_rates"]["48"] == 8.29
        
        # Verify alternative rate at 48 months
        assert ram_sport_rebel["alternative_rates"]["48"] == 3.99
        
        print(f"SUCCESS: Ram 1500 Sport, Rebel verified - lease_cash: ${ram_sport_rebel['lease_cash']}")
        
    def test_post_calculate_lease_ram_1500(self):
        """Test POST /api/sci/calculate-lease for Ram 1500"""
        # API requires msrp, selling_price, annual_rate, residual_pct
        payload = {
            "msrp": 71580,
            "selling_price": 71580,
            "term": 48,
            "annual_rate": 3.99,  # Alternative rate at 48 months
            "residual_pct": 53,   # Ram 1500 Sport 48-month residual
            "km_per_year": 24000,
            "lease_cash": 8250,
            "bonus_cash": 0,
            "cash_down": 0,
            "trade_value": 0,
            "trade_owed": 0,
            "frais_dossier": 259.95,
            "taxe_pneus": 15,
            "frais_rdprm": 100
        }
        
        response = requests.post(f"{BASE_URL}/api/sci/calculate-lease", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        assert "monthly_payment" in data
        assert "biweekly_payment" in data
        assert "weekly_payment" in data
        assert "residual_value" in data
        assert "residual_pct" in data
        
        # Verify residual percentage for 48 months (should be 53%)
        assert data["residual_pct"] == 53
        
        # Verify monthly payment is reasonable (should be around $800-1200)
        assert data["monthly_payment"] > 500
        assert data["monthly_payment"] < 2000
        
        print(f"SUCCESS: Lease calculation - Monthly: ${data['monthly_payment']:.2f}, Residual: {data['residual_pct']}%")
        
    def test_calculate_lease_km_adjustment(self):
        """Test km adjustment affects residual correctly"""
        base_payload = {
            "msrp": 71580,
            "selling_price": 71580,
            "term": 48,
            "annual_rate": 3.99,
            "residual_pct": 53,  # Base residual
            "lease_cash": 8250,
            "bonus_cash": 0,
            "cash_down": 0,
            "trade_value": 0,
            "trade_owed": 0,
            "frais_dossier": 0,
            "taxe_pneus": 0,
            "frais_rdprm": 0
        }
        
        # Test with 24k km (standard - no adjustment)
        payload_24k = {**base_payload, "km_per_year": 24000}
        response_24k = requests.post(f"{BASE_URL}/api/sci/calculate-lease", json=payload_24k)
        
        # Test with 12k km (should have +4% higher residual at 48 months)
        payload_12k = {**base_payload, "km_per_year": 12000}
        response_12k = requests.post(f"{BASE_URL}/api/sci/calculate-lease", json=payload_12k)
        
        assert response_24k.status_code == 200
        assert response_12k.status_code == 200
        
        data_24k = response_24k.json()
        data_12k = response_12k.json()
        
        # 12k km should have higher residual (better for lessee)
        assert data_12k["residual_pct"] > data_24k["residual_pct"]
        
        # The difference should be about 4% for 48 month term
        diff = data_12k["residual_pct"] - data_24k["residual_pct"]
        assert diff >= 3 and diff <= 5, f"Expected ~4% diff, got {diff}%"
        
        print(f"SUCCESS: km adjustment verified - 24k: {data_24k['residual_pct']}%, 12k: {data_12k['residual_pct']}%")
        
    def test_calculate_lease_different_terms(self):
        """Test lease calculation across different terms"""
        # Residuals by term from Ram 1500 Sport data
        residuals_by_term = {24: 66, 36: 59, 48: 53, 60: 49}
        
        base_payload = {
            "msrp": 71580,
            "selling_price": 71580,
            "km_per_year": 24000,
            "annual_rate": 3.99,
            "lease_cash": 8250,
            "bonus_cash": 0,
            "cash_down": 0,
            "trade_value": 0,
            "trade_owed": 0,
            "frais_dossier": 0,
            "taxe_pneus": 0,
            "frais_rdprm": 0
        }
        
        results = {}
        for term in [24, 36, 48, 60]:
            payload = {**base_payload, "term": term, "residual_pct": residuals_by_term[term]}
            response = requests.post(f"{BASE_URL}/api/sci/calculate-lease", json=payload)
            assert response.status_code == 200, f"Failed for term {term}"
            data = response.json()
            results[term] = data
            
        # Shorter terms should have higher residual (as we provided)
        assert results[24]["residual_pct"] > results[36]["residual_pct"]
        assert results[36]["residual_pct"] > results[48]["residual_pct"]
        assert results[48]["residual_pct"] > results[60]["residual_pct"]
        
        print(f"SUCCESS: Multi-term calculation")
        for term, data in results.items():
            print(f"  {term} months: ${data['monthly_payment']:.2f}/mo, {data['residual_pct']}% residual")


class TestAuthenticationAndLogin:
    """Test login flow with provided credentials"""
    
    def test_login_success(self):
        """Test login with provided credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL.lower()
        
        print(f"SUCCESS: Login successful for {TEST_EMAIL}")
        return data["token"]
        
    def test_programs_api(self):
        """Test GET /api/programs returns financing programs"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0
        
        # Find Ram 1500 Sport, Rebel
        ram_found = False
        for prog in data:
            if prog["brand"] == "Ram" and "1500" in prog["model"] and prog.get("trim"):
                if "Sport" in prog["trim"] or "Rebel" in prog["trim"]:
                    ram_found = True
                    assert prog["consumer_cash"] == 8250, f"Expected consumer_cash 8250, got {prog['consumer_cash']}"
                    break
                    
        assert ram_found, "Ram 1500 Sport, Rebel program not found"
        print(f"SUCCESS: Programs API - {len(data)} programs found")


class TestLeaseRateMatching:
    """Test lease rate matching for specific vehicles"""
    
    def test_match_ram_1500_sport(self):
        """Verify Ram 1500 Sport matches correct rate entry"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        data = response.json()
        
        # The entry should be "Ram 1500 Sport, Rebel" for 2026
        vehicles = data["vehicles_2026"]
        
        matches = [v for v in vehicles if "Ram" in v["brand"] and "Sport" in v["model"]]
        assert len(matches) > 0, "No Ram Sport entries found"
        
        sport_rebel = matches[0]
        assert sport_rebel["lease_cash"] == 8250
        print(f"SUCCESS: Ram 1500 Sport matches '{sport_rebel['model']}' with lease_cash ${sport_rebel['lease_cash']}")
        
    def test_match_ram_1500_rebel(self):
        """Verify Ram 1500 Rebel matches same entry as Sport"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        data = response.json()
        
        # "Ram 1500 Sport, Rebel" should match for both Sport and Rebel trims
        vehicles = data["vehicles_2026"]
        
        matches = [v for v in vehicles if "Ram" in v["brand"] and "Rebel" in v["model"]]
        assert len(matches) > 0, "No Ram Rebel entries found"
        
        sport_rebel = matches[0]
        assert sport_rebel["lease_cash"] == 8250
        print(f"SUCCESS: Ram 1500 Rebel matches '{sport_rebel['model']}' with lease_cash ${sport_rebel['lease_cash']}")


class TestResidualMatching:
    """Test residual value matching for specific vehicles"""
    
    def test_ram_1500_sport_residual(self):
        """Verify Ram 1500 Sport has correct residual at 48 months"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        
        # Find Ram 1500 Sport entry
        vehicles = data["vehicles"]
        ram_sport = None
        for v in vehicles:
            if v["brand"] == "Ram" and v["model_name"] == "1500" and v["trim"] == "Sport":
                ram_sport = v
                break
                
        assert ram_sport is not None, "Ram 1500 Sport not found in residuals"
        
        # 48 month residual should be 53% (based on Crew Cab LWB 4WD)
        residual_48 = ram_sport["residual_percentages"]["48"]
        assert residual_48 >= 50 and residual_48 <= 55, f"48mo residual {residual_48}% not in expected range 50-55%"
        
        print(f"SUCCESS: Ram 1500 Sport residual at 48 months: {residual_48}%")
        
    def test_ram_1500_rebel_residual(self):
        """Verify Ram 1500 Rebel has correct residual at 48 months"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        data = response.json()
        
        vehicles = data["vehicles"]
        ram_rebel = None
        for v in vehicles:
            if v["brand"] == "Ram" and v["model_name"] == "1500" and v["trim"] == "Rebel":
                ram_rebel = v
                break
                
        assert ram_rebel is not None, "Ram 1500 Rebel not found in residuals"
        
        # 48 month residual for Rebel
        residual_48 = ram_rebel["residual_percentages"]["48"]
        assert residual_48 >= 50 and residual_48 <= 55, f"48mo residual {residual_48}% not in expected range 50-55%"
        
        print(f"SUCCESS: Ram 1500 Rebel residual at 48 months: {residual_48}%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
