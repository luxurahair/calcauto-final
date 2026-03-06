from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime
from database import db, ADMIN_EMAIL
from models import UserRegister, UserLogin, User
from dependencies import hash_password, generate_token, get_current_user

router = APIRouter()

@router.post("/auth/register")
async def register_user(user_data: UserRegister):
    """Register a new user"""
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    
    # Create user
    user = User(
        name=user_data.name,
        email=user_data.email.lower(),
        password_hash=hash_password(user_data.password)
    )
    
    user_dict = user.dict()
    await db.users.insert_one(user_dict)
    
    # Generate token
    token = generate_token()
    await db.tokens.insert_one({
        "user_id": user.id,
        "token": token,
        "created_at": datetime.utcnow()
    })
    
    return {
        "success": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        },
        "token": token
    }

@router.post("/auth/login")
async def login_user(credentials: UserLogin):
    """Login user"""
    user = await db.users.find_one({
        "email": credentials.email.lower(),
        "password_hash": hash_password(credentials.password)
    })
    
    if not user:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    
    # Check if user is blocked
    if user.get("is_blocked", False):
        raise HTTPException(status_code=403, detail="Votre compte a été désactivé. Contactez l'administrateur.")
    
    # Update last_login
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Check if user should be admin
    is_admin = user.get("is_admin", False) or user["email"] == ADMIN_EMAIL
    
    # Generate token
    token = generate_token()
    await db.tokens.insert_one({
        "user_id": user["id"],
        "token": token,
        "created_at": datetime.utcnow()
    })
    
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "is_admin": is_admin
        },
        "token": token
    }

@router.post("/auth/logout")
async def logout_user(token: str):
    """Logout user by deleting token"""
    await db.tokens.delete_one({"token": token})
    return {"success": True}


@router.post("/auth/demo-login")
async def demo_login():
    """Auto-login as demo user with full admin access. No password required."""
    demo_email = "demo@calcauto.ca"
    demo_user = await db.users.find_one({"email": demo_email})

    if not demo_user:
        from models import User
        user = User(
            name="Demo Admin",
            email=demo_email,
            password_hash=hash_password("demo_access_2026")
        )
        user_dict = user.dict()
        user_dict["is_admin"] = True
        await db.users.insert_one(user_dict)
        demo_user = user_dict

    await db.users.update_one(
        {"email": demo_email},
        {"$set": {"is_admin": True, "last_login": datetime.utcnow()}}
    )

    token = generate_token()
    await db.tokens.insert_one({
        "user_id": demo_user["id"],
        "token": token,
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "user": {
            "id": demo_user["id"],
            "name": demo_user.get("name", "Demo Admin"),
            "email": demo_email,
            "is_admin": True
        },
        "token": token
    }

