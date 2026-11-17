from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import datetime

from database import get_db
from auth_dependency import get_current_user
from models import User, Alert, Symbol, Fundamental

router = APIRouter(prefix="/alerts", tags=["alerts"])

VALID_FIELDS = {"pe_ratio", "eps", "market_cap", "revenue_growth"}
VALID_OPERATORS = {"<", ">", "<=", ">=", "=", "=="}

class AlertCreate(BaseModel):
    field: str
    operator: str
    threshold: float
    symbol: Optional[str] = None

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_alert(alert: AlertCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    clean_field = alert.field.strip().lower()
    clean_op = alert.operator.strip()
    clean_symbol = alert.symbol.strip().upper() if alert.symbol else None

    if clean_field not in VALID_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid field: '{clean_field}'. Allowed fields: {sorted(list(VALID_FIELDS))}"
        )
    if clean_op not in VALID_OPERATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operator: '{clean_op}'. Allowed operators: {sorted(list(VALID_OPERATORS))}"
        )

    if clean_symbol:
        comp = db.query(Symbol).filter(Symbol.symbol == clean_symbol).first()
        if not comp:
            raise HTTPException(status_code=404, detail=f"Symbol '{clean_symbol}' not found in database")

    new_alert = Alert(
        user_id=current_user.id,
        symbol=clean_symbol,
        field=clean_field,
        operator=clean_op,
        threshold=alert.threshold,
        created_at=datetime.datetime.utcnow()
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    return {
        "message": "Alert created successfully",
        "alert": {
            "id": new_alert.id,
            "symbol": new_alert.symbol or "MARKET_WIDE",
            "field": new_alert.field,
            "operator": new_alert.operator,
            "threshold": new_alert.threshold
        }
    }

@router.get("/")
def view_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    alerts = db.query(Alert).filter(Alert.user_id == current_user.id).order_by(Alert.id.desc()).all()
    return [
        {
            "id": a.id,
            "symbol": a.symbol or "MARKET_WIDE",
            "field": a.field,
            "operator": a.operator,
            "threshold": a.threshold,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in alerts
    ]

@router.get("/evaluated")
def view_evaluated_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Dynamically evaluate user alerts against latest fundamental metrics."""
    alerts = db.query(Alert).filter(Alert.user_id == current_user.id).order_by(Alert.id.desc()).all()
    evaluated = []

    def evaluate_condition(current_val, op, thresh):
        if current_val is None:
            return False
        if op == "<": return current_val < thresh
        elif op == ">": return current_val > thresh
        elif op == "<=": return current_val <= thresh
        elif op == ">=": return current_val >= thresh
        elif op in ("=", "=="): return current_val == thresh
        return False

    for a in alerts:
        target_symbol = a.symbol
        if target_symbol:
            company = db.query(Symbol).filter(Symbol.symbol == target_symbol).first()
            if not company or not company.fundamentals:
                evaluated.append({
                    "id": a.id,
                    "symbol": target_symbol,
                    "field": a.field,
                    "operator": a.operator,
                    "threshold": a.threshold,
                    "current_value": None,
                    "status": "NO_DATA",
                    "message": f"No financial fundamentals available for {target_symbol}"
                })
                continue
                
            current_val = getattr(company.fundamentals, a.field, None)
            is_triggered = evaluate_condition(current_val, a.operator, a.threshold)
            status_text = "TRIGGERED" if is_triggered else "MONITORING"
            val_display = f"{current_val:,.2f}" if current_val is not None else "N/A"
            msg = f"{target_symbol} {a.field} is {val_display} (Threshold: {a.operator} {a.threshold:,.2f})"

            evaluated.append({
                "id": a.id,
                "symbol": target_symbol,
                "field": a.field,
                "operator": a.operator,
                "threshold": a.threshold,
                "current_value": current_val,
                "status": status_text,
                "message": msg
            })
        else:
            # Market-wide alert across all companies
            all_comps = db.query(Symbol).join(Fundamental).all()
            matching_symbols = []
            for c in all_comps:
                if c.fundamentals:
                    val = getattr(c.fundamentals, a.field, None)
                    if evaluate_condition(val, a.operator, a.threshold):
                        matching_symbols.append(c.symbol)

            match_count = len(matching_symbols)
            status_text = "TRIGGERED" if match_count > 0 else "MONITORING"
            preview = ", ".join(matching_symbols[:4])
            if match_count > 4:
                preview += f", +{match_count - 4} more"
                
            msg = f"{match_count} companies meet {a.field} {a.operator} {a.threshold:,.2f}"
            if matching_symbols:
                msg += f" ({preview})"

            evaluated.append({
                "id": a.id,
                "symbol": "MARKET_WIDE",
                "field": a.field,
                "operator": a.operator,
                "threshold": a.threshold,
                "current_value": match_count,
                "status": status_text,
                "message": msg
            })

    return evaluated

@router.delete("/{alert_id}")
def delete_alert(alert_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == current_user.id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted successfully"}
