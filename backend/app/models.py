from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, unique=True, index=True, nullable=False)
    name       = Column(String, nullable=True)
    picture    = Column(String, nullable=True)
    hashed_pw  = Column(String, nullable=True)
    google_id  = Column(String, unique=True, nullable=True, index=True)
    is_active  = Column(Boolean, default=True)
    tier       = Column(String, default="free", nullable=False)  # free, pro, enterprise
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions  = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("UserFeedback", back_populates="user", cascade="all, delete-orphan")


class PasswordResetOTP(Base):
    __tablename__ = "password_reset_otps"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, index=True, nullable=False)
    otp        = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used       = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title      = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    user     = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session",
                            cascade="all, delete-orphan", order_by="ChatMessage.created_at")

    __table_args__ = (
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role        = Column(String, nullable=False)       # "user" | "assistant"
    content     = Column(Text, nullable=False)
    is_claim    = Column(Boolean, default=False)
    verdict     = Column(String, nullable=True)
    confidence  = Column(Float, nullable=True)
    ml_score    = Column(Float, nullable=True)
    ai_score    = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    evidence    = Column(Text, nullable=True)          # JSON string
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)

    session = relationship("ChatSession", back_populates="messages")


class UserFeedback(Base):
    """Stores user corrections — predicted vs actual verdict."""
    __tablename__ = "user_feedback"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    claim_text  = Column(Text, nullable=False)
    predicted   = Column(String, nullable=False)
    actual      = Column(String, nullable=False)
    confidence  = Column(Float, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="feedbacks")


class ClaimRecord(Base):
    """Tracks every claim verification — enables temporal analysis."""
    __tablename__ = "claim_records"

    id             = Column(Integer, primary_key=True, index=True)
    claim_hash     = Column(String(64), nullable=False)
    claim_text     = Column(Text, nullable=False)
    verdict        = Column(String, nullable=False)
    confidence     = Column(Float, nullable=True)
    ml_score       = Column(Float, nullable=True)
    ai_score       = Column(Float, nullable=True)
    evidence_score = Column(Float, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_claim_records_hash_created", "claim_hash", "created_at"),
    )


class VelocityRecord(Base):
    """Tracks claim velocity for rapid spread detection."""
    __tablename__ = "velocity_records"

    id                = Column(Integer, primary_key=True, index=True)
    claim_hash        = Column(String(64), nullable=False, index=True)
    claim_text        = Column(Text, nullable=False)
    velocity_score    = Column(Float, nullable=False)
    count_5min        = Column(Integer, nullable=False)
    count_1hr         = Column(Integer, nullable=False)
    count_24hr        = Column(Integer, nullable=False)
    is_viral          = Column(Boolean, default=False, index=True)
    is_trending       = Column(Boolean, default=False, index=True)
    cooldown_score    = Column(Float, nullable=True)
    cooldown_level    = Column(String, nullable=True)
    # Phase 2.5: Semantic clustering
    cluster_id        = Column(Integer, nullable=True, index=True)
    cluster_size      = Column(Integer, nullable=True)
    campaign_score    = Column(Float, nullable=True)
    is_coordinated    = Column(Boolean, default=False, index=True)
    created_at        = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_velocity_records_hash_created", "claim_hash", "created_at"),
        Index("ix_velocity_records_viral_created", "is_viral", "created_at"),
        Index("ix_velocity_records_coordinated", "is_coordinated", "created_at"),
    )


# ── Phase 4.3: A/B Testing Models ─────────────────────────────

class ABTest(Base):
    """A/B test configuration for model experimentation."""
    __tablename__ = "ab_tests"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status      = Column(String, default="draft", index=True)  # draft, active, paused, completed
    
    # Variant configuration (JSON string)
    # Example: {"control": {"model": "v1.0"}, "treatment": {"model": "v2.0"}}
    variants    = Column(Text, nullable=False)
    
    # Traffic split (JSON string)
    # Example: {"control": 0.5, "treatment": 0.5}
    traffic_split = Column(Text, nullable=False)
    
    # Metrics to track (JSON string)
    # Example: ["accuracy", "latency", "user_trust", "sharing_reduction"]
    metrics     = Column(Text, nullable=True)
    
    # Test duration
    start_date  = Column(DateTime, nullable=True, index=True)
    end_date    = Column(DateTime, nullable=True, index=True)
    
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignments = relationship("ABTestAssignment", back_populates="test", cascade="all, delete-orphan")
    events      = relationship("ABTestEvent", back_populates="test", cascade="all, delete-orphan")


class ABTestAssignment(Base):
    """Tracks which variant each user/session is assigned to."""
    __tablename__ = "ab_test_assignments"

    id          = Column(Integer, primary_key=True, index=True)
    test_id     = Column(Integer, ForeignKey("ab_tests.id"), nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_key = Column(String, nullable=True, index=True)  # For anonymous users
    variant     = Column(String, nullable=False, index=True)  # control, treatment, etc.
    assigned_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    test = relationship("ABTest", back_populates="assignments")
    user = relationship("User")
    
    __table_args__ = (
        Index("ix_ab_assignments_test_user", "test_id", "user_id"),
        Index("ix_ab_assignments_test_session", "test_id", "session_key"),
    )


class ABTestEvent(Base):
    """Tracks events and metrics for A/B test analysis."""
    __tablename__ = "ab_test_events"

    id          = Column(Integer, primary_key=True, index=True)
    test_id     = Column(Integer, ForeignKey("ab_tests.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("ab_test_assignments.id"), nullable=True, index=True)
    variant     = Column(String, nullable=False, index=True)
    
    # Event details
    event_type  = Column(String, nullable=False, index=True)  # prediction, feedback, share, etc.
    event_data  = Column(Text, nullable=True)  # JSON string with event-specific data
    
    # Metrics
    accuracy    = Column(Float, nullable=True)  # If feedback available
    latency_ms  = Column(Integer, nullable=True)
    confidence  = Column(Float, nullable=True)
    
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    test = relationship("ABTest", back_populates="events")
    assignment = relationship("ABTestAssignment")
    
    __table_args__ = (
        Index("ix_ab_events_test_variant", "test_id", "variant"),
        Index("ix_ab_events_test_type", "test_id", "event_type"),
    )
