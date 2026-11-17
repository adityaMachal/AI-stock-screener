import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Use SQLite for standalone unit testing
os.environ["DATABASE_URL"] = "sqlite:///./stock_screener_test.db"

from database import engine, Base, SessionLocal, check_and_migrate_db
from models import User, Symbol, Fundamental, PortfolioItem, Alert
from auth_utils import get_password_hash, create_access_token
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_phase2_tests():
    print("=========================================")
    print("🚀 RUNNING PHASE 2 VERIFICATION TESTS")
    print("=========================================\n")

    Base.metadata.create_all(bind=engine)
    check_and_migrate_db()
    db = SessionLocal()

    # 1. Setup test user & test symbol
    print("1. Preparing test environment (User & Symbols)...")
    db.query(Alert).delete()
    db.query(PortfolioItem).delete()
    db.query(Fundamental).delete()
    db.query(Symbol).delete()
    db.query(User).filter(User.username == "portfolio_tester").delete()
    db.commit()

    test_user = User(
        username="portfolio_tester",
        email="trader@hedgefund.com",
        full_name="Alpha Trader",
        hashed_password=get_password_hash("traderpass123"),
        is_active=True
    )
    db.add(test_user)

    aapl = Symbol(symbol="AAPL", company_name="Apple Inc", sector="Technology")
    msft = Symbol(symbol="MSFT", company_name="Microsoft Corp", sector="Technology")
    db.add_all([aapl, msft])
    db.commit()

    # Add fundamentals for alert testing: AAPL PE = 28.5, MSFT PE = 35.0
    db.add(Fundamental(company_id=aapl.id, pe_ratio=28.5, eps=6.1, market_cap=2.8e12, revenue_growth=5.2))
    db.add(Fundamental(company_id=msft.id, pe_ratio=35.0, eps=9.5, market_cap=3.1e12, revenue_growth=12.0))
    db.commit()

    token = create_access_token(data={"sub": test_user.username, "email": test_user.email})
    headers = {"Authorization": f"Bearer {token}"}
    print("   [PASS] User and symbols initialized.\n")

    # 2. Test Portfolio Add (POST /portfolio/)
    print("2. Testing Portfolio Add (POST /portfolio/)...")
    buy_res = client.post("/portfolio/", json={"symbol": "AAPL", "quantity": 10, "purchase_price": 150.0}, headers=headers)
    assert buy_res.status_code == 200, f"Buy failed: {buy_res.text}"
    print("   [PASS] Bought 10 shares of AAPL @ $150.00.")

    # Buy more to test weighted average calculation
    buy_more_res = client.post("/portfolio/", json={"symbol": "AAPL", "quantity": 10, "purchase_price": 170.0}, headers=headers)
    assert buy_more_res.status_code == 200
    item = db.query(PortfolioItem).filter(PortfolioItem.user_id == test_user.id).first()
    assert item.quantity == 20, f"Expected 20 shares, got {item.quantity}"
    assert item.purchase_price == 160.0, f"Expected avg price $160.00, got {item.purchase_price}"
    print(f"   [PASS] Weighted average calculation verified: 20 shares @ ${item.purchase_price:.2f}.\n")

    # 3. Test Portfolio View (GET /portfolio/)
    print("3. Testing Portfolio View (GET /portfolio/)...")
    view_res = client.get("/portfolio/", headers=headers)
    assert view_res.status_code == 200
    holdings = view_res.json()
    assert len(holdings) == 1
    assert holdings[0]["symbol"] == "AAPL"
    assert holdings[0]["quantity"] == 20
    item_id = holdings[0]["id"]
    print(f"   [PASS] Portfolio view returned active holding: AAPL (Qty: {holdings[0]['quantity']}).\n")

    # 4. Test Portfolio Trim / Sell (POST /portfolio/sell)
    print("4. Testing Portfolio Trim / Sell (POST /portfolio/sell)...")
    trim_res = client.post("/portfolio/sell", json={"symbol": "AAPL", "quantity": 5, "sell_price": 180.0}, headers=headers)
    assert trim_res.status_code == 200, f"Trim failed: {trim_res.text}"
    trim_data = trim_res.json()
    assert trim_data["remaining_shares"] == 15
    assert trim_data["realized_profit_loss"] == 100.0, f"Expected $100 realized profit, got {trim_data['realized_profit_loss']}"
    print(f"   [PASS] Trimmed 5 shares @ $180.00. Realized P/L: ${trim_data['realized_profit_loss']:.2f}.\n")

    # Test Sell More Than Owned (Should fail with 400)
    oversell_res = client.post("/portfolio/sell", json={"symbol": "AAPL", "quantity": 50, "sell_price": 180.0}, headers=headers)
    assert oversell_res.status_code == 400, "Should reject selling more shares than owned"
    print("   [PASS] Oversell attempt correctly rejected (400).\n")

    # Test Closing Position Completely
    close_res = client.post("/portfolio/sell", json={"symbol": "AAPL", "quantity": 15, "sell_price": 190.0}, headers=headers)
    assert close_res.status_code == 200
    assert close_res.json()["remaining_shares"] == 0
    remaining_items = db.query(PortfolioItem).filter(PortfolioItem.user_id == test_user.id).count()
    assert remaining_items == 0, "Position should be deleted after closing"
    print("   [PASS] Full position closed and record cleared from database.\n")

    # 5. Test Position Deletion (DELETE /portfolio/{id})
    print("5. Testing Position Direct Deletion (DELETE /portfolio/{id})...")
    client.post("/portfolio/", json={"symbol": "MSFT", "quantity": 5, "purchase_price": 400.0}, headers=headers)
    msft_item = db.query(PortfolioItem).filter(PortfolioItem.user_id == test_user.id).first()
    assert msft_item is not None
    del_res = client.delete(f"/portfolio/{msft_item.id}", headers=headers)
    assert del_res.status_code == 200
    assert db.query(PortfolioItem).filter(PortfolioItem.id == msft_item.id).first() is None
    print("   [PASS] Direct position deletion succeeded.\n")

    # 6. Test Alert Creation (POST /alerts/)
    print("6. Testing Alert Creation (POST /alerts/)...")
    # Ticker specific alert: AAPL PE < 30 (Currently 28.5 -> Should be TRIGGERED)
    a1_res = client.post("/alerts/", json={"symbol": "AAPL", "field": "pe_ratio", "operator": "<", "threshold": 30.0}, headers=headers)
    assert a1_res.status_code == 201, f"Alert creation failed: {a1_res.text}"
    a1_id = a1_res.json()["alert"]["id"]

    # Market-wide alert: Any company with PE < 20 (Currently min is 28.5 -> Should be MONITORING)
    a2_res = client.post("/alerts/", json={"field": "pe_ratio", "operator": "<", "threshold": 20.0}, headers=headers)
    assert a2_res.status_code == 201
    a2_id = a2_res.json()["alert"]["id"]
    print("   [PASS] Created symbol-specific and market-wide alerts.\n")

    # 7. Test Alert Dynamic Evaluation (GET /alerts/evaluated)
    print("7. Testing Dynamic Alert Evaluation (GET /alerts/evaluated)...")
    eval_res = client.get("/alerts/evaluated", headers=headers)
    assert eval_res.status_code == 200
    eval_list = eval_res.json()
    assert len(eval_list) == 2

    # Check AAPL alert evaluation
    aapl_eval = next(a for a in eval_list if a["symbol"] == "AAPL")
    assert aapl_eval["status"] == "TRIGGERED", f"Expected TRIGGERED, got {aapl_eval['status']}"
    assert aapl_eval["current_value"] == 28.5
    print(f"   [PASS] AAPL Alert evaluated: STATUS={aapl_eval['status']}, MSG='{aapl_eval['message']}'")

    # Check market-wide alert evaluation
    market_eval = next(a for a in eval_list if a["symbol"] == "MARKET_WIDE")
    assert market_eval["status"] == "MONITORING", f"Expected MONITORING, got {market_eval['status']}"
    print(f"   [PASS] Market-wide Alert evaluated: STATUS={market_eval['status']}, MSG='{market_eval['message']}'\n")

    # 8. Test Alert Deletion (DELETE /alerts/{id})
    print("8. Testing Alert Deletion (DELETE /alerts/{id})...")
    del_alert_res = client.delete(f"/alerts/{a1_id}", headers=headers)
    assert del_alert_res.status_code == 200
    assert db.query(Alert).filter(Alert.id == a1_id).first() is None
    print("   [PASS] Alert deleted successfully.\n")

    db.close()
    print("=========================================")
    print("✅ ALL PHASE 2 TESTS PASSED SUCCESSFULLY!")
    print("=========================================")

if __name__ == "__main__":
    run_phase2_tests()
