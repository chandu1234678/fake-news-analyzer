import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

_db_dir = os.path.dirname(os.path.abspath(__file__))
_default_db = f"sqlite:///{os.path.join(_db_dir, 'fake_news.db')}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_db)

# Fix relative sqlite paths
if DATABASE_URL.startswith("sqlite:///./"):
    rel_path = DATABASE_URL[len("sqlite:///./"):]
    DATABASE_URL = f"sqlite:///{os.path.join(_db_dir, rel_path)}"

# Render gives postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

is_sqlite = DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    # PostgreSQL production settings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,       # reconnect if connection dropped
        pool_size=5,              # max persistent connections
        max_overflow=10,          # extra connections under load
        pool_timeout=30,          # wait up to 30s for a connection
        pool_recycle=1800,        # recycle connections every 30 min
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
