from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    portfolio = relationship("PortfolioItem", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=False)
    sector = Column(String, index=True)

    fundamentals = relationship("Fundamental", back_populates="company", uselist=False)
    historical_metrics = relationship("HistoricalMetric", back_populates="company")

class Fundamental(Base):
    __tablename__ = "fundamentals"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("symbols.id"), unique=True)
    pe_ratio = Column(Float, nullable=True)
    eps = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    revenue_growth = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    company = relationship("Symbol", back_populates="fundamentals")

class HistoricalMetric(Base):
    __tablename__ = "historical_metrics"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("symbols.id"))
    quarter = Column(String, index=True) # e.g. "2024-Q1"
    revenue = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)

    company = relationship("Symbol", back_populates="historical_metrics")

class PortfolioItem(Base):
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    company_id = Column(Integer, ForeignKey("symbols.id"))
    quantity = Column(Integer, nullable=False, default=1)
    purchase_price = Column(Float, nullable=False)

    user = relationship("User", back_populates="portfolio")
    company = relationship("Symbol")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String, nullable=True)
    field = Column(String, nullable=False) # e.g., 'pe_ratio'
    operator = Column(String, nullable=False) # e.g., '<'
    threshold = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="alerts")
