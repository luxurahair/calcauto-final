#!/usr/bin/env python3
"""
Detailed investigation of contact data isolation issue
"""

import requests
import json

BACKEND_URL = "https://deal-detail-modal.preview.emergentagent.com/api"

def investigate_contacts():
    # Login first
    login_data = {"email": "test@test.com", "password": "test123"}
    response = requests.post(f"{BACKEND_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} - {response.text}")
        return
        
    data = response.json()
    token = data["token"]
    user_id = data["user"]["id"]
    
    print(f"Logged in as user: {user_id}")
    
    # Get contacts with token
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BACKEND_URL}/contacts", headers=headers)
    
    if response.status_code == 200:
        contacts = response.json()
        print(f"\nFound {len(contacts)} contacts:")
        
        for i, contact in enumerate(contacts):
            print(f"Contact {i+1}:")
            print(f"  ID: {contact.get('id')}")
            print(f"  Name: {contact.get('name')}")
            print(f"  Owner ID: {contact.get('owner_id', 'NOT SET')}")
            print(f"  Current User: {user_id}")
            print(f"  Matches: {contact.get('owner_id') == user_id}")
            print()
            
        # Check if any contacts don't belong to current user
        foreign_contacts = [c for c in contacts if c.get('owner_id') != user_id]
        if foreign_contacts:
            print(f"❌ ISSUE: Found {len(foreign_contacts)} contacts belonging to other users!")
            for contact in foreign_contacts:
                print(f"  - {contact.get('name')} (owner: {contact.get('owner_id')})")
        else:
            print("✅ All contacts belong to current user")
    else:
        print(f"Failed to get contacts: {response.status_code} - {response.text}")

if __name__ == "__main__":
    investigate_contacts()