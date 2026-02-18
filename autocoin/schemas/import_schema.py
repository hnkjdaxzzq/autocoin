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
