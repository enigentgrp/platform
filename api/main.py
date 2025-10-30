# main.py
# FastAPI scaffold with JWT auth stubs and key endpoints
import os
from datetime import datetime, timedelta, date
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt

from database.database import get_session
from database.models import (
    User, Role, Account, Stock, PriceHistory, OptionsChain, 
    GlobalEnvVar, NightlyJob, PriorityStock, ChangeLog, Permission,
    RolePermission, MarketSegment
)

# === Configuration ===
JWT_SECRET = os.getenv("JWT_SECRET", "unsafe-dev-secret")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

app = FastAPI(title="Foundation - Algo Trading API (MVP)")

# OAuth2 setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ==================
# Utility functions
# ==================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - currently using simple hash, replace with bcrypt in production"""
    import hashlib
    # Simple verification for now
    if ':' in hashed_password:
        salt, hash_value = hashed_password.split(':')
        return hashlib.sha256((plain_password + salt).encode()).hexdigest() == hash_value
    else:
        salted = f"{plain_password}_trading_salt"
        return hashlib.sha256(salted.encode()).hexdigest() == hashed_password

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def require_role(user: User, roles: List[str]):
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if user.role is None or user.role.name not in roles:
        raise HTTPException(status_code=403, detail="Forbidden")


# ==================
# Pydantic schemas
# ==================
class TokenResp(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EnvVarIn(BaseModel):
    name: str
    value: str
    value_type: Optional[str] = "str"
    description: Optional[str] = None


class OrderIn(BaseModel):
    account_id: int
    stock_symbol: Optional[str] = None
    option_id: Optional[int] = None
    order_type: str
    side: str
    quantity: int
    price: Optional[float] = None


class UserInfo(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role_name: Optional[str]

    class Config:
        from_attributes = True


# ==================
# Auth endpoints
# ==================
@app.post("/auth/login", response_model=TokenResp)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token({
        "sub": user.username,
        "role": user.role.name if user.role else "viewer",
        "uid": user.id
    })
    return {"access_token": token, "token_type": "bearer"}


# ==================
# User / account endpoints
# ==================
@app.get("/users/me", response_model=UserInfo)
async def users_me(current_user: User = Depends(get_current_user)):
    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role_name=current_user.role.name if current_user.role else None
    )


# ==================
# ENV VAR endpoints (admin)
# ==================
@app.post("/env/global")
async def set_global_env(
    var: EnvVarIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    require_role(current_user, ["admin"])
    
    existing = db.query(GlobalEnvVar).filter(GlobalEnvVar.name == var.name).first()
    if existing:
        existing.value = var.value
        existing.value_type = var.value_type or existing.value_type
        existing.description = var.description or existing.description
    else:
        g = GlobalEnvVar(
            name=var.name,
            value=var.value,
            value_type=var.value_type or "str",
            description=var.description
        )
        db.add(g)
    db.commit()
    return {"ok": True, "name": var.name, "value": var.value}


@app.get("/env/global")
async def get_global_env(db: Session = Depends(get_session)):
    vars = db.query(GlobalEnvVar).all()
    return [{"name": v.name, "value": v.value, "value_type": v.value_type, "description": v.description} for v in vars]


# ==================
# Stocks & price endpoints
# ==================
@app.get("/stocks")
def list_stocks(limit: int = 100, db: Session = Depends(get_session)):
    stocks = db.query(Stock).limit(limit).all()
    return [{"symbol": s.symbol, "name": s.name, "id": s.id, "is_active": s.is_active} for s in stocks]


@app.get("/stocks/{symbol}/price_history")
def stock_price_history(symbol: str, days: int = 60, db: Session = Depends(get_session)):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (db.query(PriceHistory)
            .filter(PriceHistory.stock_id == stock.id, PriceHistory.ts >= cutoff)
            .order_by(PriceHistory.ts.asc())
            .all())
    return [{
        "ts": r.ts.isoformat(),
        "open": float(r.open) if r.open is not None else None,
        "high": float(r.high) if r.high is not None else None,
        "low": float(r.low) if r.low is not None else None,
        "close": float(r.close) if r.close is not None else None,
        "volume": r.volume
    } for r in rows]


@app.get("/stocks/{symbol}/options")
def stock_options(
    symbol: str,
    type: Optional[str] = None,
    expiry: Optional[date] = None,
    db: Session = Depends(get_session)
):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    q = db.query(OptionsChain).filter(OptionsChain.stock_id == stock.id)
    if type:
        q = q.filter(OptionsChain.type == type.upper())
    if expiry:
        q = q.filter(OptionsChain.expiry == expiry)
    rows = q.order_by(OptionsChain.volume.desc()).limit(200).all()
    return [{
        "option_symbol": r.option_symbol,
        "strike": float(r.strike),
        "expiry": r.expiry.isoformat(),
        "type": r.type,
        "last_price": float(r.last_price) if r.last_price is not None else None,
        "volume": r.volume
    } for r in rows]


# ==================
# Orders & Positions
# ==================
@app.post("/orders")
async def place_order(
    order: OrderIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    account = db.query(Account).filter(Account.id == order.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Verify user owns the account
    if account.user_id != current_user.id:
        require_role(current_user, ["admin"])
    
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be > 0")
    
    # Create order
    from database.models import Order as OrderModel
    new_order = OrderModel(
        account_id=order.account_id,
        order_type=order.order_type,
        side=order.side,
        quantity=order.quantity,
        price=order.price,
        status="PENDING",
        created_at=datetime.utcnow()
    )
    
    # Set stock_id or option_id
    if order.stock_symbol:
        stock = db.query(Stock).filter(Stock.symbol == order.stock_symbol).first()
        if stock:
            new_order.stock_id = stock.id
    elif order.option_id:
        new_order.option_id = order.option_id
    
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    return {"ok": True, "order_id": new_order.id, "status": new_order.status}


@app.get("/positions")
async def list_positions(
    account_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    if account_id:
        acct = db.query(Account).filter(Account.id == account_id).first()
        if not acct:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Verify access
        if acct.user_id != current_user.id:
            require_role(current_user, ["admin"])
        
        return [{
            "id": p.id,
            "stock_id": p.stock_id,
            "option_id": p.option_id,
            "qty": p.quantity,
            "avg_price": float(p.avg_price),
            "side": p.side
        } for p in acct.positions]
    
    # List all user's positions
    user_accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    out = []
    for acct in user_accounts:
        for p in acct.positions:
            out.append({
                "account_id": acct.id,
                "position_id": p.id,
                "stock_id": p.stock_id,
                "option_id": p.option_id,
                "qty": p.quantity,
                "side": p.side
            })
    return out


# ==================
# Nightly job trigger (admin)
# ==================
@app.post("/jobs/nightly")
async def trigger_nightly(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    require_role(current_user, ["admin"])
    
    job = NightlyJob(
        job_date=date.today(),
        status="STARTED",
        started_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return {"ok": True, "job_id": job.id, "job_date": str(job.job_date)}


# ==================
# Priority list
# ==================
@app.get("/priority")
def get_priority(limit: int = 200, db: Session = Depends(get_session)):
    rows = (db.query(PriorityStock)
            .order_by(PriorityStock.score.desc())
            .limit(limit)
            .all())
    out = []
    for r in rows:
        out.append({
            "symbol": r.stock.symbol if r.stock else None,
            "reason": r.reason,
            "score": float(r.score) if r.score is not None else None,
            "flagged_at": r.flagged_at.isoformat()
        })
    return out


# ==================
# Change log entry
# ==================
@app.post("/changelog")
async def add_changelog(
    change_tag: str,
    details: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    require_role(current_user, ["admin"])
    
    row = ChangeLog(change_tag=change_tag, details=details)
    db.add(row)
    db.commit()
    db.refresh(row)
    
    return {"ok": True, "id": row.id}


# ==================
# Root
# ==================
@app.get("/")
def root():
    return {
        "service": "Foundation - Algo Trading API",
        "version": "mvp",
        "now": datetime.utcnow().isoformat()
    }
