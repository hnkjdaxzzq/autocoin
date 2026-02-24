from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from autocoin.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    source = Column(String(20), nullable=False, index=True)          # 'alipay' | 'wechat'
    source_order_id = Column(String(64), nullable=True)
    merchant_order_id = Column(String(64), nullable=True)
    transaction_time = Column(DateTime, nullable=False, index=True)
    transaction_type = Column(String(64), nullable=True)             # raw category from source
    category = Column(String(64), nullable=True, index=True)         # user-editable
    counterparty = Column(String(128), nullable=True)
    counterparty_account = Column(String(128), nullable=True)
    product = Column(Text, nullable=True)
    direction = Column(String(10), nullable=False, index=True)       # 'income'|'expense'|'neutral'
    amount = Column(Float, nullable=False)
    payment_method = Column(String(64), nullable=True)
    status = Column(String(32), nullable=True)
    remark = Column(Text, nullable=True)
    import_batch_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "source", "source_order_id", name="uq_user_source_order"),
    )
