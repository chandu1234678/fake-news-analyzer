from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    email        = Column(String, unique=True, index=True, nullable=False)
    name         = Column(String, nullable=True)
    picture      = Column(String, nullable=True)
    hashed_pw    = Column(String, nullable=True)
    google_id    = Column(String, unique=True, nullable=True)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    sessions     = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, index=True, nullable=False)
    otp        = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    title        = Column(String, default="New Chat")
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user         = relationship("User", back_populates="sessions")
    messages     = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id           = Column(Integer, primary_key=True, index=True)
    session_id   = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role         = Column(String, nullable=False)          # "user" | "assistant"
    content      = Column(Text, nullable=False)
    is_claim     = Column(Boolean, default=False)
    verdict      = Column(String, nullable=True)
    confidence   = Column(Float, nullable=True)
    ml_score     = Column(Float, nullable=True)
    ai_score     = Column(Float, nullable=True)
    explanation  = Column(Text, nullable=True)
    evidence     = Column(Text, nullable=True)             # JSON string
    created_at   = Column(DateTime, default=datetime.utcnow)

    session      = relationship("ChatSession", back_populates="messages")
