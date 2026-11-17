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
                
            # Seed initial companies if empty
            if db.query(Symbol).count() == 0:
                print("Database has 0 symbols. Auto-seeding initial stock universe...")
                stocks = [
                    {"symbol": "AAPL", "name": "Apple Inc", "sector": "Technology", "pe": 28.5, "eps": 6.1, "mcap": 2.8e12, "rev_growth": 5.2},
                    {"symbol": "MSFT", "name": "Microsoft Corp", "sector": "Technology", "pe": 35.2, "eps": 9.6, "mcap": 3.0e12, "rev_growth": 15.0},
                    {"symbol": "GOOGL", "name": "Alphabet Inc", "sector": "Technology", "pe": 24.1, "eps": 5.8, "mcap": 2.1e12, "rev_growth": 13.5},
                    {"symbol": "NVDA", "name": "NVIDIA Corp", "sector": "Technology", "pe": 45.0, "eps": 2.5, "mcap": 3.1e12, "rev_growth": 122.0},
                    {"symbol": "AMZN", "name": "Amazon.com Inc", "sector": "Consumer Cyclical", "pe": 42.8, "eps": 3.8, "mcap": 1.9e12, "rev_growth": 12.0},
                    {"symbol": "TSLA", "name": "Tesla Inc", "sector": "Consumer Cyclical", "pe": 65.4, "eps": 2.1, "mcap": 7.5e11, "rev_growth": 3.0},
                    {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare", "pe": 15.0, "eps": 10.5, "mcap": 4.0e11, "rev_growth": 2.1},
                    {"symbol": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare", "pe": 22.3, "eps": 25.1, "mcap": 5.2e11, "rev_growth": 8.5},
                    {"symbol": "JPM", "name": "JPMorgan Chase & Co", "sector": "Financial Services", "pe": 11.8, "eps": 16.2, "mcap": 5.8e11, "rev_growth": 7.1},
                    {"symbol": "PG", "name": "Procter & Gamble Co", "sector": "Consumer Defensive", "pe": 25.6, "eps": 6.5, "mcap": 3.9e11, "rev_growth": 3.8},
                ]
                
                for s in stocks:
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
                db.commit()
                print("Auto-seeding completed successfully with 10 companies!")
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
