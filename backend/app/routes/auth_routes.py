from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta

from database import get_db
from app.models import User, PasswordResetOTP
from app.auth import hash_password, verify_password, create_token, verify_google_token, verify_google_access_token, get_current_user
from app.email_utils import generate_otp, send_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleRequest(BaseModel):
    id_token: str = ""
    access_token: str = ""

class AuthResponse(BaseModel):
    token: str
    user: dict

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists. Try signing in instead.")
    user = User(
        email=req.email,
        name=req.name or req.email.split("@")[0],
        hashed_pw=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "user": _user_dict(user)}


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.hashed_pw or not verify_password(req.password, user.hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_token(user.id), "user": _user_dict(user)}


@router.post("/google", response_model=AuthResponse)
def google_auth(req: GoogleRequest, db: Session = Depends(get_db)):
    # Support both id_token (web) and access_token (Chrome extension)
    if req.access_token:
        info = verify_google_access_token(req.access_token)
    elif req.id_token:
        info = verify_google_token(req.id_token)
    else:
        raise HTTPException(status_code=400, detail="Provide id_token or access_token")

    google_id = info["sub"]
    email     = info.get("email", "")
    name      = info.get("name", "")
    picture   = info.get("picture", "")

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        # Check if email already exists (link accounts)
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
            user.picture   = picture
        else:
            user = User(email=email, name=name, picture=picture, google_id=google_id)
            db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user.id), "user": _user_dict(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_dict(user)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send OTP to email. Works for both email/password AND Google-only users."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        # Don't reveal if email exists
        return {"message": "If that email exists, a code was sent."}

    # Rate limit: max 3 OTP requests per 10 minutes
    window_start = datetime.utcnow() - timedelta(minutes=10)
    recent_count = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == req.email,
        PasswordResetOTP.created_at >= window_start,
    ).count()
    if recent_count >= 3:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a few minutes before trying again.")

    # Invalidate old unused OTPs for this email
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == req.email,
        PasswordResetOTP.used == False
    ).update({"used": True})

    # Cleanup expired OTPs older than 1 hour
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.expires_at < datetime.utcnow() - timedelta(hours=1)
    ).delete()

    db.commit()

    otp = generate_otp()
    record = PasswordResetOTP(
        email=req.email,
        otp=otp,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(record)
    db.commit()

    try:
        send_otp_email(req.email, otp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email send failed: {e}")

    return {"message": "If that email exists, a code was sent."}


@router.post("/reset-password")
def reset_password(req: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Verify OTP and set new password. Works for Google users too (sets a password)."""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    record = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == req.email,
        PasswordResetOTP.otp == req.otp,
        PasswordResetOTP.used == False,
        PasswordResetOTP.expires_at > datetime.utcnow(),
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Set password — works for both email users (reset) and Google users (first-time set)
    user.hashed_pw = hash_password(req.new_password)
    record.used = True
    db.commit()

    return {"message": "Password updated successfully"}


def _user_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}
