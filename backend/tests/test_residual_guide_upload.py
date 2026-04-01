"""
Tests for the upload-residual-guide endpoint with auto-detection features.
Tests:
1. Auto-detection of month/year from PDF content
2. KM adjustments extraction from last page
3. Comparison with existing data
4. File naming with French month names
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://toc-extraction-fix.preview.emergentagent.com').rstrip('/')
ADMIN_PASSWORD = "Liana2018"
TEST_PDF_PATH = "/app/april_2026_residual.pdf"


class TestResidualGuideUpload:
    """Tests for POST /api/upload-residual-guide endpoint"""

    @pytest.fixture
    def pdf_file(self):
        """Load the test PDF file"""
        if not os.path.exists(TEST_PDF_PATH):
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")
        return open(TEST_PDF_PATH, 'rb')

    def test_upload_with_auto_detection(self, pdf_file):
        """Test 1-6: Upload with ONLY file and password - should auto-detect month/year"""
        files = {'file': ('april_2026_residual.pdf', pdf_file, 'application/pdf')}
        data = {'password': ADMIN_PASSWORD}
        
        response = requests.post(
            f"{BASE_URL}/api/upload-residual-guide",
            files=files,
            data=data,
            timeout=120
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:2000]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get('success') == True, f"Expected success=True, got {result}"
        
        # Test 1: Auto-detection of month/year
        # Response has detected_month and detected_year as separate fields
        assert 'detected_month' in result, f"Missing 'detected_month' in response: {result.keys()}"
        assert 'detected_year' in result, f"Missing 'detected_year' in response: {result.keys()}"
        
        detected_month = result['detected_month']
        detected_year = result['detected_year']
        print(f"Detected: month={detected_month}, year={detected_year}")
        
        # The PDF contains "MARCH 2026" so should detect month=3, year=2026
        assert detected_month == 3, f"Expected month=3 (March), got {detected_month}"
        assert detected_year == 2026, f"Expected year=2026, got {detected_year}"
        
        # Test 2: Response should include 'detected_period' field (string format)
        assert 'detected_period' in result, f"Missing 'detected_period' in response: {result.keys()}"
        detected_period = result['detected_period']
        print(f"Detected period: {detected_period}")
        assert 'Mars' in detected_period or 'mars' in detected_period.lower(), f"Expected 'Mars' in detected_period, got {detected_period}"
        
        # Test 3: Response should include 'changes' object
        assert 'changes' in result, f"Missing 'changes' in response: {result.keys()}"
        changes = result['changes']
        assert 'new_vehicles' in changes, f"Missing 'new_vehicles' in changes"
        assert 'modified_vehicles' in changes, f"Missing 'modified_vehicles' in changes"
        assert 'unchanged_vehicles' in changes, f"Missing 'unchanged_vehicles' in changes"
        print(f"Changes: new={changes.get('new_vehicles')}, modified={changes.get('modified_vehicles')}, unchanged={changes.get('unchanged_vehicles')}")
        
        # Test 4: KM adjustments should be extracted
        assert 'km_adjustments' in result, f"Missing 'km_adjustments' in response: {result.keys()}"
        km_adj = result['km_adjustments']
        assert km_adj.get('source') == 'residual_guide', f"Expected source='residual_guide', got {km_adj.get('source')}"
        
        # Test 5: KM adjustments should have correct values (12k_60mo=5, 18k_60mo=4)
        print(f"KM adjustments: {km_adj}")
        assert km_adj.get('12k_60mo') == 5, f"Expected 12k_60mo=5, got {km_adj.get('12k_60mo')}"
        assert km_adj.get('18k_60mo') == 4, f"Expected 18k_60mo=4, got {km_adj.get('18k_60mo')}"
        
        # Test 6: File should be saved with French month name
        assert 'json_file' in result, f"Missing 'json_file' in response"
        json_file = result.get('json_file', '')
        print(f"Saved file: {json_file}")
        assert 'mars2026' in json_file.lower(), f"Expected file name with 'mars2026', got {json_file}"

    def test_upload_wrong_password(self, pdf_file):
        """Test that wrong password returns 401"""
        files = {'file': ('april_2026_residual.pdf', pdf_file, 'application/pdf')}
        data = {'password': 'wrong_password'}
        
        response = requests.post(
            f"{BASE_URL}/api/upload-residual-guide",
            files=files,
            data=data,
            timeout=30
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestSCIResidualsAPI:
    """Tests for GET /api/sci/residuals endpoint"""

    def test_get_residuals_march_2026(self):
        """Test 7: GET /api/sci/residuals?month=3&year=2026 should return new data"""
        response = requests.get(
            f"{BASE_URL}/api/sci/residuals",
            params={'month': 3, 'year': 2026},
            timeout=30
        )
        
        print(f"Response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Should have vehicles
        assert 'vehicles' in data, f"Missing 'vehicles' in response"
        vehicles = data.get('vehicles', [])
        print(f"Total vehicles: {len(vehicles)}")
        assert len(vehicles) > 0, "Expected at least some vehicles"
        
        # Should have km_adjustments
        assert 'km_adjustments' in data, f"Missing 'km_adjustments' in response"
        km_adj = data.get('km_adjustments', {})
        print(f"KM adjustments source: {km_adj.get('source')}")
        
        # Test 8: Check Ram 1500 Laramie Crew Cab LWB 4WD has 60mo base residual of 46%
        ram_1500_laramie = None
        for v in vehicles:
            if (v.get('brand', '').lower() == 'ram' and 
                '1500' in v.get('model_name', '') and 
                'laramie' in v.get('trim', '').lower() and
                'crew cab lwb 4wd' in v.get('body_style', '').lower()):
                ram_1500_laramie = v
                break
        
        if ram_1500_laramie:
            residuals = ram_1500_laramie.get('residual_percentages', {})
            residual_60 = residuals.get('60')
            print(f"Ram 1500 Laramie Crew Cab LWB 4WD 60mo residual: {residual_60}%")
            assert residual_60 == 46, f"Expected 60mo residual=46%, got {residual_60}%"
        else:
            print("WARNING: Ram 1500 Laramie Crew Cab LWB 4WD not found in vehicles")
            # List some Ram vehicles for debugging
            ram_vehicles = [v for v in vehicles if v.get('brand', '').lower() == 'ram']
            print(f"Found {len(ram_vehicles)} Ram vehicles")
            for rv in ram_vehicles[:5]:
                print(f"  - {rv.get('model_name')} {rv.get('trim')} {rv.get('body_style')}")
            pytest.fail("Ram 1500 Laramie Crew Cab LWB 4WD not found")

    def test_get_residuals_latest(self):
        """Test GET /api/sci/residuals without params returns latest data"""
        response = requests.get(
            f"{BASE_URL}/api/sci/residuals",
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'vehicles' in data
        assert 'km_adjustments' in data


class TestKMAdjustmentsExtraction:
    """Tests for KM adjustments extraction from residual guide"""

    def test_km_adjustments_file_created(self):
        """Verify km_adjustments file was created with correct values"""
        km_path = "/app/backend/data/km_adjustments_mar2026.json"
        
        if not os.path.exists(km_path):
            pytest.skip(f"KM adjustments file not found: {km_path}")
        
        with open(km_path, 'r') as f:
            data = json.load(f)
        
        print(f"KM adjustments data: {json.dumps(data, indent=2)}")
        
        assert data.get('source') == 'residual_guide', f"Expected source='residual_guide'"
        assert data.get('standard_km') == 24000
        
        adjustments = data.get('adjustments', {})
        assert '12000' in adjustments
        assert '18000' in adjustments
        
        # Verify specific values
        assert adjustments['12000'].get('60') == 5
        assert adjustments['18000'].get('60') == 4

    def test_residuals_file_has_french_name(self):
        """Test 6: Verify file saved as sci_residuals_mars2026.json"""
        mars_path = "/app/backend/data/sci_residuals_mars2026.json"
        
        assert os.path.exists(mars_path), f"Expected file {mars_path} to exist"
        
        with open(mars_path, 'r') as f:
            data = json.load(f)
        
        assert 'vehicles' in data
        print(f"Mars 2026 residuals file has {len(data.get('vehicles', []))} vehicles")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
