"""
Test suite for CalcAuto AiPro - Residual Guide Upload System
Tests:
1. POST /api/upload-residual-guide - Upload PDF, parse, save JSON, send email
2. Verify JSON file is saved to /app/backend/data/
3. GET /api/sci/vehicle-hierarchy - Verify hierarchy after upload
"""
import pytest
import requests
import os
import json
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')
ADMIN_PASSWORD = "Liana2018"
TEST_PDF_PATH = "/app/sci_residual_guide.pdf"

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    return session


class TestResidualGuideUpload:
    """Test the residual guide upload endpoint"""
    
    def test_upload_residual_guide_success(self, api_client):
        """Test uploading a valid PDF file returns success with vehicle count"""
        # Skip if PDF doesn't exist
        if not os.path.exists(TEST_PDF_PATH):
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")
        
        url = f"{BASE_URL}/api/upload-residual-guide"
        
        with open(TEST_PDF_PATH, 'rb') as pdf_file:
            files = {'file': ('sci_residual_guide.pdf', pdf_file, 'application/pdf')}
            data = {
                'password': ADMIN_PASSWORD,
                'effective_month': '2',
                'effective_year': '2026'
            }
            
            response = api_client.post(url, files=files, data=data, timeout=120)
        
        # Check status code
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Check response structure
        result = response.json()
        assert result.get('success') == True, f"Expected success=True, got {result}"
        assert 'total_vehicles' in result, f"Missing total_vehicles in response: {result}"
        assert result['total_vehicles'] > 0, f"Expected some vehicles, got {result['total_vehicles']}"
        
        # Check brands breakdown
        assert 'brands' in result, f"Missing brands in response: {result}"
        brands = result['brands']
        assert len(brands) > 0, f"Expected some brands, got {brands}"
        
        # Verify Stellantis brands are present (at least some)
        expected_brands = ['Chrysler', 'Dodge', 'Jeep', 'Ram', 'Fiat']
        found_brands = list(brands.keys())
        assert any(b in found_brands for b in expected_brands), f"Expected at least one Stellantis brand in {found_brands}"
        
        print(f"SUCCESS: Uploaded residual guide - {result['total_vehicles']} vehicles")
        print(f"Brands: {brands}")
        print(f"Email sent: {result.get('email_sent', False)}")
    
    def test_upload_residual_guide_wrong_password(self, api_client):
        """Test upload with wrong password returns 401"""
        if not os.path.exists(TEST_PDF_PATH):
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")
        
        url = f"{BASE_URL}/api/upload-residual-guide"
        
        with open(TEST_PDF_PATH, 'rb') as pdf_file:
            files = {'file': ('sci_residual_guide.pdf', pdf_file, 'application/pdf')}
            data = {
                'password': 'wrong_password',
                'effective_month': '2',
                'effective_year': '2026'
            }
            
            response = api_client.post(url, files=files, data=data, timeout=30)
        
        assert response.status_code == 401, f"Expected 401 for wrong password, got {response.status_code}"
        print("SUCCESS: Wrong password correctly rejected with 401")
    
    def test_upload_residual_guide_missing_password(self, api_client):
        """Test upload without password returns 422"""
        if not os.path.exists(TEST_PDF_PATH):
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")
        
        url = f"{BASE_URL}/api/upload-residual-guide"
        
        with open(TEST_PDF_PATH, 'rb') as pdf_file:
            files = {'file': ('sci_residual_guide.pdf', pdf_file, 'application/pdf')}
            data = {
                'effective_month': '2',
                'effective_year': '2026'
            }
            
            response = api_client.post(url, files=files, data=data, timeout=30)
        
        # 422 = Unprocessable Entity (missing required field)
        assert response.status_code == 422, f"Expected 422 for missing password, got {response.status_code}"
        print("SUCCESS: Missing password correctly rejected with 422")


class TestVehicleHierarchy:
    """Test the vehicle hierarchy endpoint after upload"""
    
    def test_get_vehicle_hierarchy(self, api_client):
        """Test GET /api/sci/vehicle-hierarchy returns valid hierarchy
        
        Structure: {
            "Chrysler": {"Grand Caravan": {...}, "Pacifica": {...}},
            "Dodge": {...},
            ...
        }
        """
        url = f"{BASE_URL}/api/sci/vehicle-hierarchy"
        response = api_client.get(url, timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        
        # Result should be a dict with brand names as keys
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert len(result) > 0, f"Expected some brands, got empty dict"
        
        # Check for expected Stellantis brands
        expected_brands = ['Chrysler', 'Dodge', 'Jeep', 'Ram', 'Fiat']
        found_brands = list(result.keys())
        
        # At least 3 brands should be present
        matching_brands = [b for b in expected_brands if b in found_brands]
        assert len(matching_brands) >= 3, f"Expected at least 3 Stellantis brands, got {found_brands}"
        
        # Each brand should have models (as dict with model names as keys)
        for brand_name in found_brands[:3]:
            brand_data = result[brand_name]
            assert isinstance(brand_data, dict), f"Brand {brand_name} should be dict, got {type(brand_data)}"
            assert len(brand_data) > 0, f"Brand {brand_name} should have models"
        
        print(f"SUCCESS: Vehicle hierarchy returned {len(found_brands)} brands")
        print(f"Brands: {found_brands}")
    
    def test_vehicle_hierarchy_structure(self, api_client):
        """Test that hierarchy has correct nested structure: brand->model->trims->body_styles"""
        url = f"{BASE_URL}/api/sci/vehicle-hierarchy"
        response = api_client.get(url, timeout=10)
        
        assert response.status_code == 200
        result = response.json()
        
        # Result is dict: {brand_name: {model_name: {...}}}
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert len(result) > 0, "No brands found"
        
        # Pick a brand and check model structure
        brand_name = list(result.keys())[0]
        brand_models = result[brand_name]
        assert isinstance(brand_models, dict), f"Brand models should be dict"
        
        # Pick a model and check structure
        model_name = list(brand_models.keys())[0]
        model_data = brand_models[model_name]
        
        print(f"Testing brand: {brand_name}, model: {model_name}")
        print(f"Model data keys: {list(model_data.keys())}")
        
        # Model should have trims and years
        assert 'trims' in model_data, f"Model should have 'trims' key"
        assert 'years' in model_data, f"Model should have 'years' key"
        
        # Trims is a dict: {trim_name: [body_styles]}
        trims = model_data['trims']
        assert isinstance(trims, dict), f"Trims should be dict"
        
        if trims:
            trim_name = list(trims.keys())[0]
            body_styles = trims[trim_name]
            assert isinstance(body_styles, list), f"Body styles should be list"
            print(f"Sample trim: {trim_name} -> Body styles: {body_styles}")
        
        # Years is a list
        years = model_data['years']
        assert isinstance(years, list), f"Years should be list"
        assert all(isinstance(y, int) for y in years), f"Years should be integers"
        
        print(f"SUCCESS: Model structure valid - {len(trims)} trims, years: {years}")


class TestVerifyPasswordEndpoint:
    """Test the verify-password endpoint used by import page"""
    
    def test_verify_password_success(self, api_client):
        """Test correct password verification"""
        url = f"{BASE_URL}/api/verify-password"
        
        # The endpoint expects form data
        data = {'password': ADMIN_PASSWORD}
        response = api_client.post(url, data=data, timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("SUCCESS: Password verification passed")
    
    def test_verify_password_failure(self, api_client):
        """Test wrong password rejection"""
        url = f"{BASE_URL}/api/verify-password"
        
        data = {'password': 'wrong_password'}
        response = api_client.post(url, data=data, timeout=10)
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("SUCCESS: Wrong password correctly rejected")


class TestJSONFilePersistence:
    """Test that JSON files are correctly saved"""
    
    def test_json_file_exists_after_upload(self):
        """Test that JSON file exists in /app/backend/data/ after upload"""
        data_dir = Path("/app/backend/data")
        
        # Look for any sci_residuals file
        residual_files = list(data_dir.glob("sci_residuals_*.json"))
        assert len(residual_files) > 0, f"No sci_residuals JSON files found in {data_dir}"
        
        # Check latest file
        latest_file = sorted(residual_files)[-1]
        print(f"Found residual file: {latest_file}")
        
        # Verify JSON structure
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        assert 'vehicles' in data, f"Missing 'vehicles' key in JSON: {data.keys()}"
        assert 'km_adjustments' in data, f"Missing 'km_adjustments' key in JSON"
        
        vehicles = data['vehicles']
        assert len(vehicles) > 0, "No vehicles in JSON file"
        
        # Check vehicle structure
        vehicle = vehicles[0]
        required_fields = ['brand', 'model_year', 'model_name', 'trim', 'body_style', 'residual_percentages']
        for field in required_fields:
            assert field in vehicle, f"Missing '{field}' in vehicle: {vehicle.keys()}"
        
        # Check residual percentages has expected terms
        residuals = vehicle['residual_percentages']
        expected_terms = ['24', '27', '36', '39', '42', '48', '51', '54', '60']
        for term in expected_terms:
            assert term in residuals, f"Missing term '{term}' in residual_percentages"
        
        print(f"SUCCESS: JSON file valid with {len(vehicles)} vehicles")
        print(f"Sample vehicle: {vehicle['brand']} {vehicle['model_name']} {vehicle['trim']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
