from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import yfinance as yf
import pandas as pd

from database import get_db
from auth_dependency import get_current_user
from models import User, PortfolioItem, Symbol

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

class PortfolioItemCreate(BaseModel):
    symbol: str
    quantity: int
    purchase_price: float

class PortfolioSellRequest(BaseModel):
    symbol: str
    quantity: int
    sell_price: Optional[float] = None

@router.post("/")
def add_to_portfolio(item: PortfolioItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clean_symbol = item.symbol.strip().upper()
    if item.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")
    if item.purchase_price < 0:
        raise HTTPException(status_code=400, detail="Purchase price cannot be negative")

    company = db.query(Symbol).filter(Symbol.symbol == clean_symbol).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Symbol '{clean_symbol}' not found in database")
        
    # Check if user already owns this company
    existing_item = db.query(PortfolioItem).filter(
        PortfolioItem.user_id == current_user.id,
        PortfolioItem.company_id == company.id
    ).first()

    if existing_item:
        # Calculate new weighted average purchase price
        total_cost = (existing_item.quantity * existing_item.purchase_price) + (item.quantity * item.purchase_price)
        new_total_quantity = existing_item.quantity + item.quantity
        
        existing_item.purchase_price = round(total_cost / new_total_quantity, 2)
        existing_item.quantity = new_total_quantity
        
        db.commit()
        db.refresh(existing_item)
        return {
            "message": "Updated existing position (Weighted Average Applied)",
            "symbol": clean_symbol,
            "quantity": existing_item.quantity,
            "avg_purchase_price": existing_item.purchase_price
        }
    else:
        new_item = PortfolioItem(
            user_id=current_user.id,
            company_id=company.id,
            quantity=item.quantity,
            purchase_price=round(item.purchase_price, 2)
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return {
            "message": "Added to portfolio",
            "symbol": clean_symbol,
            "quantity": new_item.quantity,
            "purchase_price": new_item.purchase_price
        }

@router.post("/sell")
def sell_portfolio_item(sell_req: PortfolioSellRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clean_symbol = sell_req.symbol.strip().upper()
    if sell_req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Sell quantity must be greater than 0")

    company = db.query(Symbol).filter(Symbol.symbol == clean_symbol).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Symbol '{clean_symbol}' not found")

    existing_item = db.query(PortfolioItem).filter(
        PortfolioItem.user_id == current_user.id,
        PortfolioItem.company_id == company.id
    ).first()

    if not existing_item:
        raise HTTPException(status_code=404, detail=f"You do not own any shares of '{clean_symbol}'")

    if sell_req.quantity > existing_item.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sell {sell_req.quantity} shares; you only own {existing_item.quantity} shares of {clean_symbol}"
        )

    # Determine sell price
    sell_price = sell_req.sell_price
    if sell_price is None or sell_price <= 0:
        try:
            ticker = yf.Ticker(clean_symbol)
            sell_price = ticker.fast_info.get("last_price")
        except Exception:
            pass
        if sell_price is None or pd.isna(sell_price):
            sell_price = existing_item.purchase_price

    cost_basis = existing_item.purchase_price * sell_req.quantity
    proceeds = sell_price * sell_req.quantity
    realized_pl = proceeds - cost_basis
    realized_pl_pct = ((sell_price - existing_item.purchase_price) / existing_item.purchase_price) * 100 if existing_item.purchase_price > 0 else 0.0

    remaining_shares = existing_item.quantity - sell_req.quantity
    if remaining_shares == 0:
        db.delete(existing_item)
        db.commit()
        return {
            "message": f"Closed position in {clean_symbol}",
            "symbol": clean_symbol,
            "shares_sold": sell_req.quantity,
            "remaining_shares": 0,
            "sell_price": round(sell_price, 2),
            "realized_profit_loss": round(realized_pl, 2),
            "realized_pl_percent": round(realized_pl_pct, 2)
        }
    else:
        existing_item.quantity = remaining_shares
        db.commit()
        db.refresh(existing_item)
        return {
            "message": f"Trimmed position in {clean_symbol} by {sell_req.quantity} shares",
            "symbol": clean_symbol,
            "shares_sold": sell_req.quantity,
            "remaining_shares": existing_item.quantity,
            "sell_price": round(sell_price, 2),
            "realized_profit_loss": round(realized_pl, 2),
            "realized_pl_percent": round(realized_pl_pct, 2)
        }

@router.delete("/{item_id}")
def delete_portfolio_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(PortfolioItem).filter(
        PortfolioItem.id == item_id,
        PortfolioItem.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Portfolio position not found")
        
    symbol_name = item.company.symbol if item.company else f"Item #{item_id}"
    db.delete(item)
    db.commit()
    return {"message": f"Position for {symbol_name} deleted successfully"}

@router.get("/")
def view_portfolio(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = db.query(PortfolioItem).filter(PortfolioItem.user_id == current_user.id).all()
    result = []
    
    symbols = [item.company.symbol for item in items if item.company and item.company.symbol]
    prices = {}
    if symbols:
        try:
            df = yf.download(symbols, period="1d", progress=False)
            if 'Close' in df.columns:
                close_df = df['Close']
                if isinstance(close_df, pd.Series):
                    s = close_df.dropna()
                    if not s.empty:
                        prices[symbols[0]] = float(s.iloc[-1])
                elif isinstance(close_df, pd.DataFrame):
                    for sym in symbols:
                        if sym in close_df.columns:
                            col_s = close_df[sym].dropna()
                            if not col_s.empty:
                                prices[sym] = float(col_s.iloc[-1])
        except Exception as e:
            print(f"Batch price download notice: {e}")

    for item in items:
        symbol = item.company.symbol if item.company else "UNKNOWN"
        current_price = prices.get(symbol)
        
        # Fallback to fast_info or purchase_price if batch failed
        if current_price is None or pd.isna(current_price):
            try:
                ticker = yf.Ticker(symbol)
                current_price = ticker.fast_info.get("last_price")
            except Exception:
                pass
                
        if current_price is None or pd.isna(current_price):
            current_price = item.purchase_price
            
        total_val = current_price * item.quantity
        profit_loss = (current_price - item.purchase_price) * item.quantity
        pl_percent = ((current_price - item.purchase_price) / item.purchase_price) * 100 if item.purchase_price > 0 else 0.0

        result.append({
            "id": item.id,
            "symbol": symbol,
            "company_name": item.company.company_name if item.company else symbol,
            "sector": item.company.sector if item.company else "N/A",
            "quantity": item.quantity,
            "purchase_price": round(item.purchase_price, 2),
            "current_price": round(current_price, 2),
            "total_value": round(total_val, 2),
            "profit_loss": round(profit_loss, 2),
            "pl_percent": round(pl_percent, 2)
        })
    return result
