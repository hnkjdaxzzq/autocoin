from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    id: int
    source: str
    source_order_id: Optional[str] = None
    merchant_order_id: Optional[str] = None
    transaction_time: Optional[str] = None
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    counterparty: Optional[str] = None
    counterparty_account: Optional[str] = None
    product: Optional[str] = None
    direction: str
    amount: float
    payment_method: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    import_batch_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FilteredSummary(BaseModel):
    total_income: float = 0.0
    total_expense: float = 0.0
    balance: float = 0.0
    total_count: int = 0


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    summary: Optional[FilteredSummary] = None


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    remark: Optional[str] = None
    direction: Optional[str] = None


class TransactionCreate(BaseModel):
    transaction_time: str               # "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS"
    direction: str                      # "income" | "expense" | "neutral"
    amount: float
    category: Optional[str] = ""
    counterparty: Optional[str] = ""
    product: Optional[str] = ""
    payment_method: Optional[str] = ""
    remark: Optional[str] = ""
    source: Optional[str] = "manual"    # default to "manual"


class BatchDeleteRequest(BaseModel):
    ids: list[int]


class BatchUpdateRequest(BaseModel):
    ids: list[int]
    category: Optional[str] = None
    direction: Optional[str] = None
