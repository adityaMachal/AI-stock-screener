import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Example PostgreSQL URL: postgresql://user:password@postgresserver/db
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./stock_screener.db")

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    # If a remote/postgres database is configured, test connection
    if "postgresql" in SQLALCHEMY_DATABASE_URL:
        with engine.connect() as conn:
            pass
except Exception as e:
    print(f"Notice: Configured DATABASE_URL unavailable ({e}). Falling back to local SQLite.")
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
