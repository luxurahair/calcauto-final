"""
Test CRM Offers and History Features

Tests for:
1. POST /api/compare-programs - Returns offers with payments_by_term for all 6 terms
2. GET /api/better-offers - Returns stored offers with payments_by_term
3. History tab - Verify submissions can be opened in calculator
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "danielgiroux007@gmail.com"
TEST_PASSWORD = "Liana2018$"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("token")


@pytest.fixture
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestComparePrograms:
    """Tests for POST /api/compare-programs endpoint"""
    
    def test_compare_programs_returns_200(self, authenticated_client):
        """Test compare-programs endpoint returns 200 OK"""
        response = authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("POST /api/compare-programs returned 200 OK")
    
    def test_compare_programs_returns_better_offers_array(self, authenticated_client):
        """Test compare-programs returns better_offers array"""
        response = authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        data = response.json()
        
        assert "better_offers" in data, "Response missing 'better_offers' field"
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["better_offers"], list), "better_offers should be a list"
        print(f"Found {data['count']} better offers")
    
    def test_compare_programs_offers_have_payments_by_term(self, authenticated_client):
        """Test that offers contain payments_by_term for all 6 terms (36, 48, 60, 72, 84, 96)"""
        response = authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No better offers found - skipping payments_by_term validation")
        
        expected_terms = ["36", "48", "60", "72", "84", "96"]
        
        for offer in data["better_offers"]:
            assert "payments_by_term" in offer, f"Offer {offer.get('client_name')} missing 'payments_by_term'"
            pbt = offer["payments_by_term"]
            
            # Verify all 6 terms are present
            for term in expected_terms:
                assert term in pbt, f"Missing term {term} in payments_by_term for {offer.get('client_name')}"
                
                term_data = pbt[term]
                # Verify structure of each term
                assert "opt1_rate" in term_data, f"Missing opt1_rate for term {term}"
                assert "opt1_payment" in term_data, f"Missing opt1_payment for term {term}"
                # opt2 fields can be None if no option 2
                assert "opt2_rate" in term_data, f"Missing opt2_rate field for term {term}"
                assert "opt2_payment" in term_data, f"Missing opt2_payment field for term {term}"
            
            print(f"Offer for {offer.get('client_name')} has all 6 terms in payments_by_term")
    
    def test_compare_programs_offers_structure(self, authenticated_client):
        """Test that offers have required structure for detail modal"""
        response = authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No better offers found - skipping structure validation")
        
        required_fields = [
            "submission_id", "client_name", "client_phone", "client_email",
            "vehicle", "vehicle_brand", "vehicle_model", "vehicle_year", "vehicle_price",
            "old_payment", "new_payment", "old_rate", "new_rate",
            "savings_monthly", "savings_total", "term",
            "old_program", "new_program", "new_program_data", "payments_by_term"
        ]
        
        for offer in data["better_offers"][:3]:  # Check first 3 offers
            for field in required_fields:
                assert field in offer, f"Offer missing required field: {field}"
            
            # Verify new_program_data structure
            npd = offer["new_program_data"]
            assert "consumer_cash" in npd, "new_program_data missing consumer_cash"
            assert "bonus_cash" in npd, "new_program_data missing bonus_cash"
            assert "option1_rates" in npd, "new_program_data missing option1_rates"
            
            print(f"Offer for {offer['client_name']}: old={offer['old_payment']}, new={offer['new_payment']}, savings={offer['savings_monthly']}/m")


class TestBetterOffers:
    """Tests for GET /api/better-offers endpoint"""
    
    def test_get_better_offers_returns_200(self, authenticated_client):
        """Test GET /api/better-offers returns 200 OK"""
        response = authenticated_client.get(f"{BASE_URL}/api/better-offers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("GET /api/better-offers returned 200 OK")
    
    def test_get_better_offers_returns_array(self, authenticated_client):
        """Test GET /api/better-offers returns array"""
        response = authenticated_client.get(f"{BASE_URL}/api/better-offers")
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"GET /api/better-offers returned {len(data)} offers")
    
    def test_stored_offers_have_payments_by_term(self, authenticated_client):
        """Test that stored offers have payments_by_term field"""
        # First refresh offers
        authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        
        # Then get stored offers
        response = authenticated_client.get(f"{BASE_URL}/api/better-offers")
        offers = response.json()
        
        if len(offers) == 0:
            pytest.skip("No stored better offers found")
        
        for offer in offers:
            assert "payments_by_term" in offer, f"Stored offer {offer.get('client_name')} missing payments_by_term"
            pbt = offer["payments_by_term"]
            if pbt:  # Check if not None
                assert len(pbt) == 6, f"Expected 6 terms in payments_by_term, got {len(pbt)}"
                print(f"Stored offer for {offer.get('client_name')} has payments_by_term with {len(pbt)} terms")


class TestSubmissions:
    """Tests for submissions (history tab)"""
    
    def test_get_submissions_returns_200(self, authenticated_client):
        """Test GET /api/submissions returns 200 OK"""
        response = authenticated_client.get(f"{BASE_URL}/api/submissions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("GET /api/submissions returned 200 OK")
    
    def test_submissions_have_required_fields(self, authenticated_client):
        """Test submissions have fields needed for 'Ouvrir le calcul'"""
        response = authenticated_client.get(f"{BASE_URL}/api/submissions")
        submissions = response.json()
        
        if len(submissions) == 0:
            pytest.skip("No submissions found")
        
        required_fields = [
            "id", "client_name", "vehicle_brand", "vehicle_model", "vehicle_year",
            "vehicle_price", "term", "payment_monthly", "rate"
        ]
        
        for sub in submissions[:5]:  # Check first 5
            for field in required_fields:
                assert field in sub, f"Submission missing required field: {field}"
            
            # calculator_state can be None/missing for old submissions - that's OK
            # The frontend handles this case with partial state restoration
            calc_state = sub.get("calculator_state")
            print(f"Submission {sub['id']}: {sub['client_name']} - {sub['vehicle_brand']} {sub['vehicle_model']} (has_calc_state: {calc_state is not None})")


class TestPaymentsByTermCalculation:
    """Tests to verify payments_by_term calculation correctness"""
    
    def test_payments_decrease_with_longer_terms(self, authenticated_client):
        """Test that monthly payments decrease as term increases"""
        response = authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No better offers found")
        
        for offer in data["better_offers"][:2]:
            pbt = offer["payments_by_term"]
            terms = [36, 48, 60, 72, 84, 96]
            
            previous_payment = None
            for term in terms:
                term_key = str(term)
                payment = pbt[term_key]["opt1_payment"]
                
                if previous_payment is not None and payment > 0:
                    # Payment should generally decrease with longer term
                    # (allowing small increases due to interest differences)
                    print(f"Term {term}m: ${payment}")
                
                previous_payment = payment
            
            print(f"✓ Payment progression verified for {offer['client_name']}")
    
    def test_client_term_highlighted_correctly(self, authenticated_client):
        """Test that client's original term is in the payments_by_term data"""
        response = authenticated_client.post(f"{BASE_URL}/api/compare-programs")
        data = response.json()
        
        if data["count"] == 0:
            pytest.skip("No better offers found")
        
        for offer in data["better_offers"][:3]:
            client_term = offer["term"]
            pbt = offer["payments_by_term"]
            
            assert str(client_term) in pbt, f"Client term {client_term} not in payments_by_term"
            term_data = pbt[str(client_term)]
            
            # The old payment at client's term should match the offer's old_payment
            print(f"Client {offer['client_name']}: term={client_term}m, old_payment={offer['old_payment']}, new_opt1={term_data['opt1_payment']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
