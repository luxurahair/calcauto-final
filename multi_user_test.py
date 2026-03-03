#!/usr/bin/env python3
"""
Comprehensive User Isolation Test - Tests with multiple users
"""

import requests
import json
import uuid
from datetime import datetime

BACKEND_URL = "https://deal-detail-modal.preview.emergentagent.com/api"

def test_multi_user_isolation():
    print("🔒 MULTI-USER DATA ISOLATION TEST")
    print("=" * 50)
    
    # Create two test users
    user1_email = f"testuser1_{uuid.uuid4().hex[:8]}@test.com"
    user2_email = f"testuser2_{uuid.uuid4().hex[:8]}@test.com"
    
    print(f"Creating test users:")
    print(f"User 1: {user1_email}")
    print(f"User 2: {user2_email}")
    print()
    
    # Register User 1
    user1_data = {
        "name": "Test User 1",
        "email": user1_email,
        "password": "testpass123"
    }
    
    response = requests.post(f"{BACKEND_URL}/auth/register", json=user1_data)
    if response.status_code != 200:
        print(f"❌ Failed to register User 1: {response.status_code} - {response.text}")
        return False
        
    user1_info = response.json()
    user1_token = user1_info["token"]
    user1_id = user1_info["user"]["id"]
    print(f"✅ User 1 registered: {user1_id}")
    
    # Register User 2
    user2_data = {
        "name": "Test User 2", 
        "email": user2_email,
        "password": "testpass123"
    }
    
    response = requests.post(f"{BACKEND_URL}/auth/register", json=user2_data)
    if response.status_code != 200:
        print(f"❌ Failed to register User 2: {response.status_code} - {response.text}")
        return False
        
    user2_info = response.json()
    user2_token = user2_info["token"]
    user2_id = user2_info["user"]["id"]
    print(f"✅ User 2 registered: {user2_id}")
    print()
    
    # User 1 creates contacts
    print("User 1 creating contacts...")
    user1_headers = {"Authorization": f"Bearer {user1_token}"}
    
    user1_contacts = [
        {"name": "User1 Contact A", "phone": "5141111111", "email": "contact1a@test.com", "source": "manual"},
        {"name": "User1 Contact B", "phone": "5141111112", "email": "contact1b@test.com", "source": "manual"}
    ]
    
    for contact in user1_contacts:
        response = requests.post(f"{BACKEND_URL}/contacts", json=contact, headers=user1_headers)
        if response.status_code in [200, 201]:
            print(f"✅ User 1 created: {contact['name']}")
        else:
            print(f"❌ Failed to create contact for User 1: {response.status_code}")
    
    # User 2 creates contacts
    print("\nUser 2 creating contacts...")
    user2_headers = {"Authorization": f"Bearer {user2_token}"}
    
    user2_contacts = [
        {"name": "User2 Contact X", "phone": "5142222221", "email": "contact2x@test.com", "source": "manual"},
        {"name": "User2 Contact Y", "phone": "5142222222", "email": "contact2y@test.com", "source": "manual"}
    ]
    
    for contact in user2_contacts:
        response = requests.post(f"{BACKEND_URL}/contacts", json=contact, headers=user2_headers)
        if response.status_code in [200, 201]:
            print(f"✅ User 2 created: {contact['name']}")
        else:
            print(f"❌ Failed to create contact for User 2: {response.status_code}")
    
    print()
    
    # Test isolation - User 1 should only see their contacts
    print("Testing User 1 contact isolation...")
    response = requests.get(f"{BACKEND_URL}/contacts", headers=user1_headers)
    if response.status_code == 200:
        user1_retrieved_contacts = response.json()
        user1_contact_names = [c["name"] for c in user1_retrieved_contacts]
        
        print(f"User 1 sees {len(user1_retrieved_contacts)} contacts: {user1_contact_names}")
        
        # Check if User 1 can see any of User 2's contacts
        user2_names_in_user1 = [name for name in user1_contact_names if "User2" in name]
        if user2_names_in_user1:
            print(f"❌ ISOLATION BREACH: User 1 can see User 2's contacts: {user2_names_in_user1}")
            return False
        else:
            print("✅ User 1 isolation working - cannot see User 2's contacts")
    else:
        print(f"❌ Failed to get User 1 contacts: {response.status_code}")
        return False
    
    # Test isolation - User 2 should only see their contacts
    print("\nTesting User 2 contact isolation...")
    response = requests.get(f"{BACKEND_URL}/contacts", headers=user2_headers)
    if response.status_code == 200:
        user2_retrieved_contacts = response.json()
        user2_contact_names = [c["name"] for c in user2_retrieved_contacts]
        
        print(f"User 2 sees {len(user2_retrieved_contacts)} contacts: {user2_contact_names}")
        
        # Check if User 2 can see any of User 1's contacts
        user1_names_in_user2 = [name for name in user2_contact_names if "User1" in name]
        if user1_names_in_user2:
            print(f"❌ ISOLATION BREACH: User 2 can see User 1's contacts: {user1_names_in_user2}")
            return False
        else:
            print("✅ User 2 isolation working - cannot see User 1's contacts")
    else:
        print(f"❌ Failed to get User 2 contacts: {response.status_code}")
        return False
    
    print()
    print("🎉 MULTI-USER ISOLATION TEST PASSED!")
    print("✅ Users can only see their own data")
    print("✅ No cross-user data leakage detected")
    
    return True

if __name__ == "__main__":
    success = test_multi_user_isolation()
    exit(0 if success else 1)