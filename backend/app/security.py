"""Password hashing (scrypt), JWT tokens, and a small in-memory rate limiter."""
import base64
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import AdminUser

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
        salt, dk = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        test = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk, test)
    except Exception:
        return False


def make_token(user: AdminUser) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=config.TOKEN_HOURS)
    return jwt.encode({"sub": str(user.id), "exp": exp}, config.SECRET_KEY, algorithm="HS256")


def current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> AdminUser:
    if not creds:
        raise HTTPException(401, "Not signed in")
    try:
        data = jwt.decode(creds.credentials, config.SECRET_KEY, algorithms=["HS256"])
        user = db.get(AdminUser, int(data["sub"]))
    except Exception:
        raise HTTPException(401, "Session expired, sign in again")
    if not user:
        raise HTTPException(401, "Account no longer exists")
    return user


_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limited(key: str, limit: int, window: int) -> bool:
    q, t = _hits[key], time.monotonic()
    while q and q[0] < t - window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(t)
    return False
