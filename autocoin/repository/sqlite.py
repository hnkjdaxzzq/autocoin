from datetime import datetime, date
from typing import Optional

from sqlalchemy import text, func, or_, and_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from autocoin.models.transaction import Transaction
from autocoin.models.import_batch import ImportBatch
from autocoin.repository.base import DataRepository


def _tx_to_dict(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "source": tx.source,
        "source_order_id": tx.source_order_id,
        "merchant_order_id": tx.merchant_order_id,
        "transaction_time": tx.transaction_time.isoformat() if tx.transaction_time else None,
        "transaction_type": tx.transaction_type,
        "category": tx.category,
        "counterparty": tx.counterparty,
        "counterparty_account": tx.counterparty_account,
        "product": tx.product,
        "direction": tx.direction,
        "amount": tx.amount,
        "payment_method": tx.payment_method,
        "status": tx.status,
        "remark": tx.remark,
        "import_batch_id": tx.import_batch_id,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "updated_at": tx.updated_at.isoformat() if tx.updated_at else None,
    }


def _batch_to_dict(b: ImportBatch) -> dict:
    return {
        "id": b.id,
        "filename": b.filename,
        "source": b.source,
        "imported_at": b.imported_at.isoformat() if b.imported_at else None,
        "total_rows": b.total_rows,
        "imported_rows": b.imported_rows,
        "duplicate_rows": b.duplicate_rows,
        "error_rows": b.error_rows,
        "status": b.status,
    }


class SQLiteRepository(DataRepository):

    def __init__(self, db: Session):
        self._db = db

    # ---------- Transactions ----------

    def _build_filter_query(
        self,
        start_date=None,
        end_date=None,
        direction=None,
        category=None,
        source=None,
        search=None,
    ):
        q = self._db.query(Transaction).filter(Transaction.is_deleted == 0)

        if start_date:
            q = q.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            q = q.filter(Transaction.transaction_time <= end_dt)
        if direction:
            q = q.filter(Transaction.direction == direction)
        if category:
            q = q.filter(Transaction.category.ilike(f"%{category}%"))
        if source:
            q = q.filter(Transaction.source == source)
        if search:
            q = q.filter(
                or_(
                    Transaction.counterparty.ilike(f"%{search}%"),
                    Transaction.product.ilike(f"%{search}%"),
                    Transaction.remark.ilike(f"%{search}%"),
                    Transaction.transaction_type.ilike(f"%{search}%"),
                    Transaction.payment_method.ilike(f"%{search}%"),
                )
            )
        return q

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
        q = self._build_filter_query(start_date, end_date, direction, category, source, search)

        total = q.count()

        sort_col = getattr(Transaction, sort_by, Transaction.transaction_time)
        if sort_dir == "asc":
            q = q.order_by(sort_col.asc())
        else:
            q = q.order_by(sort_col.desc())

        offset = (page - 1) * page_size
        items = q.offset(offset).limit(page_size).all()
        return [_tx_to_dict(t) for t in items], total

    def get_transaction(self, id: int) -> Optional[dict]:
        tx = self._db.query(Transaction).filter(
            Transaction.id == id, Transaction.is_deleted == 0
        ).first()
        return _tx_to_dict(tx) if tx else None

    def update_transaction(self, id: int, data: dict) -> Optional[dict]:
        tx = self._db.query(Transaction).filter(
            Transaction.id == id, Transaction.is_deleted == 0
        ).first()
        if not tx:
            return None
        allowed = {"category", "remark", "direction"}
        for k, v in data.items():
            if k in allowed and v is not None:
                setattr(tx, k, v)
        tx.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(tx)
        return _tx_to_dict(tx)

    def create_transaction(self, data: dict) -> dict:
        now = datetime.utcnow()
        tx = Transaction(
            source=data.get("source", "manual"),
            source_order_id=data.get("source_order_id", f"manual_{now.strftime('%Y%m%d%H%M%S%f')}"),
            merchant_order_id=data.get("merchant_order_id", ""),
            transaction_time=datetime.fromisoformat(data["transaction_time"]) if isinstance(data.get("transaction_time"), str) else data.get("transaction_time", now),
            transaction_type=data.get("category", ""),
            category=data.get("category", ""),
            counterparty=data.get("counterparty", ""),
            counterparty_account=data.get("counterparty_account", ""),
            product=data.get("product", ""),
            direction=data["direction"],
            amount=float(data["amount"]),
            payment_method=data.get("payment_method", ""),
            status="手动录入",
            remark=data.get("remark", ""),
            import_batch_id=None,
            created_at=now,
            updated_at=now,
            is_deleted=0,
        )
        self._db.add(tx)
        self._db.commit()
        self._db.refresh(tx)
        return _tx_to_dict(tx)

    def get_filtered_summary(
        self,
        start_date=None,
        end_date=None,
        direction=None,
        category=None,
        source=None,
        search=None,
    ) -> dict:
        q = self._build_filter_query(start_date, end_date, direction, category, source, search)

        income_q = q.filter(Transaction.direction == "income")
        expense_q = q.filter(Transaction.direction == "expense")

        total_income = income_q.with_entities(func.sum(Transaction.amount)).scalar() or 0.0
        total_expense = expense_q.with_entities(func.sum(Transaction.amount)).scalar() or 0.0
        total_count = q.count()

        return {
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "balance": round(total_income - total_expense, 2),
            "total_count": total_count,
        }

    def soft_delete_transaction(self, id: int) -> bool:
        tx = self._db.query(Transaction).filter(
            Transaction.id == id, Transaction.is_deleted == 0
        ).first()
        if not tx:
            return False
        tx.is_deleted = 1
        tx.updated_at = datetime.utcnow()
        self._db.commit()
        return True

    def bulk_insert_transactions(
        self, items: list[dict], batch_id: str
    ) -> tuple[int, int]:
        if not items:
            return 0, 0

        # Count rows before to detect duplicates
        before_count = self._db.query(func.count(Transaction.id)).scalar()

        # Build insert dicts, filtering out None source_order_id for unique constraint
        rows = []
        for item in items:
            row = {
                "source": item["source"],
                "source_order_id": item.get("source_order_id"),
                "merchant_order_id": item.get("merchant_order_id"),
                "transaction_time": item["transaction_time"],
                "transaction_type": item.get("transaction_type"),
                "category": item.get("category"),
                "counterparty": item.get("counterparty"),
                "counterparty_account": item.get("counterparty_account"),
                "product": item.get("product"),
                "direction": item["direction"],
                "amount": item["amount"],
                "payment_method": item.get("payment_method"),
                "status": item.get("status"),
                "remark": item.get("remark"),
                "import_batch_id": batch_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_deleted": 0,
            }
            rows.append(row)

        # Use OR IGNORE for deduplication
        stmt = sqlite_insert(Transaction).prefix_with("OR IGNORE").values(rows)
        self._db.execute(stmt)
        self._db.commit()

        after_count = self._db.query(func.count(Transaction.id)).scalar()
        inserted = after_count - before_count
        duplicates = len(items) - inserted
        return inserted, duplicates

    # ---------- Statistics ----------

    def get_summary_stats(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> dict:
        q = self._db.query(Transaction).filter(Transaction.is_deleted == 0)
        if start_date:
            q = q.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            q = q.filter(Transaction.transaction_time <= end_dt)

        income_q = q.filter(Transaction.direction == "income")
        expense_q = q.filter(Transaction.direction == "expense")

        total_income = income_q.with_entities(func.sum(Transaction.amount)).scalar() or 0.0
        total_expense = expense_q.with_entities(func.sum(Transaction.amount)).scalar() or 0.0
        income_count = income_q.count()
        expense_count = expense_q.count()
        total_count = q.count()

        return {
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "net": round(total_income - total_expense, 2),
            "transaction_count": total_count,
            "income_count": income_count,
            "expense_count": expense_count,
        }

    def get_monthly_stats(self, year: int) -> list[dict]:
        rows = (
            self._db.query(
                func.strftime("%m", Transaction.transaction_time).label("month"),
                Transaction.direction,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .filter(
                Transaction.is_deleted == 0,
                func.strftime("%Y", Transaction.transaction_time) == str(year),
                Transaction.direction.in_(["income", "expense"]),
            )
            .group_by("month", Transaction.direction)
            .all()
        )

        month_data: dict[int, dict] = {}
        for m in range(1, 13):
            month_data[m] = {"month": m, "income": 0.0, "expense": 0.0, "count": 0}

        for row in rows:
            m = int(row.month)
            if row.direction == "income":
                month_data[m]["income"] = round(row.total, 2)
            else:
                month_data[m]["expense"] = round(row.total, 2)
            month_data[m]["count"] += row.cnt

        for m in month_data.values():
            m["net"] = round(m["income"] - m["expense"], 2)

        return list(month_data.values())

    def get_category_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "expense",
    ) -> list[dict]:
        q = (
            self._db.query(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .filter(Transaction.is_deleted == 0, Transaction.direction == direction)
        )
        if start_date:
            q = q.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            q = q.filter(Transaction.transaction_time <= end_dt)

        rows = q.group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).all()

        grand_total = sum(r.total for r in rows) or 1.0
        return [
            {
                "category": r.category or "其他",
                "amount": round(r.total, 2),
                "count": r.cnt,
                "percentage": round(r.total / grand_total * 100, 2),
            }
            for r in rows
        ]

    def get_daily_stats(self, year: int, month: int) -> list[dict]:
        month_str = f"{year}-{month:02d}"
        rows = (
            self._db.query(
                func.strftime("%Y-%m-%d", Transaction.transaction_time).label("day"),
                Transaction.direction,
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.is_deleted == 0,
                func.strftime("%Y-%m", Transaction.transaction_time) == month_str,
                Transaction.direction.in_(["income", "expense"]),
            )
            .group_by("day", Transaction.direction)
            .all()
        )

        day_data: dict[str, dict] = {}
        for row in rows:
            d = row.day
            if d not in day_data:
                day_data[d] = {"date": d, "income": 0.0, "expense": 0.0}
            if row.direction == "income":
                day_data[d]["income"] = round(row.total, 2)
            else:
                day_data[d]["expense"] = round(row.total, 2)

        return sorted(day_data.values(), key=lambda x: x["date"])

    # ---------- Import Batches ----------

    def create_import_batch(self, data: dict) -> dict:
        batch = ImportBatch(**data)
        self._db.add(batch)
        self._db.commit()
        self._db.refresh(batch)
        return _batch_to_dict(batch)

    def update_import_batch(self, batch_id: str, data: dict) -> Optional[dict]:
        batch = self._db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        if not batch:
            return None
        for k, v in data.items():
            setattr(batch, k, v)
        self._db.commit()
        self._db.refresh(batch)
        return _batch_to_dict(batch)

    def get_import_batch(self, batch_id: str) -> Optional[dict]:
        batch = self._db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
        return _batch_to_dict(batch) if batch else None

    def list_import_batches(self) -> list[dict]:
        batches = (
            self._db.query(ImportBatch)
            .order_by(ImportBatch.imported_at.desc())
            .all()
        )
        return [_batch_to_dict(b) for b in batches]
