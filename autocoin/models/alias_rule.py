from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from autocoin.database import Base


class AliasRule(Base):
    __tablename__ = "alias_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    priority = Column(Integer, nullable=False, default=100, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    match_counterparty = Column(String(128), nullable=False, default="")
    match_product = Column(Text, nullable=False, default="")
    match_payment_method = Column(String(64), nullable=False, default="")
    match_transaction_type = Column(String(64), nullable=False, default="")

    product_alias = Column(String(128), nullable=False, default="")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
