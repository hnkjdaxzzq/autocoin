from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from autocoin.database import Base


class StockData(Base):
    __tablename__ = "stockdata"

    stock_vid = Column(String(16), primary_key=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    stock_market = Column(String(8), nullable=False, index=True)
    stock_id = Column(String(32), nullable=False, index=True)
    stock_name = Column(String(128), nullable=True)
    stock_alias = Column(String(128), nullable=True, index=True)
    stock_amount = Column(Float, nullable=False)
    stock_average_price = Column(Float, nullable=True)
    stock_currency = Column(String(8), nullable=False)
    stock_remark = Column(Text, nullable=True)
    stock_transaction_date = Column(DateTime, nullable=True)
    stock_entry_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
