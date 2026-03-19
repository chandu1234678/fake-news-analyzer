import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Use absolute path for SQLite so it works regardless of working directory
_db_dir = os.path.dirname(os.path.abspath(__file__))
_default_db = f"sqlite:///{os.path.join(_db_dir, 'fake_news.db')}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_db)

# If DATABASE_URL is a relative sqlite path, make it absolute
if DATABASE_URL.startswith("sqlite:///./"):
    rel_path = DATABASE_URL[len("sqlite:///./"):]
    DATABASE_URL = f"sqlite:///{os.path.join(_db_dir, rel_path)}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
