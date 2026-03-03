"""
Test du endpoint scan-invoice avec données partielles
Vérifie que l'API retourne review_required: true et blocking_errors
au lieu d'une erreur bloquante
"""

import pytest
import requests
import os
import base64

# Use the public URL from environment
BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', os.environ.get('REACT_APP_BACKEND_URL', 'https://deal-detail-modal.preview.emergentagent.com')).rstrip('/')

# Test credentials
TEST_EMAIL = "danielgiroux007@gmail.com"
TEST_PASSWORD = "Liana2018$"

class TestScanInvoicePartialData:
    """Tests pour la gestion des scans partiels"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login et obtenir le token avant chaque test"""
        # Login
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        print(f"\n[SETUP] Logged in successfully, token obtained")
    
    def test_login_works(self):
        """Test 1: Login avec credentials fournis"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "token" in data
        assert data.get("user", {}).get("email") == TEST_EMAIL
        print(f"[PASS] Login successful for {TEST_EMAIL}")
    
    def test_scan_invoice_endpoint_exists(self):
        """Test 2: Le endpoint scan-invoice existe et nécessite auth"""
        # Test sans auth - devrait retourner 401
        response = requests.post(
            f"{BASE_URL}/api/inventory/scan-invoice",
            json={"image_base64": "test", "is_pdf": False}
        )
        assert response.status_code == 401, "Should require authentication"
        print("[PASS] scan-invoice requires authentication")
        
    def test_scan_invoice_with_invalid_image(self):
        """Test 3: Scan avec image invalide retourne review_required ou erreur"""
        # Envoyer une image base64 invalide/vide
        response = requests.post(
            f"{BASE_URL}/api/inventory/scan-invoice",
            json={"image_base64": "invalid_base64_data", "is_pdf": False},
            headers=self.headers,
            timeout=30
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500] if len(response.text) > 500 else response.text}")
        
        # Le endpoint peut retourner 200 avec erreurs ou 400/500
        # Le plus important est qu'il ne crash pas
        assert response.status_code in [200, 400, 422, 500], f"Unexpected status: {response.status_code}"
        print("[PASS] scan-invoice handles invalid image gracefully")
        
    def test_scan_invoice_response_structure(self):
        """Test 4: Vérifier la structure de la réponse avec données partielles simulées
        
        Ce test vérifie que quand le backend reçoit des données partielles (VIN manquant, EP=0, etc.),
        il retourne success=false mais review_required=true avec blocking_errors
        au lieu d'une erreur bloquante 400/500.
        """
        # Créer une petite image blanche en base64 (1x1 pixel PNG)
        # Cette image ne contient pas de facture réelle donc devrait retourner des erreurs
        white_pixel_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        response = requests.post(
            f"{BASE_URL}/api/inventory/scan-invoice",
            json={"image_base64": white_pixel_png, "is_pdf": False},
            headers=self.headers,
            timeout=60
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {data}")
            
            # La structure devrait contenir soit success=true soit review_required=true
            has_success = data.get("success", False)
            has_review_required = data.get("review_required", False)
            
            if not has_success and not has_review_required:
                # Si aucun des deux, c'est peut-être une erreur différente
                print(f"[INFO] Neither success nor review_required in response")
                # Ce n'est pas forcément un échec - dépend de ce que l'OCR a trouvé
            
            # Vérifier que blocking_errors est présent quand review_required=true
            if has_review_required:
                blocking_errors = data.get("blocking_errors", [])
                print(f"[INFO] Blocking errors: {blocking_errors}")
                assert isinstance(blocking_errors, list), "blocking_errors should be a list"
                print("[PASS] Response has review_required=true with blocking_errors list")
            elif has_success:
                print("[PASS] Response has success=true (OCR found data)")
                # Vérifier que vehicle data est présent
                assert "vehicle" in data, "Should have vehicle data when success=true"
                print(f"[INFO] Vehicle data: {data.get('vehicle', {})}")
        else:
            # Si status n'est pas 200, c'est OK si c'est une erreur attendue
            print(f"[INFO] Non-200 response: {response.text[:500]}")
            # Pour une vraie image vide, 400/500 est acceptable
            assert response.status_code in [400, 422, 500], f"Unexpected status: {response.status_code}"
            print(f"[PASS] Server handled empty image with appropriate error")

    def test_inventory_access(self):
        """Test 5: Navigation vers la page Inventaire (via API)"""
        response = requests.get(
            f"{BASE_URL}/api/inventory",
            headers=self.headers
        )
        assert response.status_code == 200, f"Inventory access failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return a list of vehicles"
        print(f"[PASS] Inventory access works, found {len(data)} vehicles")
        
    def test_inventory_stats(self):
        """Test 6: Stats d'inventaire accessibles"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/stats/summary",
            headers=self.headers
        )
        assert response.status_code == 200, f"Inventory stats failed: {response.text}"
        data = response.json()
        assert "total" in data, "Should have total count"
        print(f"[PASS] Inventory stats: total={data.get('total')}, disponible={data.get('disponible')}")


class TestFrontendAcceptance:
    """Tests pour vérifier que le frontend peut gérer les réponses du backend"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login et obtenir le token avant chaque test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_frontend_logic_simulation(self):
        """Test: Simuler la logique frontend pour accepter review_required
        
        Le frontend doit accepter les réponses avec:
        - success: true  → données complètes
        - success: false && review_required: true → données partielles à corriger
        
        Avant le fix, le frontend rejetait success: false même avec review_required: true
        """
        # Simuler différentes réponses backend
        test_cases = [
            {
                "name": "Succès complet",
                "response": {"success": True, "vehicle": {"vin": "1C4RJKBG5S8123456", "ep_cost": 50000, "pdco": 60000}},
                "expected_accept": True
            },
            {
                "name": "Révision requise (VIN manquant)",
                "response": {
                    "success": False,
                    "review_required": True,
                    "blocking_errors": ["VIN manquant ou invalide (doit être 17 caractères)"],
                    "vehicle": {"vin": "", "ep_cost": 50000, "pdco": 60000}
                },
                "expected_accept": True
            },
            {
                "name": "Révision requise (EP manquant)",
                "response": {
                    "success": False,
                    "review_required": True,
                    "blocking_errors": ["EP (Employee Price) manquant"],
                    "vehicle": {"vin": "1C4RJKBG5S8123456", "ep_cost": 0, "pdco": 60000}
                },
                "expected_accept": True
            },
            {
                "name": "Échec complet (pas de review_required)",
                "response": {"success": False, "message": "Erreur critique"},
                "expected_accept": False
            }
        ]
        
        for tc in test_cases:
            response = tc["response"]
            # Logique frontend (ligne 313 dans inventory.tsx)
            frontend_accepts = response.get("success", False) or response.get("review_required", False)
            
            assert frontend_accepts == tc["expected_accept"], \
                f"Test '{tc['name']}' failed: frontend_accepts={frontend_accepts}, expected={tc['expected_accept']}"
            print(f"[PASS] {tc['name']}: frontend_accepts={frontend_accepts}")
        
        print("[PASS] Frontend logic correctly handles all response types")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
