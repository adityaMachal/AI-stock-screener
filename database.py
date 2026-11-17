import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Example PostgreSQL URL: postgresql://user:password@postgresserver/db
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock_screener.db")

engine = None
if "postgresql" in SQLALCHEMY_DATABASE_URL:
    import time
    for attempt in range(1, 6):
        try:
            temp_engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
            with temp_engine.connect() as conn:
                engine = temp_engine
                print(f"Connected to PostgreSQL database successfully on attempt {attempt}.")
                break
        except Exception as e:
            print(f"Waiting for PostgreSQL to be ready (attempt {attempt}/5): {e}")
            time.sleep(2)

if engine is None:
    if "postgresql" in SQLALCHEMY_DATABASE_URL:
        print("Notice: PostgreSQL unavailable after retries. Falling back to local SQLite.")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./stock_screener.db"
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def check_and_migrate_db():
    """Ensure newly added columns exist in SQLite/PostgreSQL without needing external alembic runs."""
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("users")]
            with engine.begin() as conn:
                if "email" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
                if "full_name" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR"))
                if "is_active" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"))
                if "created_at" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))
        
        if "alerts" in inspector.get_table_names():
            alert_cols = [c["name"] for c in inspector.get_columns("alerts")]
            with engine.begin() as conn:
                if "symbol" not in alert_cols:
                    conn.execute(text("ALTER TABLE alerts ADD COLUMN symbol VARCHAR"))
                if "created_at" not in alert_cols:
                    conn.execute(text("ALTER TABLE alerts ADD COLUMN created_at TIMESTAMP"))
    except Exception as e:
        print(f"Database migration check notice: {e}")

def auto_seed_db():
    """Seed initial symbols and demo user if the database is currently empty."""
    try:
        from models import User, Symbol, Fundamental, HistoricalMetric
        from auth_utils import get_password_hash
        db = SessionLocal()
        try:
            # Seed demo user if not exists
            if not db.query(User).filter(User.username == "testuser").first():
                demo_user = User(
                    username="testuser",
                    email="testuser@example.com",
                    full_name="Demo Trader",
                    hashed_password=get_password_hash("password123"),
                    is_active=True
                )
                db.add(demo_user)
                db.commit()
                print("Auto-seeded demo user: testuser / password123")
                
            # Curated Universe across all 11 GICS market sectors (~50 companies)
            stocks = [
                # Technology
                {"symbol": "AAPL", "name": "Apple Inc", "sector": "Technology", "pe": 28.5, "eps": 6.1, "mcap": 2.8e12, "rev_growth": 5.2},
                {"symbol": "MSFT", "name": "Microsoft Corp", "sector": "Technology", "pe": 35.2, "eps": 9.6, "mcap": 3.0e12, "rev_growth": 15.0},
                {"symbol": "GOOGL", "name": "Alphabet Inc", "sector": "Technology", "pe": 24.1, "eps": 5.8, "mcap": 2.1e12, "rev_growth": 13.5},
                {"symbol": "NVDA", "name": "NVIDIA Corp", "sector": "Technology", "pe": 45.0, "eps": 2.5, "mcap": 3.1e12, "rev_growth": 122.0},
                {"symbol": "AVGO", "name": "Broadcom Inc", "sector": "Technology", "pe": 32.4, "eps": 4.1, "mcap": 7.8e11, "rev_growth": 34.0},
                {"symbol": "ORCL", "name": "Oracle Corp", "sector": "Technology", "pe": 38.0, "eps": 3.6, "mcap": 3.7e11, "rev_growth": 7.0},
                {"symbol": "CRM", "name": "Salesforce Inc", "sector": "Technology", "pe": 41.5, "eps": 5.2, "mcap": 2.6e11, "rev_growth": 11.0},
                {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Technology", "pe": 46.2, "eps": 2.8, "mcap": 2.4e11, "rev_growth": 9.0},
                {"symbol": "CSCO", "name": "Cisco Systems Inc", "sector": "Technology", "pe": 16.5, "eps": 3.2, "mcap": 2.1e11, "rev_growth": 3.5},
                {"symbol": "INTC", "name": "Intel Corp", "sector": "Technology", "pe": 21.0, "eps": 1.4, "mcap": 1.3e11, "rev_growth": 2.0},

                # Communication Services
                {"symbol": "META", "name": "Meta Platforms Inc", "sector": "Communication Services", "pe": 26.8, "eps": 17.5, "mcap": 1.3e12, "rev_growth": 22.0},
                {"symbol": "NFLX", "name": "Netflix Inc", "sector": "Communication Services", "pe": 36.4, "eps": 16.2, "mcap": 2.8e11, "rev_growth": 16.5},
                {"symbol": "DIS", "name": "Walt Disney Co", "sector": "Communication Services", "pe": 39.5, "eps": 2.8, "mcap": 1.9e11, "rev_growth": 4.2},
                {"symbol": "TMUS", "name": "T-Mobile US Inc", "sector": "Communication Services", "pe": 23.2, "eps": 7.8, "mcap": 2.1e11, "rev_growth": 6.8},
                {"symbol": "VZ", "name": "Verizon Communications", "sector": "Communication Services", "pe": 9.8, "eps": 4.1, "mcap": 1.7e11, "rev_growth": 1.5},

                # Consumer Cyclical
                {"symbol": "AMZN", "name": "Amazon.com Inc", "sector": "Consumer Cyclical", "pe": 42.8, "eps": 3.8, "mcap": 1.9e12, "rev_growth": 12.0},
                {"symbol": "TSLA", "name": "Tesla Inc", "sector": "Consumer Cyclical", "pe": 65.4, "eps": 2.1, "mcap": 7.5e11, "rev_growth": 3.0},
                {"symbol": "HD", "name": "Home Depot Inc", "sector": "Consumer Cyclical", "pe": 23.5, "eps": 15.2, "mcap": 3.6e11, "rev_growth": 3.8},
                {"symbol": "MCD", "name": "McDonald's Corp", "sector": "Consumer Cyclical", "pe": 24.8, "eps": 11.5, "mcap": 2.1e11, "rev_growth": 4.5},
                {"symbol": "NKE", "name": "NIKE Inc", "sector": "Consumer Cyclical", "pe": 26.2, "eps": 3.1, "mcap": 1.4e11, "rev_growth": 2.5},
                {"symbol": "SBUX", "name": "Starbucks Corp", "sector": "Consumer Cyclical", "pe": 25.1, "eps": 3.4, "mcap": 1.1e11, "rev_growth": 3.1},

                # Consumer Defensive
                {"symbol": "WMT", "name": "Walmart Inc", "sector": "Consumer Defensive", "pe": 29.5, "eps": 2.5, "mcap": 5.4e11, "rev_growth": 5.8},
                {"symbol": "PG", "name": "Procter & Gamble Co", "sector": "Consumer Defensive", "pe": 25.6, "eps": 6.5, "mcap": 3.9e11, "rev_growth": 3.8},
                {"symbol": "COST", "name": "Costco Wholesale Corp", "sector": "Consumer Defensive", "pe": 52.0, "eps": 16.5, "mcap": 3.8e11, "rev_growth": 9.1},
                {"symbol": "KO", "name": "Coca-Cola Co", "sector": "Consumer Defensive", "pe": 24.2, "eps": 2.7, "mcap": 2.7e11, "rev_growth": 3.0},
                {"symbol": "PEP", "name": "PepsiCo Inc", "sector": "Consumer Defensive", "pe": 22.8, "eps": 7.5, "mcap": 2.3e11, "rev_growth": 2.8},

                # Financial Services
                {"symbol": "JPM", "name": "JPMorgan Chase & Co", "sector": "Financial Services", "pe": 11.8, "eps": 16.2, "mcap": 5.8e11, "rev_growth": 7.1},
                {"symbol": "V", "name": "Visa Inc", "sector": "Financial Services", "pe": 29.0, "eps": 9.8, "mcap": 5.6e11, "rev_growth": 10.0},
                {"symbol": "MA", "name": "Mastercard Inc", "sector": "Financial Services", "pe": 33.5, "eps": 13.5, "mcap": 4.4e11, "rev_growth": 11.2},
                {"symbol": "BAC", "name": "Bank of America Corp", "sector": "Financial Services", "pe": 13.4, "eps": 3.1, "mcap": 3.2e11, "rev_growth": 4.2},
                {"symbol": "GS", "name": "Goldman Sachs Group", "sector": "Financial Services", "pe": 15.2, "eps": 31.0, "mcap": 1.6e11, "rev_growth": 8.0},
                {"symbol": "MS", "name": "Morgan Stanley", "sector": "Financial Services", "pe": 16.8, "eps": 6.2, "mcap": 1.7e11, "rev_growth": 6.5},

                # Healthcare
                {"symbol": "LLY", "name": "Eli Lilly and Co", "sector": "Healthcare", "pe": 62.0, "eps": 12.8, "mcap": 7.6e11, "rev_growth": 26.0},
                {"symbol": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare", "pe": 22.3, "eps": 25.1, "mcap": 5.2e11, "rev_growth": 8.5},
                {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare", "pe": 15.0, "eps": 10.5, "mcap": 4.0e11, "rev_growth": 2.1},
                {"symbol": "ABBV", "name": "AbbVie Inc", "sector": "Healthcare", "pe": 40.2, "eps": 4.8, "mcap": 3.3e11, "rev_growth": 4.0},
                {"symbol": "MRK", "name": "Merck & Co Inc", "sector": "Healthcare", "pe": 17.5, "eps": 6.1, "mcap": 2.9e11, "rev_growth": 6.2},
                {"symbol": "PFE", "name": "Pfizer Inc", "sector": "Healthcare", "pe": 14.8, "eps": 1.9, "mcap": 1.6e11, "rev_growth": -2.0},

                # Energy
                {"symbol": "XOM", "name": "Exxon Mobil Corp", "sector": "Energy", "pe": 13.8, "eps": 8.5, "mcap": 4.7e11, "rev_growth": 1.2},
                {"symbol": "CVX", "name": "Chevron Corp", "sector": "Energy", "pe": 14.5, "eps": 10.2, "mcap": 2.8e11, "rev_growth": 1.8},
                {"symbol": "COP", "name": "ConocoPhillips", "sector": "Energy", "pe": 12.2, "eps": 8.9, "mcap": 1.3e11, "rev_growth": 2.5},
                {"symbol": "SLB", "name": "Schlumberger Ltd", "sector": "Energy", "pe": 15.1, "eps": 2.9, "mcap": 6.5e10, "rev_growth": 6.0},

                # Industrials
                {"symbol": "CAT", "name": "Caterpillar Inc", "sector": "Industrials", "pe": 16.8, "eps": 21.0, "mcap": 1.8e11, "rev_growth": 4.0},
                {"symbol": "GE", "name": "GE Aerospace", "sector": "Industrials", "pe": 31.0, "eps": 5.5, "mcap": 1.9e11, "rev_growth": 14.0},
                {"symbol": "UNP", "name": "Union Pacific Corp", "sector": "Industrials", "pe": 21.5, "eps": 10.8, "mcap": 1.4e11, "rev_growth": 2.0},
                {"symbol": "HON", "name": "Honeywell International", "sector": "Industrials", "pe": 22.0, "eps": 9.4, "mcap": 1.3e11, "rev_growth": 4.5},
                {"symbol": "BA", "name": "Boeing Co", "sector": "Industrials", "pe": 35.0, "eps": 4.2, "mcap": 1.1e11, "rev_growth": 3.0},

                # Utilities & Basic Materials
                {"symbol": "NEE", "name": "NextEra Energy Inc", "sector": "Utilities", "pe": 23.0, "eps": 3.3, "mcap": 1.6e11, "rev_growth": 8.0},
                {"symbol": "DUK", "name": "Duke Energy Corp", "sector": "Utilities", "pe": 18.5, "eps": 5.8, "mcap": 8.5e10, "rev_growth": 3.2},
                {"symbol": "LIN", "name": "Linde plc", "sector": "Basic Materials", "pe": 30.5, "eps": 14.5, "mcap": 2.1e11, "rev_growth": 5.5},
                {"symbol": "FCX", "name": "Freeport-McMoRan Inc", "sector": "Basic Materials", "pe": 24.8, "eps": 1.8, "mcap": 6.2e10, "rev_growth": 10.5},

                # Real Estate
                {"symbol": "PLD", "name": "Prologis Inc", "sector": "Real Estate", "pe": 38.2, "eps": 3.1, "mcap": 1.1e11, "rev_growth": 8.5},
                {"symbol": "AMT", "name": "American Tower Corp", "sector": "Real Estate", "pe": 35.0, "eps": 5.8, "mcap": 9.5e10, "rev_growth": 4.2},
            ]
            
            new_stocks_count = 0
            for s in stocks:
                sym = db.query(Symbol).filter(Symbol.symbol == s["symbol"]).first()
                if not sym:
                    sym = Symbol(symbol=s["symbol"], company_name=s["name"], sector=s["sector"])
                    db.add(sym)
                    db.commit()
                    db.refresh(sym)
                    
                    db.add(Fundamental(
                        company_id=sym.id,
                        pe_ratio=s["pe"],
                        eps=s["eps"],
                        market_cap=s["mcap"],
                        revenue_growth=s["rev_growth"]
                    ))
                    db.add(HistoricalMetric(
                        company_id=sym.id,
                        quarter="2024-Q1",
                        revenue=s["mcap"] * 0.05,
                        net_income=s["mcap"] * 0.01
                    ))
                    new_stocks_count += 1
                    
            if new_stocks_count > 0:
                db.commit()
                print(f"Auto-seeding added {new_stocks_count} new symbols. Stock catalog now contains {db.query(Symbol).count()} companies across all 11 sectors.")

        finally:
            db.close()
    except Exception as e:
        print(f"Auto-seed notice: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
