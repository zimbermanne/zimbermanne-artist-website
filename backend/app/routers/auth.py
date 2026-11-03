from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AdminUser
from ..security import client_ip, current_admin, hash_password, make_token, rate_limited, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    if rate_limited("login:" + client_ip(request), 10, 900):
        raise HTTPException(429, "Too many attempts, try again in a few minutes")
    user = db.scalar(select(AdminUser).where(AdminUser.email == body.email.strip().lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"access_token": make_token(user), "token_type": "bearer", "email": user.email}


@router.get("/me")
def me(user: AdminUser = Depends(current_admin)):
    return {"email": user.email}


@router.post("/change-password")
def change_password(body: PasswordIn, user: AdminUser = Depends(current_admin), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    if len(body.new_password) < 10:
        raise HTTPException(400, "Use at least 10 characters")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
