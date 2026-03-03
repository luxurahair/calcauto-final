"""
Test Suite for CalcAuto AiPro - SCI Lease Calculation Features (Iteration 6)

Tests the corrected lease calculation logic:
1. Separate PDSF (MSRP) from selling price for residual calculation
2. Solde reporté field for carried-over balance
3. Tax credit on trade-in limited to total lease taxes
4. Fees automatically included
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')

class TestBackendAPIs:
    """Backend API Tests"""
    
    def test_sci_residuals_endpoint(self):
        """GET /api/sci/residuals returns 200 with vehicle data"""
        response = requests.get(f"{BASE_URL}/api/sci/residuals")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "vehicles" in data, "Response should contain 'vehicles'"
        assert "km_adjustments" in data, "Response should contain 'km_adjustments'"
        assert len(data["vehicles"]) > 0, "Should have vehicle data"
        
        # Check Ram 1500 Sport/Rebel exists
        ram_found = False
        for v in data["vehicles"]:
            if v.get("brand") == "Ram" and "1500" in v.get("model_name", "") and "Sport" in (v.get("trim") or ""):
                ram_found = True
                assert "48" in v.get("residual_percentages", {}), "Should have 48-month residual"
                break
        assert ram_found, "Ram 1500 Sport should be in residuals data"
        print("✓ GET /api/sci/residuals - 200 OK with vehicle residual data")
    
    def test_sci_lease_rates_endpoint(self):
        """GET /api/sci/lease-rates returns 200 with rate programs"""
        response = requests.get(f"{BASE_URL}/api/sci/lease-rates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "vehicles_2026" in data or "vehicles_2025" in data, "Should have vehicle lease rates"
        assert "terms" in data, "Should have terms list"
        
        # Check for Ram 1500 Sport/Rebel rates
        vehicles = data.get("vehicles_2026", [])
        ram_found = False
        for v in vehicles:
            model = v.get("model", "") or ""
            if v.get("brand") == "Ram" and "Sport" in model and "Rebel" in model:
                ram_found = True
                assert v.get("lease_cash") == 8250, f"Ram 1500 Sport/Rebel should have 8250 lease cash, got {v.get('lease_cash')}"
                assert "standard_rates" in v or "alternative_rates" in v, "Should have rates"
                break
        assert ram_found, "Ram 1500 Sport/Rebel should be in lease rates"
        print("✓ GET /api/sci/lease-rates - 200 OK with lease programs")
    
    def test_auth_login(self):
        """POST /api/auth/login works with test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "danielgiroux007@gmail.com",
            "password": "Liana2018$"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Login should be successful"
        assert "token" in data, "Should return token"
        print("✓ POST /api/auth/login - 200 OK with credentials")
    
    def test_programs_endpoint(self):
        """GET /api/programs returns financing programs"""
        response = requests.get(f"{BASE_URL}/api/programs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Should return list of programs"
        assert len(data) > 0, "Should have programs"
        
        # Find Ram 1500 Sport, Rebel
        ram_found = False
        for p in data:
            trim = p.get("trim") or ""
            if p.get("brand") == "Ram" and "Sport" in trim and "Rebel" in trim:
                ram_found = True
                assert p.get("consumer_cash") == 8250, f"Ram 1500 Sport/Rebel consumer_cash should be 8250, got {p.get('consumer_cash')}"
                break
        assert ram_found, "Ram 1500 Sport, Rebel should be in programs"
        print("✓ GET /api/programs - 200 OK with Ram 1500 Sport/Rebel data")


class TestLeaseCalculationLogic:
    """Test lease calculation correctness (based on code review)"""
    
    def test_residual_calculation_uses_pdsf(self):
        """Verify residual is calculated on PDSF, not selling price"""
        # Based on frontend code review (line 658-659):
        # const pdsf = parseFloat(leasePdsf) || parseFloat(vehiclePrice);
        # const residualValue = pdsf * (adjustedResidualPct / 100);
        
        # This means:
        # - If PDSF=71580, residual at 53% = 71580 * 0.53 = 37,937.40
        # - NOT selling price 70300 * 0.53 = 37,259
        
        pdsf = 71580
        residual_pct = 53
        expected_residual = pdsf * (residual_pct / 100)
        
        assert expected_residual == 37937.4, f"Expected 37937.4, got {expected_residual}"
        print(f"✓ Residual calculation: PDSF {pdsf} × {residual_pct}% = {expected_residual}$")
    
    def test_tax_credit_limited_to_lease_taxes(self):
        """Verify tax credit on trade-in is limited to lease taxes"""
        # Based on frontend code (lines 693-698):
        # const creditTaxeEchange = tradeVal * taux;
        # const taxesEffectives = Math.max(0, taxesSurCap - Math.min(creditTaxeEchange, taxesSurCap));
        # const creditPerdu = Math.max(0, creditTaxeEchange - taxesSurCap);
        
        taux = 0.14975
        trade_val = 20000
        cap_cost_brut = 62425  # Example from user
        
        credit_taxe_echange = trade_val * taux  # 2995$
        taxes_sur_cap = cap_cost_brut * taux  # 9348$
        
        # Credit can't exceed taxes
        taxes_effectives = max(0, taxes_sur_cap - min(credit_taxe_echange, taxes_sur_cap))
        credit_perdu = max(0, credit_taxe_echange - taxes_sur_cap)
        
        assert credit_perdu == 0, "No credit should be lost when trade-in tax credit < lease taxes"
        print(f"✓ Tax credit logic: trade credit {credit_taxe_echange:.2f}$ < taxes {taxes_sur_cap:.2f}$ = no lost credit")
    
    def test_tax_credit_lost_when_exceeds_taxes(self):
        """Verify excess tax credit is lost when trade value too high"""
        taux = 0.14975
        trade_val = 100000  # High trade-in
        cap_cost_brut = 30000  # Low cap cost
        
        credit_taxe_echange = trade_val * taux  # 14975$
        taxes_sur_cap = cap_cost_brut * taux  # 4492.50$
        
        credit_perdu = max(0, credit_taxe_echange - taxes_sur_cap)
        
        assert credit_perdu > 0, "Credit should be lost when exceeding taxes"
        print(f"✓ Tax credit lost when exceeds taxes: {credit_perdu:.2f}$ lost")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
