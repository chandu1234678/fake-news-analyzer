from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_token, verify_google_token, verify_google_access_token

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


@router.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
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
def me(db: Session = Depends(get_db), user: User = Depends(__import__("app.auth", fromlist=["get_current_user"]).get_current_user)):
    return _user_dict(user)


def _user_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}
