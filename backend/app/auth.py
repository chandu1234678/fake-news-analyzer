import os
import json
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from database import get_db
from app.models import User

SECRET_KEY  = os.getenv("JWT_SECRET", "change-me-in-production-use-long-random-string")
ALGORITHM   = "HS256"
ACCESS_TTL  = 60 * 24 * 7   # 7 days in minutes
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

bearer = HTTPBearer(auto_error=False)


# ── Password helpers ─────────────────────────────────────────
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT helpers ──────────────────────────────────────────────
def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TTL)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except JWTError:
        return None


# ── Dependency: current user ─────────────────────────────────
def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def get_current_user_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not creds:
        return None
    user_id = decode_token(creds.credentials)
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


# ── Google token verify ──────────────────────────────────────
def verify_google_token(id_token_str: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Google OAuth not configured")
    try:
        info = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        return info
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")


def verify_google_access_token(access_token: str) -> dict:
    """Verify a Google access token by calling the userinfo endpoint."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            import json as _json
            info = _json.loads(resp.read().decode())
        if "sub" not in info:
            raise ValueError("Missing sub in userinfo response")
        return info
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google access token: {e}")
