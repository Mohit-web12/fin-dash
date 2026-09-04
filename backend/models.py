# models.py
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

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
    dedupe_key = Column(String, index=True, nullable=True)  # hash of date+amount+merchant, for CSV re-ingest dedup


class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    category = Column(String, index=True)
    monthly_limit = Column(Float)


class InvestmentTrade(Base):
    """A trade the user recorded in SpendGauge.

    SpendGauge is not a broker and does not execute anything — this is the user's own
    note of what they believe they traded. When the trade lifecycle engine is connected
    it owns the authoritative record and reconciles these against the broker's version;
    when it isn't (the public demo), these rows are what the Investments page reads so
    the feature still works standalone.
    """

    __tablename__ = "investment_trades"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    symbol = Column(String, index=True)
    side = Column(String)              # BUY | SELL
    quantity = Column(Float)
    price = Column(Float)              # what they paid/received per share
    traded_on = Column(Date, index=True)
