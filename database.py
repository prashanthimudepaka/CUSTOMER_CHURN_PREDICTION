"""Database models for scoring history and retention feedback.

Supports both SQLite (local development) and PostgreSQL (production).
Set DATABASE_URL environment variable to use PostgreSQL.
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Auto-detect database from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./churn_data.db")

# Fix PostgreSQL URL format if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite uses different connection args than PostgreSQL
try:
    if "postgresql" in DATABASE_URL:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
    else:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print(f"[Database] Using: {'PostgreSQL' if 'postgresql' in DATABASE_URL else 'SQLite'}")
except Exception as e:
    print(f"[Database] Warning: Could not initialize database: {e}")
    # Fallback to SQLite
    engine = create_engine("sqlite:///./churn_data.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()


class ScoringResult(Base):
    """Store each scoring event and results."""
    __tablename__ = "scoring_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    customer_id = Column(String, index=True)
    churn_probability = Column(Float)
    risk_band = Column(String)  # High, Medium, Low
    tenure = Column(Float, nullable=True)
    top_drivers = Column(String)  # JSON string of drivers


class RetentionFeedback(Base):
    """Track retention call outcomes."""
    __tablename__ = "retention_feedback"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    customer_id = Column(String, index=True)
    churn_probability = Column(Float)
    call_made = Column(Boolean, default=False)  # Was a retention call made?
    call_successful = Column(Boolean, nullable=True)  # True if customer stayed
    actual_churn = Column(Boolean, nullable=True)  # Did customer actually churn?
    notes = Column(String, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
