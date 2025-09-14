# backend/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

Base = declarative_base()

# Absolute path to finance.db (lives alongside this file)
DB_PATH = Path(__file__).parent / "finance.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
