from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ParsedTransaction:
    source: str
    source_order_id: str
    merchant_order_id: str
    transaction_time: datetime
    transaction_type: str
    category: str
    counterparty: str
    counterparty_account: str
    product: str
    direction: str          # 'income' | 'expense' | 'neutral'
    amount: float
    payment_method: str
    status: str
    remark: str


class BillParser(ABC):
    SOURCE_NAME: str = ""

    @abstractmethod
    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        """Parse file bytes and return a list of transactions."""
        ...

    @abstractmethod
    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        """Return True if this parser can handle the given file."""
        ...
