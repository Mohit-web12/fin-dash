# models.py
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)          # e.g., "Checking"
    institution = Column(String)   # e.g., "Chase"
    type = Column(String)          # e.g., "depository"
    mask = Column(String)          # last 4 digits for display
    user = relationship("User")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    account_id = Column(Integer, index=True, nullable=True)
    date = Column(Date, index=True)
    amount = Column(Float)         # negative = expense, positive = income
    merchant = Column(String, index=True)
    raw_description = Column(String)
    category = Column(String, index=True)
    subcategory = Column(String, index=True)
    is_recurring = Column(Boolean, default=False)
    notes = Column(String, nullable=True)
