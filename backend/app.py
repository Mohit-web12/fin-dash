import hashlib
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import (
    SessionLocal,
    create_access_token,
    get_current_user,
    get_db,
    seed_default_user,
    verify_password,
)
from config import settings
from db import Base, engine
from models import Account, Budget, Transaction, User
from services.categorize import categorize


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_default_user(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Finance Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def dedupe_key(user_id: int, tx_date: date, amount: float, merchant: str) -> str:
    raw = f"{user_id}|{tx_date.isoformat()}|{round(amount, 2)}|{(merchant or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def serialize_transaction(t: Transaction) -> dict:
    return {
        "id": t.id,
        "date": t.date.isoformat(),
        "amount": t.amount,
        "merchant": t.merchant,
        "category": t.category,
        "subcategory": t.subcategory,
        "notes": t.notes,
        "account_id": t.account_id,
        "is_recurring": t.is_recurring,
    }


# ----------------- Auth -----------------
class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, detail="Invalid email or password")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}


@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


# ----------------- Accounts -----------------
class AccountCreate(BaseModel):
    name: str
    institution: str = ""
    type: str = "depository"
    mask: str = ""


@app.get("/accounts")
def list_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Account).filter(Account.user_id == current_user.id).all()
    return [
        {"id": a.id, "name": a.name, "institution": a.institution, "type": a.type, "mask": a.mask}
        for a in rows
    ]


@app.post("/accounts")
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = Account(user_id=current_user.id, **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "name": a.name, "institution": a.institution, "type": a.type, "mask": a.mask}


# ----------------- Transaction Schemas -----------------
class TransactionCreate(BaseModel):
    date: date
    amount: float
    merchant: str = Field(default="")
    category: str = Field(default="Uncategorized")
    subcategory: str = Field(default="Other")
    notes: str | None = None
    account_id: int | None = None


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    amount: Optional[float] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    notes: Optional[str] = None
    is_recurring: Optional[bool] = None
    account_id: Optional[int] = None


# ----------------- Create -----------------
@app.post("/transactions")
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = Transaction(
        user_id=current_user.id,
        account_id=payload.account_id,
        date=payload.date,
        amount=payload.amount,
        merchant=payload.merchant,
        raw_description=payload.merchant,
        category=payload.category,
        subcategory=payload.subcategory,
        notes=payload.notes,
        dedupe_key=dedupe_key(current_user.id, payload.date, payload.amount, payload.merchant),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}


# ----------------- Read (list with filters) -----------------
@app.get("/transactions")
def list_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    qry = db.query(Transaction).filter(Transaction.user_id == current_user.id)

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

    return [serialize_transaction(r) for r in rows]


# ----------------- Read (single) -----------------
@app.get("/transactions/{tx_id}")
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = db.query(Transaction).filter(Transaction.user_id == current_user.id, Transaction.id == tx_id).first()
    if not t:
        raise HTTPException(404, detail="Transaction not found")
    return serialize_transaction(t)


# ----------------- Update -----------------
@app.put("/transactions/{tx_id}")
def update_transaction(
    tx_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = db.query(Transaction).filter(Transaction.user_id == current_user.id, Transaction.id == tx_id).first()
    if not t:
        raise HTTPException(404, detail="Transaction not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(t, field, value)

    t.dedupe_key = dedupe_key(current_user.id, t.date, t.amount, t.merchant)
    db.commit()
    db.refresh(t)
    return serialize_transaction(t)


# ----------------- Delete -----------------
@app.delete("/transactions/{tx_id}")
def delete_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = db.query(Transaction).filter(Transaction.user_id == current_user.id, Transaction.id == tx_id).first()
    if not t:
        raise HTTPException(404, detail="Transaction not found")
    db.delete(t)
    db.commit()
    return {"deleted": True, "id": tx_id}


# ----------------- CSV Ingest + Auto-categorize -----------------
REQUIRED_CSV_COLUMNS = {"date", "amount"}


@app.post("/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        df = pd.read_csv(file.file)
    except Exception as exc:
        raise HTTPException(400, detail=f"Could not parse CSV: {exc}")

    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED_CSV_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(400, detail=f"CSV is missing required column(s): {sorted(missing)}")

    merchant_col = "merchant" if "merchant" in df.columns else "description"
    has_category_cols = "category" in df.columns

    # existing dedupe keys for this user, loaded once to avoid a query per row
    existing_keys = {
        k for (k,) in db.query(Transaction.dedupe_key).filter(Transaction.user_id == current_user.id).all()
    }
    seen_in_batch = set()

    inserted = 0
    skipped_duplicates = 0
    errors = []

    for i, row in df.iterrows():
        row_num = i + 2  # +1 for 0-index, +1 for header row

        try:
            d = pd.to_datetime(row["date"]).date()
        except Exception:
            errors.append({"row": row_num, "reason": f"invalid date: {row.get('date')!r}"})
            continue

        try:
            amt = float(row["amount"])
        except (TypeError, ValueError):
            errors.append({"row": row_num, "reason": f"invalid amount: {row.get('amount')!r}"})
            continue

        merch = str(row.get(merchant_col, "") or "")[:200]

        if has_category_cols and pd.notna(row.get("category")) and str(row.get("category")).strip():
            cat = str(row["category"]).strip()
            sub = str(row.get("subcategory", "Other") or "Other").strip()
        else:
            cat, sub = categorize(merch)

        key = dedupe_key(current_user.id, d, amt, merch)
        if key in existing_keys or key in seen_in_batch:
            skipped_duplicates += 1
            continue
        seen_in_batch.add(key)

        t = Transaction(
            user_id=current_user.id,
            account_id=None,
            date=d,
            amount=amt,
            merchant=merch,
            raw_description=merch,
            category=cat,
            subcategory=sub,
            dedupe_key=key,
        )
        db.add(t)
        inserted += 1

    db.commit()
    return {
        "inserted": inserted,
        "skipped_duplicates": skipped_duplicates,
        "skipped_errors": len(errors),
        "errors": errors,
    }


# ----------------- Budgets -----------------
class BudgetUpsert(BaseModel):
    monthly_limit: float


@app.get("/budgets")
def list_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    return [{"id": b.id, "category": b.category, "monthly_limit": b.monthly_limit} for b in rows]


@app.put("/budgets/{category}")
def upsert_budget(
    category: str,
    payload: BudgetUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    b = (
        db.query(Budget)
        .filter(Budget.user_id == current_user.id, Budget.category.ilike(category))
        .first()
    )
    if b:
        b.monthly_limit = payload.monthly_limit
    else:
        b = Budget(user_id=current_user.id, category=category, monthly_limit=payload.monthly_limit)
        db.add(b)
    db.commit()
    db.refresh(b)
    return {"id": b.id, "category": b.category, "monthly_limit": b.monthly_limit}


@app.delete("/budgets/{category}")
def delete_budget(
    category: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    b = (
        db.query(Budget)
        .filter(Budget.user_id == current_user.id, Budget.category.ilike(category))
        .first()
    )
    if not b:
        raise HTTPException(404, detail="Budget not found")
    db.delete(b)
    db.commit()
    return {"deleted": True, "category": category}


# ----------------- Summary / Dashboard -----------------
@app.get("/summary")
def summary(
    month: Optional[str] = None,  # "YYYY-MM", defaults to the most recent month with data
    trailing_months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    all_tx = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()

    if month:
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise HTTPException(400, detail="month must be YYYY-MM")
        target_month = month
    elif all_tx:
        target_month = max(t.date.isoformat()[:7] for t in all_tx)
    else:
        target_month = datetime.now(timezone.utc).strftime("%Y-%m")

    budgets = {
        b.category: b.monthly_limit
        for b in db.query(Budget).filter(Budget.user_id == current_user.id).all()
    }

    month_tx = [t for t in all_tx if t.date.isoformat()[:7] == target_month]
    total_spend = round(-sum(t.amount for t in month_tx if t.amount < 0), 2)
    total_income = round(sum(t.amount for t in month_tx if t.amount > 0), 2)

    by_category: dict[str, float] = {}
    for t in month_tx:
        if t.amount < 0:
            by_category[t.category] = by_category.get(t.category, 0) + (-t.amount)

    categories = sorted(set(by_category) | set(budgets))
    by_category_out = [
        {
            "category": c,
            "spend": round(by_category.get(c, 0.0), 2),
            "budget": budgets.get(c),
            "remaining": round(budgets[c] - by_category.get(c, 0.0), 2) if c in budgets else None,
        }
        for c in categories
    ]
    by_category_out.sort(key=lambda x: x["spend"], reverse=True)

    # trailing monthly totals for a trend chart
    monthly_totals: dict[str, dict[str, float]] = {}
    for t in all_tx:
        ym = t.date.isoformat()[:7]
        bucket = monthly_totals.setdefault(ym, {"spend": 0.0, "income": 0.0})
        if t.amount < 0:
            bucket["spend"] += -t.amount
        else:
            bucket["income"] += t.amount

    months_sorted = sorted(monthly_totals)[-trailing_months:]
    monthly_totals_out = [
        {
            "month": ym,
            "spend": round(monthly_totals[ym]["spend"], 2),
            "income": round(monthly_totals[ym]["income"], 2),
        }
        for ym in months_sorted
    ]

    return {
        "month": target_month,
        "total_spend": total_spend,
        "total_income": total_income,
        "net": round(total_income - total_spend, 2),
        "by_category": by_category_out,
        "monthly_totals": monthly_totals_out,
    }
