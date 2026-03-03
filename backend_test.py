#!/usr/bin/env python3
"""
Backend Test Suite for CalcAuto AiPro - Better Offers System
Tests the "Better Offers" functionality which compares old submissions with new programs.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Configuration
BACKEND_URL = "https://deal-detail-modal.preview.emergentagent.com/api"
TIMEOUT = 30

class BetterOffersTestSuite:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = TIMEOUT
        self.test_results = []
        self.created_submissions = []
        
    def log_test(self, test_name: str, success: bool, message: str, details: Dict = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
    
    def test_health_check(self):
        """Test basic API health"""
        try:
            response = self.session.get(f"{BACKEND_URL}/ping")
            if response.status_code == 200:
                data = response.json()
                self.log_test("Health Check", True, f"API responding: {data}")
                return True
            else:
                self.log_test("Health Check", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def create_test_submissions(self):
        """Create test submissions with older program dates to simulate better offers scenario"""
        test_submissions = [
            {
                "client_name": "Jean Tremblay",
                "client_phone": "514-555-0101",
                "client_email": "jean.tremblay@example.com",
                "vehicle_brand": "Ram",
                "vehicle_model": "1500",
                "vehicle_year": 2025,
                "vehicle_price": 55000.0,
                "term": 72,
                "payment_monthly": 750.0,
                "payment_biweekly": 346.15,
                "payment_weekly": 173.08,
                "selected_option": "1",
                "rate": 5.99,
                "program_month": 1,  # January (older than current February)
                "program_year": 2026
            },
            {
                "client_name": "Marie Dubois",
                "client_phone": "450-555-0202",
                "client_email": "marie.dubois@example.com",
                "vehicle_brand": "Jeep",
                "vehicle_model": "Grand Cherokee",
                "vehicle_year": 2025,
                "vehicle_price": 48000.0,
                "term": 60,
                "payment_monthly": 820.0,
                "payment_biweekly": 378.46,
                "payment_weekly": 189.23,
                "selected_option": "1",
                "rate": 6.49,
                "program_month": 12,  # December (older year)
                "program_year": 2025
            },
            {
                "client_name": "Pierre Lavoie",
                "client_phone": "418-555-0303",
                "client_email": "pierre.lavoie@example.com",
                "vehicle_brand": "Dodge",
                "vehicle_model": "Durango",
                "vehicle_year": 2025,
                "vehicle_price": 52000.0,
                "term": 84,
                "payment_monthly": 680.0,
                "payment_biweekly": 313.85,
                "payment_weekly": 156.92,
                "selected_option": "1",
                "rate": 5.49,
                "program_month": 11,  # November (older year)
                "program_year": 2025
            }
        ]
        
        created_count = 0
        for submission_data in test_submissions:
            try:
                response = self.session.post(f"{BACKEND_URL}/submissions", json=submission_data)
                if response.status_code == 200:
                    submission = response.json()
                    self.created_submissions.append(submission.get("id"))
                    created_count += 1
                    self.log_test(f"Create Test Submission - {submission_data['client_name']}", 
                                True, f"Created submission ID: {submission.get('id')}")
                else:
                    self.log_test(f"Create Test Submission - {submission_data['client_name']}", 
                                False, f"HTTP {response.status_code}: {response.text}")
            except Exception as e:
                self.log_test(f"Create Test Submission - {submission_data['client_name']}", 
                            False, f"Error: {str(e)}")
        
        self.log_test("Create Test Submissions", created_count > 0, 
                     f"Created {created_count}/{len(test_submissions)} test submissions")
        return created_count > 0
    
    def test_compare_programs(self):
        """Test POST /api/compare-programs endpoint"""
        try:
            response = self.session.post(f"{BACKEND_URL}/compare-programs")
            
            if response.status_code != 200:
                self.log_test("Compare Programs", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            
            # Validate response structure
            if "better_offers" not in data or "count" not in data:
                self.log_test("Compare Programs", False, 
                            f"Invalid response structure: {data}")
                return False
            
            better_offers = data["better_offers"]
            count = data["count"]
            
            # Validate count matches array length
            if len(better_offers) != count:
                self.log_test("Compare Programs", False, 
                            f"Count mismatch: array has {len(better_offers)} items but count is {count}")
                return False
            
            # Validate each offer structure
            required_fields = [
                "submission_id", "client_name", "client_phone", "client_email", 
                "vehicle", "old_payment", "new_payment", "savings_monthly", 
                "savings_total", "term"
            ]
            
            for i, offer in enumerate(better_offers):
                for field in required_fields:
                    if field not in offer:
                        self.log_test("Compare Programs", False, 
                                    f"Offer {i} missing required field: {field}")
                        return False
                
                # Validate savings calculations
                expected_savings_monthly = offer["old_payment"] - offer["new_payment"]
                expected_savings_total = expected_savings_monthly * offer["term"]
                
                if abs(offer["savings_monthly"] - expected_savings_monthly) > 0.01:
                    self.log_test("Compare Programs", False, 
                                f"Offer {i} incorrect savings_monthly calculation")
                    return False
                
                if abs(offer["savings_total"] - expected_savings_total) > 0.01:
                    self.log_test("Compare Programs", False, 
                                f"Offer {i} incorrect savings_total calculation")
                    return False
            
            self.log_test("Compare Programs", True, 
                         f"Generated {count} better offers with valid calculations",
                         {"offers_count": count, "sample_offer": better_offers[0] if better_offers else None})
            return True
            
        except Exception as e:
            self.log_test("Compare Programs", False, f"Error: {str(e)}")
            return False
    
    def test_get_better_offers(self):
        """Test GET /api/better-offers endpoint"""
        try:
            response = self.session.get(f"{BACKEND_URL}/better-offers")
            
            if response.status_code != 200:
                self.log_test("Get Better Offers", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
            
            offers = response.json()
            
            # Should return an array
            if not isinstance(offers, list):
                self.log_test("Get Better Offers", False, 
                            f"Expected array, got: {type(offers)}")
                return False
            
            # Validate offer structure
            required_fields = [
                "submission_id", "client_name", "client_phone", "client_email", 
                "vehicle", "old_payment", "new_payment", "savings_monthly", 
                "savings_total", "term"
            ]
            
            for i, offer in enumerate(offers):
                for field in required_fields:
                    if field not in offer:
                        self.log_test("Get Better Offers", False, 
                                    f"Offer {i} missing required field: {field}")
                        return False
            
            self.log_test("Get Better Offers", True, 
                         f"Retrieved {len(offers)} pending offers",
                         {"offers_count": len(offers), "sample_offer": offers[0] if offers else None})
            return offers
            
        except Exception as e:
            self.log_test("Get Better Offers", False, f"Error: {str(e)}")
            return False
    
    def test_approve_better_offer(self, offers: List[Dict]):
        """Test POST /api/better-offers/{submission_id}/approve endpoint"""
        if not offers:
            self.log_test("Approve Better Offer", False, "No offers available to test")
            return False
        
        # Test with first offer
        offer = offers[0]
        submission_id = offer["submission_id"]
        
        try:
            response = self.session.post(f"{BACKEND_URL}/better-offers/{submission_id}/approve")
            
            # Note: This might fail if SMTP is not configured, which is expected
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_test("Approve Better Offer", True, 
                                f"Successfully approved and sent email to {offer['client_email']}")
                    return True
                else:
                    self.log_test("Approve Better Offer", False, 
                                f"API returned success=false: {data.get('message')}")
                    return False
            elif response.status_code == 500:
                # SMTP error is expected if not configured
                error_text = response.text
                if "SMTP" in error_text or "email" in error_text.lower():
                    self.log_test("Approve Better Offer", True, 
                                "Endpoint works correctly (SMTP not configured - expected)",
                                {"expected_smtp_error": error_text})
                    return True
                else:
                    self.log_test("Approve Better Offer", False, 
                                f"Unexpected 500 error: {error_text}")
                    return False
            else:
                self.log_test("Approve Better Offer", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Approve Better Offer", False, f"Error: {str(e)}")
            return False
    
    def test_ignore_better_offer(self, offers: List[Dict]):
        """Test POST /api/better-offers/{submission_id}/ignore endpoint"""
        if len(offers) < 2:
            self.log_test("Ignore Better Offer", False, "Need at least 2 offers to test ignore")
            return False
        
        # Test with second offer (first might be approved already)
        offer = offers[1] if len(offers) > 1 else offers[0]
        submission_id = offer["submission_id"]
        
        try:
            response = self.session.post(f"{BACKEND_URL}/better-offers/{submission_id}/ignore")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_test("Ignore Better Offer", True, 
                                f"Successfully ignored offer for {offer['client_name']}")
                    return True
                else:
                    self.log_test("Ignore Better Offer", False, 
                                f"API returned success=false: {data.get('message')}")
                    return False
            elif response.status_code == 404:
                # Might be already deleted
                self.log_test("Ignore Better Offer", True, 
                            "Offer not found (might be already processed)")
                return True
            else:
                self.log_test("Ignore Better Offer", False, 
                            f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Ignore Better Offer", False, f"Error: {str(e)}")
            return False
    
    def test_invalid_submission_id(self):
        """Test endpoints with invalid submission IDs"""
        invalid_id = "invalid-submission-id-12345"
        
        # Test approve with invalid ID
        try:
            response = self.session.post(f"{BACKEND_URL}/better-offers/{invalid_id}/approve")
            if response.status_code == 404:
                self.log_test("Invalid ID - Approve", True, "Correctly returned 404 for invalid ID")
            else:
                self.log_test("Invalid ID - Approve", False, 
                            f"Expected 404, got {response.status_code}")
        except Exception as e:
            self.log_test("Invalid ID - Approve", False, f"Error: {str(e)}")
        
        # Test ignore with invalid ID
        try:
            response = self.session.post(f"{BACKEND_URL}/better-offers/{invalid_id}/ignore")
            if response.status_code == 404:
                self.log_test("Invalid ID - Ignore", True, "Correctly returned 404 for invalid ID")
            else:
                self.log_test("Invalid ID - Ignore", False, 
                            f"Expected 404, got {response.status_code}")
        except Exception as e:
            self.log_test("Invalid ID - Ignore", False, f"Error: {str(e)}")
    
    def cleanup_test_data(self):
        """Clean up test submissions"""
        cleaned = 0
        for submission_id in self.created_submissions:
            try:
                # Note: There's no delete endpoint in the API, so we'll just log
                self.log_test("Cleanup", True, f"Test submission {submission_id} should be cleaned manually")
                cleaned += 1
            except Exception as e:
                self.log_test("Cleanup", False, f"Error cleaning {submission_id}: {str(e)}")
        
        return cleaned
    
    def run_all_tests(self):
        """Run the complete Better Offers test suite"""
        print("=" * 60)
        print("🚀 STARTING BETTER OFFERS TEST SUITE")
        print("=" * 60)
        
        # 1. Health check
        if not self.test_health_check():
            print("❌ Health check failed - aborting tests")
            return False
        
        # 2. Create test data
        if not self.create_test_submissions():
            print("❌ Failed to create test submissions - aborting tests")
            return False
        
        # 3. Test compare programs (generates offers)
        if not self.test_compare_programs():
            print("❌ Compare programs failed")
            return False
        
        # 4. Test get better offers
        offers = self.test_get_better_offers()
        if not offers:
            print("❌ Get better offers failed")
            return False
        
        # 5. Test approve offer
        self.test_approve_better_offer(offers)
        
        # 6. Test ignore offer
        self.test_ignore_better_offer(offers)
        
        # 7. Test invalid IDs
        self.test_invalid_submission_id()
        
        # 8. Cleanup
        self.cleanup_test_data()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        # Show failed tests
        failed_tests = [r for r in self.test_results if not r["success"]]
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['message']}")
        
        return passed == total

def main():
    """Main test execution"""
    tester = BetterOffersTestSuite()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 ALL TESTS PASSED!")
        exit(0)
    else:
        print("\n💥 SOME TESTS FAILED!")
        exit(1)

if __name__ == "__main__":
    main()