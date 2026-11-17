import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Use SQLite for local automated test execution
os.environ["DATABASE_URL"] = "sqlite:///./stock_screener_e2e.db"

from database import engine, Base, SessionLocal, check_and_migrate_db
from models import User, Symbol, Fundamental, PortfolioItem, Alert
from auth_utils import get_password_hash
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_master_e2e_suite():
    print("=" * 60)
    print("🚀 RUNNING MASTER END-TO-END VERIFICATION SUITE")
    print("=" * 60 + "\n")

    # 1. Schema & Migration Verification
    print("--- STEP 1: Database Setup & Migrations ---")
    Base.metadata.create_all(bind=engine)
    check_and_migrate_db()
    db = SessionLocal()

    # Clear previous e2e data
    db.query(Alert).delete()
    db.query(PortfolioItem).delete()
    db.query(Fundamental).delete()
    db.query(Symbol).delete()
    db.query(User).filter(User.username.in_(["e2e_trader", "dup_user"])).delete()
    db.commit()

    # Seed baseline symbols and fundamentals
    aapl = Symbol(symbol="AAPL", company_name="Apple Inc", sector="Technology")
    msft = Symbol(symbol="MSFT", company_name="Microsoft Corp", sector="Technology")
    jnj = Symbol(symbol="JNJ", company_name="Johnson & Johnson", sector="Healthcare")
    db.add_all([aapl, msft, jnj])
    db.commit()

    db.add(Fundamental(company_id=aapl.id, pe_ratio=28.5, eps=6.1, market_cap=2.8e12, revenue_growth=5.2))
    db.add(Fundamental(company_id=msft.id, pe_ratio=35.0, eps=9.5, market_cap=3.1e12, revenue_growth=12.0))
    db.add(Fundamental(company_id=jnj.id, pe_ratio=15.5, eps=10.2, market_cap=4.2e11, revenue_growth=2.1))
    db.commit()
    print("✅ Database cleanly initialized with AAPL, MSFT, JNJ.\n")

    # 2. Authentication: Registration
    print("--- STEP 2: Native User Registration ---")
    reg_payload = {
        "username": "e2e_trader",
        "email": "e2e_trader@hedgefund.com",
        "full_name": "Cathie Wood",
        "password": "strongPassword123"
    }
    res_reg = client.post("/auth/register", json=reg_payload)
    assert res_reg.status_code == 201, f"Register failed: {res_reg.text}"
    data_reg = res_reg.json()
    assert "access_token" in data_reg
    assert data_reg["user"]["username"] == "e2e_trader"
    token = data_reg["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ User 'e2e_trader' registered successfully with JWT.")

    # Duplicate username check
    assert client.post("/auth/register", json=reg_payload).status_code == 400
    print("✅ Duplicate username correctly rejected (400).")

    # Duplicate email check
    dup_email_payload = reg_payload.copy()
    dup_email_payload["username"] = "different_user_name"
    assert client.post("/auth/register", json=dup_email_payload).status_code == 400
    print("✅ Duplicate email correctly rejected (400).\n")

    # 3. Authentication: Login (Username & Email)
    print("--- STEP 3: User Login ---")
    # Login via username
    l1 = client.post("/auth/login", json={"username": "e2e_trader", "password": "strongPassword123"})
    assert l1.status_code == 200 and "access_token" in l1.json()
    print("✅ Login via username successful.")

    # Login via email
    l2 = client.post("/auth/login", json={"identifier": "e2e_trader@hedgefund.com", "password": "strongPassword123"})
    assert l2.status_code == 200 and "access_token" in l2.json()
    print("✅ Login via email successful.")

    # Rejection of invalid credentials
    l3 = client.post("/auth/login", json={"username": "e2e_trader", "password": "wrongpassword"})
    assert l3.status_code == 401
    print("✅ Bad password rejected with 401.\n")

    # 4. User Profile
    print("--- STEP 4: User Profile Management ---")
    prof = client.get("/auth/me", headers=headers)
    assert prof.status_code == 200
    assert prof.json()["full_name"] == "Cathie Wood"
    print("✅ GET /auth/me profile returned user metadata.")

    prof_upd = client.put("/auth/me", json={"full_name": "Cathie Duddy Wood"}, headers=headers)
    assert prof_upd.status_code == 200
    assert prof_upd.json()["user"]["full_name"] == "Cathie Duddy Wood"
    print("✅ PUT /auth/me updated full name successfully.\n")

    # 5. Natural Language Screener Query
    print("--- STEP 5: AI Screener & Fallback Parser ---")
    q_res = client.post("/query/", json={"query": "Healthcare companies"}, headers=headers)
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert "results" in q_data
    assert len(q_data["results"]) >= 1
    assert q_data["results"][0]["symbol"] == "JNJ"
    print(f"✅ Query 'Healthcare companies' returned {len(q_data['results'])} result(s): {q_data['results'][0]['company_name']}")

    # Test numerical query
    q_res2 = client.post("/query/", json={"query": "Tech stocks with PE < 30"}, headers=headers)
    assert q_res2.status_code == 200
    res2_data = q_res2.json()
    assert "results" in res2_data
    matched_symbols = [r["symbol"] for r in res2_data["results"]]
    assert "AAPL" in matched_symbols
    assert "MSFT" not in matched_symbols  # MSFT PE is 35.0, so excluded!
    print(f"✅ Filter 'Tech stocks with PE < 30' correctly matched AAPL and excluded MSFT.\n")

    # 6. Portfolio Management
    print("--- STEP 6: Portfolio Lifecycle ---")
    # Buy 10 AAPL @ 150
    b1 = client.post("/portfolio/", json={"symbol": "AAPL", "quantity": 10, "purchase_price": 150.0}, headers=headers)
    assert b1.status_code == 200

    # Average in: Buy 10 AAPL @ 170 -> 20 shares @ 160
    b2 = client.post("/portfolio/", json={"symbol": "AAPL", "quantity": 10, "purchase_price": 170.0}, headers=headers)
    assert b2.status_code == 200

    # View portfolio
    port_res = client.get("/portfolio/", headers=headers)
    assert port_res.status_code == 200
    port_items = port_res.json()
    assert len(port_items) == 1
    assert port_items[0]["quantity"] == 20
    assert port_items[0]["purchase_price"] == 160.0
    print("✅ Portfolio Add & Weighted Average calculation verified: 20 shares @ $160.00.")

    # Trim 5 shares @ 200 -> Realized P/L = (200 - 160) * 5 = +$200.00
    sell_res = client.post("/portfolio/sell", json={"symbol": "AAPL", "quantity": 5, "sell_price": 200.0}, headers=headers)
    assert sell_res.status_code == 200
    sell_data = sell_res.json()
    assert sell_data["remaining_shares"] == 15
    assert sell_data["realized_profit_loss"] == 200.0
    print(f"✅ Trimmed 5 shares @ $200.00. Realized P/L booked: ${sell_data['realized_profit_loss']:.2f} (+{sell_data['realized_pl_percent']}%)")

    # Oversell rejection
    assert client.post("/portfolio/sell", json={"symbol": "AAPL", "quantity": 50, "sell_price": 200.0}, headers=headers).status_code == 400
    print("✅ Oversell correctly blocked (400).")

    # Close remaining 15 shares
    close_res = client.post("/portfolio/sell", json={"symbol": "AAPL", "quantity": 15, "sell_price": 180.0}, headers=headers)
    assert close_res.status_code == 200
    assert close_res.json()["remaining_shares"] == 0
    assert len(client.get("/portfolio/", headers=headers).json()) == 0
    print("✅ Position closed cleanly.\n")

    # Direct delete test
    client.post("/portfolio/", json={"symbol": "MSFT", "quantity": 5, "purchase_price": 400.0}, headers=headers)
    msft_id = client.get("/portfolio/", headers=headers).json()[0]["id"]
    del_res = client.delete(f"/portfolio/{msft_id}", headers=headers)
    assert del_res.status_code == 200
    assert len(client.get("/portfolio/", headers=headers).json()) == 0
    print("✅ Direct position deletion verified.\n")

    # 7. Smart Alerts Lifecycle
    print("--- STEP 7: Smart Alerts Dynamic Evaluation ---")
    # AAPL PE < 30 (AAPL is 28.5 -> TRIGGERED)
    a1 = client.post("/alerts/", json={"symbol": "AAPL", "field": "pe_ratio", "operator": "<", "threshold": 30.0}, headers=headers)
    assert a1.status_code == 201
    a1_id = a1.json()["alert"]["id"]

    # Market-wide PE < 10 (None are < 10 -> MONITORING)
    a2 = client.post("/alerts/", json={"field": "pe_ratio", "operator": "<", "threshold": 10.0}, headers=headers)
    assert a2.status_code == 201
    a2_id = a2.json()["alert"]["id"]

    eval_alerts = client.get("/alerts/evaluated", headers=headers).json()
    a1_eval = next(a for a in eval_alerts if a["id"] == a1_id)
    a2_eval = next(a for a in eval_alerts if a["id"] == a2_id)

    assert a1_eval["status"] == "TRIGGERED", f"Expected TRIGGERED, got {a1_eval['status']}"
    assert a2_eval["status"] == "MONITORING", f"Expected MONITORING, got {a2_eval['status']}"
    print(f"✅ Symbol alert evaluated: STATUS={a1_eval['status']}, MSG='{a1_eval['message']}'")
    print(f"✅ Market-wide alert evaluated: STATUS={a2_eval['status']}, MSG='{a2_eval['message']}'")

    # Delete alert
    assert client.delete(f"/alerts/{a1_id}", headers=headers).status_code == 200
    assert client.delete(f"/alerts/{a2_id}", headers=headers).status_code == 200
    assert len(client.get("/alerts/", headers=headers).json()) == 0
    print("✅ Alerts deleted cleanly.\n")

    db.close()
    print("=" * 60)
    print("🎉 ALL MASTER END-TO-END TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_master_e2e_suite()
