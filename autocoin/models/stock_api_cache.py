from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from autocoin.database import Base


class StockApiCache(Base):
    __tablename__ = "stock_api_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_market = Column(String(8), nullable=False, index=True)
    stock_id = Column(String(32), nullable=False, index=True)
    stock_name = Column(String(128), nullable=True)
    current_price = Column(Float, nullable=True)
    stock_currency = Column(String(8), nullable=False)
    raw_api_source = Column(String(32), nullable=True)
    raw_api_data = Column(Text, nullable=True)
    queried_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("stock_market", "stock_id", name="uq_stock_api_cache_market_code"),
    )
