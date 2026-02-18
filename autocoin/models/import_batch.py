from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from autocoin.database import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(String(36), primary_key=True)             # UUID
    filename = Column(String(256), nullable=False)
    source = Column(String(20), nullable=False)           # 'alipay' | 'wechat'
    imported_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    total_rows = Column(Integer, default=0)
    imported_rows = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    status = Column(String(20), nullable=False, default="pending")  # pending|success|partial|failed
