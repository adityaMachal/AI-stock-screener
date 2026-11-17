import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database import get_db
from models import User
from auth_utils import get_password_hash, verify_password, create_access_token
from auth_dependency import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    clean_username = user.username.strip()
    clean_email = user.email.strip().lower()
    
    if len(clean_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
        
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="Invalid email address format")
        
    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    # Check for existing username
    if db.query(User).filter(User.username == clean_username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
        
    # Check for existing email
    if db.query(User).filter(User.email == clean_email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=clean_username,
        email=clean_email,
        full_name=user.full_name.strip() if user.full_name else None,
        hashed_password=hashed_password,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.username, "email": new_user.email})
    return {
        "message": "User registered successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name
        }
    }

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    identifier = ""
    password = ""
    
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        identifier = body.get("username") or body.get("identifier") or body.get("email") or ""
        password = body.get("password") or ""
    else:
        # Form body (x-www-form-urlencoded or multipart)
        form = await request.form()
        identifier = form.get("username") or form.get("identifier") or ""
        password = form.get("password") or ""
        
    if not identifier or not password:
        raise HTTPException(status_code=400, detail="Username/email and password are required")
        
    from sqlalchemy import or_, func
    clean_identifier = str(identifier).strip()
    user = db.query(User).filter(
        or_(
            func.lower(User.username) == clean_identifier.lower(),
            func.lower(User.email) == clean_identifier.lower()
        )
    ).first()
    
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username/email or password")
        
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
        
    access_token = create_access_token(data={"sub": user.username, "email": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name
        }
    }

@router.get("/me")
def get_profile(current_user: User = Depends(get_current_user)):
    portfolio_count = len(current_user.portfolio) if current_user.portfolio else 0
    alerts_count = len(current_user.alerts) if current_user.alerts else 0
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "portfolio_count": portfolio_count,
        "alerts_count": alerts_count
    }

@router.put("/me")
def update_profile(
    update_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name.strip()
        
    if update_data.email is not None:
        clean_email = update_data.email.strip().lower()
        if not EMAIL_REGEX.match(clean_email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        existing = db.query(User).filter(User.email == clean_email, User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use by another account")
        current_user.email = clean_email
        
    if update_data.new_password:
        if not update_data.current_password:
            raise HTTPException(status_code=400, detail="Current password required to change password")
        if not verify_password(update_data.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password incorrect")
        if len(update_data.new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
        current_user.hashed_password = get_password_hash(update_data.new_password)
        
    db.commit()
    db.refresh(current_user)
    return {
        "message": "Profile updated successfully",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name
        }
    }
