from datetime import datetime
from typing import Optional

from pydantic import BaseModel, validator


class ImportBatchResponse(BaseModel):
    id: str
    filename: str
    source: str
    imported_at: Optional[str] = None
    total_rows: int = 0
    imported_rows: int = 0
    duplicate_rows: int = 0
    error_rows: int = 0
    status: str


class ImageTransactionItem(BaseModel):
    """A single transaction recognized from an image."""
    transaction_time: str = ""
    direction: str = "expense"
    amount: float = 0.0
    category: str = ""
    counterparty: str = ""
    product: str = ""
    payment_method: str = ""
    remark: str = ""

    @validator("transaction_time")
    def validate_time(cls, v):
        if not v or not v.strip():
            raise ValueError("交易时间不能为空")
        v = v.strip().replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                datetime.strptime(v, fmt)
                return v
            except ValueError:
                continue
        raise ValueError(f"时间格式无效: {v}，请使用 YYYY-MM-DD HH:MM:SS")

    @validator("direction")
    def validate_direction(cls, v):
        if v not in ("expense", "income", "neutral"):
            raise ValueError(f"无效的收支类型: {v}")
        return v

    @validator("amount")
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("金额必须大于 0")
        return round(v, 2)


class ImageRecognizeResponse(BaseModel):
    """Response from image recognition endpoint."""
    transactions: list[ImageTransactionItem] = []
    image_count: int = 0
    filenames: list[str] = []
    daily_used: Optional[int] = None
    daily_limit: Optional[int] = None
