import sys
import os

# Set path dynamically to project root
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Use SQLite for standalone unit testing if postgres is not running
os.environ["DATABASE_URL"] = "sqlite:///./stock_screener_test.db"

from database import engine, Base, SessionLocal, check_and_migrate_db
from models import User, Symbol, Fundamental
from auth_utils import get_password_hash, verify_password, create_access_token
from llm.parser import rule_based_fallback_parser, parse_query_to_dsl
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_tests():
    print("=========================================")
    print("🚀 RUNNING PHASE 1 VERIFICATION TESTS")
    print("=========================================\n")
    
    # 1. Database schema & migration
    print("1. Testing Database & Migrations...")
    Base.metadata.create_all(bind=engine)
    check_and_migrate_db()
    db = SessionLocal()
    
    # Clean up test users if they exist
    db.query(User).filter(User.username.in_(["testinvestor", "newuser123"])).delete(synchronize_session=False)
    db.commit()
    print("   [PASS] DB initialized and migration check passed.\n")
    
    # 2. Test Registration Endpoint
    print("2. Testing User Registration (POST /auth/register)...")
    reg_payload = {
        "username": "testinvestor",
        "email": "investor@example.com",
        "full_name": "Warren Buffett Jr",
        "password": "securepassword123"
    }
    res = client.post("/auth/register", json=reg_payload)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert "access_token" in data, "access_token missing from register response"
    assert data["user"]["username"] == "testinvestor"
    assert data["user"]["email"] == "investor@example.com"
    token = data["access_token"]
    print("   [PASS] Successfully registered user with JWT token.")
    
    # Test duplicate username rejection
    dup_res = client.post("/auth/register", json=reg_payload)
    assert dup_res.status_code == 400, "Should reject duplicate username"
    print("   [PASS] Duplicate username correctly rejected (400).")
    
    # Test duplicate email rejection
    dup_email_payload = reg_payload.copy()
    dup_email_payload["username"] = "different_user"
    dup_email_res = client.post("/auth/register", json=dup_email_payload)
    assert dup_email_res.status_code == 400, "Should reject duplicate email"
    print("   [PASS] Duplicate email correctly rejected (400).\n")
    
    # 3. Test Login Endpoint (JSON & Form data)
    print("3. Testing User Login (POST /auth/login)...")
    # Login via username (JSON)
    login_user_res = client.post("/auth/login", json={"username": "testinvestor", "password": "securepassword123"})
    assert login_user_res.status_code == 200, f"Login failed: {login_user_res.text}"
    assert "access_token" in login_user_res.json()
    print("   [PASS] Login via username (JSON) successful.")
    
    # Login via email (JSON)
    login_email_res = client.post("/auth/login", json={"identifier": "investor@example.com", "password": "securepassword123"})
    assert login_email_res.status_code == 200, f"Login via email failed: {login_email_res.text}"
    print("   [PASS] Login via email (JSON) successful.")
    
    # Login via Form Data (OAuth2 standard)
    login_form_res = client.post("/auth/login", data={"username": "testinvestor", "password": "securepassword123"})
    assert login_form_res.status_code == 200, f"Form login failed: {login_form_res.text}"
    print("   [PASS] Login via Form Data successful.")
    
    # Login with wrong password
    bad_login_res = client.post("/auth/login", json={"username": "testinvestor", "password": "wrongpassword"})
    assert bad_login_res.status_code == 401, "Should reject invalid credentials with 401"
    print("   [PASS] Invalid password correctly rejected (401).\n")
    
    # 4. Test Profile Endpoints (GET /auth/me, PUT /auth/me)
    print("4. Testing Profile Endpoints (GET/PUT /auth/me)...")
    headers = {"Authorization": f"Bearer {token}"}
    profile_res = client.get("/auth/me", headers=headers)
    assert profile_res.status_code == 200, f"Get profile failed: {profile_res.text}"
    profile = profile_res.json()
    assert profile["username"] == "testinvestor"
    assert profile["email"] == "investor@example.com"
    assert profile["full_name"] == "Warren Buffett Jr"
    assert profile["is_active"] is True
    print("   [PASS] GET /auth/me returned user profile.")
    
    # Update profile
    update_res = client.put("/auth/me", json={"full_name": "Benjamin Graham"}, headers=headers)
    assert update_res.status_code == 200, f"Update profile failed: {update_res.text}"
    assert update_res.json()["user"]["full_name"] == "Benjamin Graham"
    print("   [PASS] PUT /auth/me updated full_name successfully.\n")
    
    # 5. Test Rule-Based Fallback Parser (Offline / 429 Resilience)
    print("5. Testing Fallback Query Parser...")
    q1 = "Tech stocks with PE < 30"
    res1 = rule_based_fallback_parser(q1)
    assert res1 is not None, "Fallback parser returned None for q1"
    assert any(f["field"] == "sector" and f["value"] == "Technology" for f in res1["filters"])
    assert any(f["field"] == "pe_ratio" and f["operator"] == "<" and f["value"] == 30.0 for f in res1["filters"])
    print(f"   [PASS] '{q1}' -> {res1}")
    
    q2 = "Healthcare companies"
    res2 = rule_based_fallback_parser(q2)
    assert res2 is not None
    assert any(f["field"] == "sector" and f["value"] == "Healthcare" for f in res2["filters"])
    print(f"   [PASS] '{q2}' -> {res2}")
    
    q3 = "Financials with market cap > 50B"
    res3 = rule_based_fallback_parser(q3)
    assert res3 is not None
    assert any(f["field"] == "sector" and f["value"] == "Financial Services" for f in res3["filters"])
    assert any(f["field"] == "market_cap" and f["operator"] == ">" and f["value"] == 50000000000.0 for f in res3["filters"])
    print(f"   [PASS] '{q3}' -> {res3}\n")

    # 6. Test End-to-End Query Execution through API
    print("6. Testing End-to-End API Query (POST /query/)...")
    query_payload = {"query": "Healthcare companies"}
    query_res = client.post("/query/", json=query_payload, headers=headers)
    assert query_res.status_code == 200, f"Query endpoint failed: {query_res.text}"
    query_data = query_res.json()
    assert "results" in query_data, "Response missing 'results' key"
    print(f"   [PASS] Query succeeded! Returned {len(query_data['results'])} matches from DB.")
    if query_data['results']:
        print(f"   Sample match: {query_data['results'][0]['company_name']} ({query_data['results'][0]['symbol']})")
    print()
    
    db.close()
    print("=========================================")
    print("✅ ALL PHASE 1 TESTS PASSED SUCCESSFULLY!")
    print("=========================================\n")

if __name__ == "__main__":
    run_tests()
