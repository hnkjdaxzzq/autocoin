from typing import Optional

from pydantic import BaseModel


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


class ImageRecognizeResponse(BaseModel):
    """Response from image recognition endpoint."""
    transactions: list[ImageTransactionItem] = []
    image_count: int = 0
    filenames: list[str] = []
    daily_used: Optional[int] = None
    daily_limit: Optional[int] = None
