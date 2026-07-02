from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from autocoin.database import Base


class StockQueryCache(Base):
    __tablename__ = "stock_query_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_market = Column(String(8), nullable=False, index=True)
    stock_id = Column(String(32), nullable=False, index=True)
    query_key = Column(String(96), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    queried_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("stock_market", "stock_id", "query_key", name="uq_stock_query_cache_key"),
    )
