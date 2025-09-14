from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime

from db import Base, engine, SessionLocal
from models import Transaction

# CSV + categorization
import pandas as pd
from services.categorize import categorize

from pydantic import BaseModel, Field

app = FastAPI(title="Finance Dashboard API")

# --- Create DB tables on startup ---
Base.metadata.create_all(bind=engine)

# --- DB session dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok"}

# ----------------- Schemas -----------------
class TransactionCreate(BaseModel):
    date: date
    amount: float
    merchant: str = Field(default="")
    category: str = Field(default="Uncategorized")
    subcategory: str = Field(default="Other")
    notes: str | None = None

class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    notes: Optional[str] = None
    is_recurring: Optional[bool] = None

# ----------------- Create -----------------
@app.post("/transactions")
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    t = Transaction(
        user_id=1,  # dev mode, no auth yet
        account_id=None,
        date=payload.date,
        amount=payload.amount,
        merchant=payload.merchant,
        raw_description=payload.merchant,
        category=payload.category,
        subcategory=payload.subcategory,
        notes=payload.notes,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}

# ----------------- Read (list with filters) -----------------
@app.get("/transactions")
def list_transactions(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    month: Optional[str] = None,          # "YYYY-MM"
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,               # search merchant/description
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    order: str = Query("date_desc", pattern="^(date|amount)_(asc|desc)$"),
):
    qry = db.query(Transaction).filter(Transaction.user_id == 1)

    # month shortcut
    if month:
        try:
            d0 = datetime.strptime(month + "-01", "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, detail="month must be YYYY-MM")
        # month end
        if d0.month == 12:
            d1 = date(d0.year + 1, 1, 1)
        else:
            d1 = date(d0.year, d0.month + 1, 1)
        qry = qry.filter(Transaction.date >= d0, Transaction.date < d1)

    if start_date:
        qry = qry.filter(Transaction.date >= start_date)
    if end_date:
        qry = qry.filter(Transaction.date <= end_date)

    if category:
        qry = qry.filter(Transaction.category.ilike(category))

    if q:
        like = f"%{q}%"
        qry = qry.filter(
            (Transaction.merchant.ilike(like)) | (Transaction.raw_description.ilike(like))
        )

    if min_amount is not None:
        qry = qry.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        qry = qry.filter(Transaction.amount <= max_amount)

    # ordering
    if order == "date_desc":
        qry = qry.order_by(Transaction.date.desc(), Transaction.id.desc())
    elif order == "date_asc":
        qry = qry.order_by(Transaction.date.asc(), Transaction.id.asc())
    elif order == "amount_desc":
        qry = qry.order_by(Transaction.amount.desc(), Transaction.id.desc())
    elif order == "amount_asc":
        qry = qry.order_by(Transaction.amount.asc(), Transaction.id.asc())

    rows = qry.offset(offset).limit(limit).all()

    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "amount": r.amount,
            "merchant": r.merchant,
            "category": r.category,
            "subcategory": r.subcategory,
            "notes": r.notes,
        }
        for r in rows
    ]

# ----------------- Read (single) -----------------
@app.get("/transactions/{tx_id}")
def get_transaction(tx_id: int, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.user_id == 1, Transaction.id == tx_id).first()
    if not t:
        raise HTTPException(404, detail="Transaction not found")
    return {
        "id": t.id,
        "date": t.date.isoformat(),
        "amount": t.amount,
        "merchant": t.merchant,
        "category": t.category,
        "subcategory": t.subcategory,
        "notes": t.notes,
        "is_recurring": t.is_recurring,
    }

# ----------------- Update -----------------
@app.put("/transactions/{tx_id}")
def update_transaction(tx_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.user_id == 1, Transaction.id == tx_id).first()
    if not t:
        raise HTTPException(404, detail="Transaction not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(t, field, value)

    db.commit()
    db.refresh(t)
    return {
        "id": t.id,
        "date": t.date.isoformat(),
        "amount": t.amount,
        "merchant": t.merchant,
        "category": t.category,
        "subcategory": t.subcategory,
        "notes": t.notes,
        "is_recurring": t.is_recurring,
    }

# ----------------- Delete -----------------
@app.delete("/transactions/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.user_id == 1, Transaction.id == tx_id).first()
    if not t:
        raise HTTPException(404, detail="Transaction not found")
    db.delete(t)
    db.commit()
    return {"deleted": True, "id": tx_id}

# ----------------- CSV Ingest + Auto-categorize -----------------
@app.post("/ingest/csv")
async def ingest_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Expect columns: date, amount, merchant OR description
    df = pd.read_csv(file.file)
    df.columns = [c.strip().lower() for c in df.columns]
    merchant_col = "merchant" if "merchant" in df.columns else "description"

    inserted = 0
    for _, row in df.iterrows():
        try:
            d = pd.to_datetime(row["date"]).date()
        except Exception:
            continue  # skip bad rows

        amt = float(row["amount"])
        merch = str(row.get(merchant_col, ""))[:200]
        cat, sub = categorize(merch)

        t = Transaction(
            user_id=1,
            account_id=None,
            date=d,
            amount=amt,
            merchant=merch,
            raw_description=merch,
            category=cat,
            subcategory=sub,
        )
        db.add(t)
        inserted += 1

    db.commit()
    return {"inserted": inserted}
