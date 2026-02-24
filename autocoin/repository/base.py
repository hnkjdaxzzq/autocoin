from abc import ABC, abstractmethod
from typing import Any, Optional


class DataRepository(ABC):
    """
    Abstract storage interface for all data operations.
    Implementations must be constructed with a user_id to scope all queries.
    """

    # ---------- Transactions ----------

    @abstractmethod
    def list_transactions(
        self,
        page: int = 1,
        page_size: int = 50,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "transaction_time",
        sort_dir: str = "desc",
    ) -> tuple[list[dict], int]:
        """Returns (items, total_count)."""
        ...

    @abstractmethod
    def get_transaction(self, id: int) -> Optional[dict]:
        ...

    @abstractmethod
    def update_transaction(self, id: int, data: dict) -> Optional[dict]:
        ...

    @abstractmethod
    def create_transaction(self, data: dict) -> dict:
        """Create a single transaction manually."""
        ...

    @abstractmethod
    def get_filtered_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        """Returns aggregated income/expense/balance for filtered transactions."""
        ...

    @abstractmethod
    def soft_delete_transaction(self, id: int) -> bool:
        ...

    @abstractmethod
    def bulk_insert_transactions(
        self, items: list[dict], batch_id: str
    ) -> tuple[int, int]:
        """Returns (inserted_count, duplicate_count)."""
        ...

    # ---------- Statistics ----------

    @abstractmethod
    def get_summary_stats(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> dict:
        ...

    @abstractmethod
    def get_monthly_stats(self, year: int) -> list[dict]:
        ...

    @abstractmethod
    def get_category_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "expense",
    ) -> list[dict]:
        ...

    @abstractmethod
    def get_daily_stats(self, year: int, month: int) -> list[dict]:
        ...

    # ---------- Import Batches ----------

    @abstractmethod
    def create_import_batch(self, data: dict) -> dict:
        ...

    @abstractmethod
    def update_import_batch(self, batch_id: str, data: dict) -> Optional[dict]:
        ...

    @abstractmethod
    def get_import_batch(self, batch_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def list_import_batches(self) -> list[dict]:
        ...
