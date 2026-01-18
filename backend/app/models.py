from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
from datetime import datetime

class Analysis(Base):
    __tablename__ = "analysis"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String)
    verdict = Column(String)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
