from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, check_and_migrate_db, auto_seed_db
from backend.routes import auth, query, portfolio, alerts, companies
from prometheus_fastapi_instrumentator import Instrumentator

# Create database tables, apply column migrations, and seed initial dataset if empty
Base.metadata.create_all(bind=engine)
check_and_migrate_db()
auto_seed_db()

app = FastAPI(title="AI-Powered Stock Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(query.router)
app.include_router(portfolio.router)
app.include_router(alerts.router)
app.include_router(companies.router)

# Instrument the app
Instrumentator().instrument(app).expose(app)

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI-Powered Stock Screener API"}

@app.post("/seed")
def trigger_seed():
    auto_seed_db()
    return {"message": "Database auto-seeded successfully"}

