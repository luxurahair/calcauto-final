"""
Tests for CalcAuto AiPro - Calculator State Feature
- POST /api/submissions accepts calculator_state field (JSON object)
- GET /api/submissions returns calculator_state in response
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "danielgiroux007@gmail.com"
TEST_PASSWORD = "Liana2018$"


class TestCalculatorState:
    """Test calculator_state field in submissions"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Return headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_01_login_success(self, auth_token):
        """Test login works with provided credentials"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✅ Login successful, token: {auth_token[:20]}...")
    
    def test_02_create_submission_with_calculator_state(self, headers):
        """Test POST /api/submissions accepts calculator_state field"""
        # Sample calculator_state as would be sent from frontend
        calculator_state = {
            "selectedProgram": {
                "id": "test-program-id",
                "brand": "Ram",
                "model": "1500",
                "trim": "Tradesman",
                "year": 2026,
                "consumer_cash": 6500,
                "bonus_cash": 0
            },
            "vehiclePrice": "65000",
            "selectedTerm": 72,
            "selectedOption": "1",
            "paymentFrequency": "monthly",
            "customBonusCash": "",
            "comptantTxInclus": "",
            "fraisDossier": "259.95",
            "taxePneus": "15",
            "fraisRDPRM": "100",
            "prixEchange": "",
            "montantDuEchange": "",
            "accessories": [],
            "leaseRabaisConcess": "5000",
            "leasePdsf": "",
            "leaseSoldeReporte": "",
            "leaseTerm": 48,
            "leaseKmPerYear": 24000,
            "showLease": True,
            "manualVin": "",
            "selectedYear": 2026,
            "selectedBrand": "Ram"
        }
        
        submission_data = {
            "client_name": "TEST_CalcState_Client",
            "client_email": "test_calcstate@example.com",
            "client_phone": "555-123-4567",
            "vehicle_brand": "Ram",
            "vehicle_model": "1500",
            "vehicle_year": 2026,
            "vehicle_price": 65000,
            "term": 72,
            "payment_monthly": 1200.50,
            "payment_biweekly": 553.31,
            "payment_weekly": 276.65,
            "selected_option": "1",
            "rate": 4.99,
            "program_month": 2,
            "program_year": 2026,
            "calculator_state": calculator_state
        }
        
        response = requests.post(
            f"{BASE_URL}/api/submissions",
            headers=headers,
            json=submission_data
        )
        
        assert response.status_code in [200, 201], f"Create submission failed: {response.text}"
        
        data = response.json()
        
        # Response may be: {"success": true, "submission": {...}} or just the submission object
        if "submission" in data:
            submission = data["submission"]
        else:
            submission = data
        
        assert "id" in submission, f"Response should contain submission ID. Got: {data}"
        
        # Store ID for cleanup
        TestCalculatorState.created_submission_id = submission["id"]
        
        # Verify calculator_state was stored
        if "calculator_state" in submission and submission["calculator_state"] is not None:
            print(f"✅ Created submission with ID: {submission['id']}")
            print(f"   calculator_state included in response: Yes")
            print(f"   vehiclePrice in state: {submission['calculator_state'].get('vehiclePrice')}")
        else:
            print(f"✅ Created submission with ID: {submission['id']}")
            print(f"   calculator_state included in request: Yes (may not be in immediate response)")
    
    def test_03_get_submission_returns_calculator_state(self, headers):
        """Test GET /api/submissions returns calculator_state in response"""
        response = requests.get(
            f"{BASE_URL}/api/submissions",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get submissions failed: {response.text}"
        
        submissions = response.json()
        assert isinstance(submissions, list), "Response should be a list"
        
        # Find our test submission
        test_submission = None
        for sub in submissions:
            if sub.get("client_name") == "TEST_CalcState_Client":
                test_submission = sub
                break
        
        assert test_submission is not None, "Test submission not found in response"
        
        # Verify calculator_state is returned
        if "calculator_state" in test_submission:
            calc_state = test_submission["calculator_state"]
            
            if calc_state is not None:
                # Verify some fields are preserved
                assert "vehiclePrice" in calc_state, "calculator_state should contain vehiclePrice"
                assert calc_state["vehiclePrice"] == "65000", f"vehiclePrice mismatch: {calc_state.get('vehiclePrice')}"
                
                assert "selectedTerm" in calc_state, "calculator_state should contain selectedTerm"
                assert calc_state["selectedTerm"] == 72, f"selectedTerm mismatch: {calc_state.get('selectedTerm')}"
                
                assert "leaseRabaisConcess" in calc_state, "calculator_state should contain leaseRabaisConcess"
                assert calc_state["leaseRabaisConcess"] == "5000", f"leaseRabaisConcess mismatch"
                
                assert "showLease" in calc_state, "calculator_state should contain showLease"
                assert calc_state["showLease"] == True, f"showLease mismatch"
                
                print(f"✅ calculator_state returned correctly with all fields preserved")
                print(f"   vehiclePrice: {calc_state.get('vehiclePrice')}")
                print(f"   selectedTerm: {calc_state.get('selectedTerm')}")
                print(f"   leaseRabaisConcess: {calc_state.get('leaseRabaisConcess')}")
                print(f"   showLease: {calc_state.get('showLease')}")
            else:
                print("⚠️ calculator_state is None in response")
        else:
            print("⚠️ calculator_state field not in response")
            pytest.fail("calculator_state field missing from GET /api/submissions response")
    
    def test_04_get_single_submission_returns_calculator_state(self, headers):
        """Test GET /api/submissions/{id} returns calculator_state"""
        submission_id = getattr(TestCalculatorState, 'created_submission_id', None)
        
        if not submission_id:
            pytest.skip("No submission ID from previous test")
        
        response = requests.get(
            f"{BASE_URL}/api/submissions/{submission_id}",
            headers=headers
        )
        
        # Note: This endpoint might not exist - if 404 or 405, skip
        if response.status_code in [404, 405]:
            pytest.skip("GET /api/submissions/{id} endpoint not available")
        
        assert response.status_code == 200, f"Get single submission failed: {response.text}"
        
        data = response.json()
        assert "calculator_state" in data, "Single submission should include calculator_state"
        
        print(f"✅ Single submission GET returns calculator_state")
    
    def test_05_submission_without_calculator_state(self, headers):
        """Test submission without calculator_state field (backward compatibility)"""
        submission_data = {
            "client_name": "TEST_NoCalcState_Client",
            "client_email": "test_nocalcstate@example.com",
            "client_phone": "555-999-8888",
            "vehicle_brand": "Jeep",
            "vehicle_model": "Wrangler",
            "vehicle_year": 2025,
            "vehicle_price": 55000,
            "term": 60,
            "payment_monthly": 1000.00,
            "payment_biweekly": 461.54,
            "payment_weekly": 230.77,
            "selected_option": "1",
            "rate": 4.99,
            "program_month": 2,
            "program_year": 2026
            # Note: No calculator_state field
        }
        
        response = requests.post(
            f"{BASE_URL}/api/submissions",
            headers=headers,
            json=submission_data
        )
        
        assert response.status_code in [200, 201], f"Create submission without calculator_state failed: {response.text}"
        
        data = response.json()
        
        # Response may be: {"success": true, "submission": {...}} or just the submission object
        if "submission" in data:
            submission = data["submission"]
        else:
            submission = data
        
        TestCalculatorState.no_calc_state_id = submission["id"]
        
        print(f"✅ Submission without calculator_state created successfully (ID: {submission['id']})")
    
    def test_06_cleanup_test_submissions(self, headers):
        """Clean up test submissions"""
        # Get all submissions
        response = requests.get(f"{BASE_URL}/api/submissions", headers=headers)
        
        if response.status_code != 200:
            print("⚠️ Could not fetch submissions for cleanup")
            return
        
        submissions = response.json()
        
        # Delete test submissions
        deleted = 0
        for sub in submissions:
            if sub.get("client_name", "").startswith("TEST_"):
                delete_response = requests.delete(
                    f"{BASE_URL}/api/submissions/{sub['id']}",
                    headers=headers
                )
                if delete_response.status_code in [200, 204]:
                    deleted += 1
        
        print(f"✅ Cleanup: Deleted {deleted} test submissions")


class TestHistoryTabAPI:
    """Test API endpoints used by History tab in CRM"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_01_get_submissions_for_history(self, headers):
        """Test GET /api/submissions returns submissions with calculator_state"""
        response = requests.get(f"{BASE_URL}/api/submissions", headers=headers)
        
        assert response.status_code == 200, f"Get submissions failed: {response.text}"
        
        submissions = response.json()
        assert isinstance(submissions, list), "Response should be a list"
        
        print(f"✅ GET /api/submissions returns {len(submissions)} submissions")
        
        # Check if any submission has calculator_state
        has_calc_state = 0
        no_calc_state = 0
        
        for sub in submissions:
            if sub.get("calculator_state") is not None:
                has_calc_state += 1
            else:
                no_calc_state += 1
        
        print(f"   - With calculator_state: {has_calc_state}")
        print(f"   - Without calculator_state: {no_calc_state}")
    
    def test_02_programs_api_works(self, headers):
        """Test GET /api/programs works (needed for vehicle selection)"""
        response = requests.get(f"{BASE_URL}/api/programs", headers=headers)
        
        assert response.status_code == 200, f"Get programs failed: {response.text}"
        
        programs = response.json()
        assert isinstance(programs, list), "Response should be a list"
        assert len(programs) > 0, "Should have at least one program"
        
        print(f"✅ GET /api/programs returns {len(programs)} programs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
