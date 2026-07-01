from datetime import datetime
import json
import re
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from autocoin.models.alias_rule import AliasRule
from autocoin.models.classification_rule import ClassificationRule
from autocoin.models.transaction import Transaction
from autocoin.models.import_batch import ImportBatch
from autocoin.models.user_preference import UserPreference
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
        "product_alias": tx.product_alias,
        "direction": tx.direction,
        "amount": tx.amount,
        "payment_method": tx.payment_method,
        "status": tx.status,
        "remark": tx.remark,
        "import_batch_id": tx.import_batch_id,
        "is_deleted": tx.is_deleted,
        "finishrefundcheck": tx.finishrefundcheck,
        "is_ai_classified": tx.is_ai_classified,
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


def _rule_to_dict(rule: ClassificationRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "match_counterparty": rule.match_counterparty,
        "match_product": rule.match_product,
        "match_payment_method": rule.match_payment_method,
        "match_transaction_type": rule.match_transaction_type,
        "category": rule.category,
        "remark": rule.remark,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _alias_rule_to_dict(rule: AliasRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "priority": rule.priority,
        "is_active": rule.is_active,
        "match_counterparty": rule.match_counterparty,
        "match_product": rule.match_product,
        "match_payment_method": rule.match_payment_method,
        "match_transaction_type": rule.match_transaction_type,
        "product_alias": rule.product_alias,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _normalize_sources(source) -> list[str]:
    if not source:
        return []
    if isinstance(source, str):
        return [s.strip() for s in source.split(",") if s.strip()]
    return [str(s).strip() for s in source if str(s).strip()]


def _apply_source_filter(q, source):
    sources = _normalize_sources(source)
    if "__none__" in sources:
        return q.filter(Transaction.source == "__none__")
    if len(sources) == 1:
        return q.filter(Transaction.source == sources[0])
    if len(sources) > 1:
        return q.filter(Transaction.source.in_(sources))
    return q


class SQLiteRepository(DataRepository):

    def __init__(self, db: Session, user_id: int):
        self._db = db
        self._user_id = user_id

    def _list_active_rules(self) -> list[ClassificationRule]:
        return (
            self._db.query(ClassificationRule)
            .filter(
                ClassificationRule.user_id == self._user_id,
                ClassificationRule.is_active == True,
            )
            .order_by(ClassificationRule.priority.asc(), ClassificationRule.id.asc())
            .all()
        )

    def _list_active_alias_rules(self) -> list[AliasRule]:
        return (
            self._db.query(AliasRule)
            .filter(
                AliasRule.user_id == self._user_id,
                AliasRule.is_active == True,
            )
            .order_by(AliasRule.priority.asc(), AliasRule.id.asc())
            .all()
        )

    def _matches_rule(self, item: dict, rule: ClassificationRule) -> bool:
        def matches(value: str, pattern: str) -> bool:
            if not pattern:
                return True
            try:
                return re.search(pattern, value or "", re.IGNORECASE) is not None
            except re.error:
                return False
        return all([
            matches(item.get("counterparty", ""), rule.match_counterparty),
            matches(item.get("product", ""), rule.match_product),
            matches(item.get("payment_method", ""), rule.match_payment_method),
            matches(item.get("transaction_type", ""), rule.match_transaction_type),
        ])

    def _matches_alias_rule(self, item: dict, rule: AliasRule) -> bool:
        return self._matches_rule(item, rule)

    def _apply_classification_rules(self, item: dict) -> dict:
        normalized = dict(item)
        for rule in self._list_active_rules():
            if not self._matches_rule(normalized, rule):
                continue
            # 保存原始分类
            orig_category = normalized.get("category")
            existing_remark = (normalized.get("remark") or "").strip()
            # 无条件应用规则分类（如果规则提供了分类）
            if rule.category:
                normalized["category"] = rule.category
            # 构建备注
            remark_parts = []
            if rule.remark:
                remark_parts.append(rule.remark)
            else:
                if existing_remark:
                    remark_parts.append(existing_remark)
            # 如果分类被覆盖且原分类非空，添加追溯信息
            if (
                rule.category
                and orig_category
                and orig_category != rule.category
                and "原数据分类为：" not in existing_remark
            ):
                remark_parts.append(f"原数据分类为：{orig_category}")
            if remark_parts:
                normalized["remark"] = "；".join(remark_parts)
            break
        return normalized

    def _apply_alias_rules(self, item: dict) -> dict:
        normalized = dict(item)
        for rule in self._list_active_alias_rules():
            if not self._matches_alias_rule(normalized, rule):
                continue
            if rule.product_alias:
                normalized["product_alias"] = rule.product_alias
            break
        return normalized

    # ---------- Transactions ----------

    def _build_filter_query(
        self,
        start_date=None,
        end_date=None,
        direction=None,
        category=None,
        payment_method=None,
        source=None,
        search=None,
        include_deleted: bool = False,
    ):
        q = self._db.query(Transaction).filter(Transaction.user_id == self._user_id)
        if not include_deleted:
            q = q.filter(Transaction.is_deleted == 0)

        if start_date:
            q = q.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            q = q.filter(Transaction.transaction_time <= end_dt)
        if direction:
            q = q.filter(Transaction.direction == direction)
        if category:
            q = q.filter(Transaction.category.ilike(f"%{category}%"))
        if payment_method:
            q = q.filter(Transaction.payment_method.ilike(f"%{payment_method}%"))
        q = _apply_source_filter(q, source)
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
        payment_method: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "transaction_time",
        sort_dir: str = "desc",
        include_deleted: bool = False,
    ) -> tuple[list[dict], int]:
        q = self._build_filter_query(
            start_date,
            end_date,
            direction,
            category,
            payment_method,
            source,
            search,
            include_deleted=include_deleted,
        )

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
            Transaction.id == id,
            Transaction.user_id == self._user_id,
            Transaction.is_deleted == 0,
        ).first()
        return _tx_to_dict(tx) if tx else None

    def update_transaction(self, id: int, data: dict) -> Optional[dict]:
        tx = self._db.query(Transaction).filter(
            Transaction.id == id,
            Transaction.user_id == self._user_id,
            Transaction.is_deleted == 0,
        ).first()
        if not tx:
            return None
        allowed = {"category", "remark", "direction", "is_ai_classified"}
        for k, v in data.items():
            if k in allowed and v is not None:
                setattr(tx, k, v)
        tx.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(tx)
        return _tx_to_dict(tx)

    def create_transaction(self, data: dict) -> dict:
        data = self._apply_classification_rules(data)
        data = self._apply_alias_rules(data)
        now = datetime.utcnow()
        tx = Transaction(
            user_id=self._user_id,
            source=data.get("source", "manual"),
            source_order_id=data.get("source_order_id") or f"manual_{now.strftime('%Y%m%d%H%M%S%f')}",
            merchant_order_id=data.get("merchant_order_id", ""),
            transaction_time=datetime.fromisoformat(data["transaction_time"]) if isinstance(data.get("transaction_time"), str) else data.get("transaction_time", now),
            transaction_type=data.get("category", ""),
            category=data.get("category", ""),
            counterparty=data.get("counterparty", ""),
            counterparty_account=data.get("counterparty_account", ""),
            product=data.get("product", ""),
            product_alias=data.get("product_alias", ""),
            direction=data["direction"],
            amount=float(data["amount"]),
            payment_method=data.get("payment_method", ""),
            status=data.get("status", "手动录入"),
            remark=data.get("remark", ""),
            import_batch_id=data.get("import_batch_id"),
            created_at=now,
            updated_at=now,
            is_deleted=0,
            finishrefundcheck=0,
            is_ai_classified=0,
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
        payment_method=None,
        source=None,
        search=None,
        include_deleted: bool = False,
    ) -> dict:
        q = self._build_filter_query(
            start_date,
            end_date,
            direction,
            category,
            payment_method,
            source,
            search,
            include_deleted=include_deleted,
        )

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
            Transaction.id == id,
            Transaction.user_id == self._user_id,
            Transaction.is_deleted == 0,
        ).first()
        if not tx:
            return False
        tx.is_deleted = 1
        tx.updated_at = datetime.utcnow()
        self._db.commit()
        return True

    def hard_delete_transaction(self, id: int) -> bool:
        tx = self._db.query(Transaction).filter(
            Transaction.id == id,
            Transaction.user_id == self._user_id,
        ).first()
        if not tx:
            return False
        self._db.delete(tx)
        self._db.commit()
        return True

    def list_categories(self, source=None) -> list[str]:
        """Return distinct non-empty categories for this user."""
        q = (
            self._db.query(Transaction.category)
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.is_deleted == 0,
                Transaction.category != None,
                Transaction.category != "",
            )
        )
        q = _apply_source_filter(q, source)
        rows = q.distinct().order_by(Transaction.category).all()
        return [r[0] for r in rows]

    def list_payment_methods(self) -> list[str]:
        """Return distinct non-empty payment methods for this user."""
        rows = (
            self._db.query(Transaction.payment_method)
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.is_deleted == 0,
                Transaction.payment_method != None,
                Transaction.payment_method != "",
            )
            .distinct()
            .order_by(Transaction.payment_method)
            .all()
        )
        return [r[0] for r in rows]

    def bulk_insert_transactions(
        self, items: list[dict], batch_id: str
    ) -> tuple[int, int]:
        if not items:
            return 0, 0

        before_count = self._db.query(func.count(Transaction.id)).filter(
            Transaction.user_id == self._user_id,
        ).scalar()

        rows = []
        for item in items:
            item = self._apply_classification_rules(item)
            item = self._apply_alias_rules(item)
            transaction_time = item["transaction_time"]
            if isinstance(transaction_time, str):
                transaction_time = datetime.fromisoformat(transaction_time.replace("T", " "))
            row = {
                "user_id": self._user_id,
                "source": item["source"],
                "source_order_id": item.get("source_order_id"),
                "merchant_order_id": item.get("merchant_order_id"),
                "transaction_time": transaction_time,
                "transaction_type": item.get("transaction_type"),
                "category": item.get("category"),
                "counterparty": item.get("counterparty"),
                "counterparty_account": item.get("counterparty_account"),
                "product": item.get("product"),
                "product_alias": item.get("product_alias"),
                "direction": item["direction"],
                "amount": item["amount"],
                "payment_method": item.get("payment_method"),
                "status": item.get("status"),
                "remark": item.get("remark"),
                "import_batch_id": batch_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "is_deleted": 0,
                "finishrefundcheck": 0,
            }
            rows.append(row)

        stmt = sqlite_insert(Transaction).prefix_with("OR IGNORE").values(rows)
        self._db.execute(stmt)
        self._db.commit()

        after_count = self._db.query(func.count(Transaction.id)).filter(
            Transaction.user_id == self._user_id,
        ).scalar()
        inserted = after_count - before_count
        duplicates = len(items) - inserted
        return inserted, duplicates

    def reclassify_all_transactions(self) -> dict:
        """Re-apply classification rules to all non-deleted transactions, returning changed records."""
        txs = (
            self._db.query(Transaction)
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.is_deleted == 0,
            )
            .all()
        )
        changes = []
        for tx in txs:
            original = _tx_to_dict(tx)
            applied = self._apply_classification_rules(original.copy())
            cat_changed = original.get("category") != applied.get("category")
            rem_changed = original.get("remark") != applied.get("remark")
            if cat_changed or rem_changed:
                tx.category = applied.get("category", tx.category)
                tx.remark = applied.get("remark", tx.remark)
                tx.updated_at = datetime.utcnow()
                changes.append({
                    "id": tx.id,
                    "before": original,
                    "after": applied,
                })
        if changes:
            self._db.commit()
        return {"modified_count": len(changes), "changes": changes}

    def realias_all_transactions(self) -> dict:
        """Apply alias rules to all non-deleted transactions, updating product_alias only."""
        txs = (
            self._db.query(Transaction)
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.is_deleted == 0,
            )
            .all()
        )
        changes = []
        for tx in txs:
            original = _tx_to_dict(tx)
            applied = self._apply_alias_rules(original.copy())
            alias_changed = original.get("product_alias") != applied.get("product_alias")
            if alias_changed:
                tx.product_alias = applied.get("product_alias", tx.product_alias)
                tx.updated_at = datetime.utcnow()
                changes.append({
                    "id": tx.id,
                    "before": original,
                    "after": applied,
                })
        if changes:
            self._db.commit()
        return {"modified_count": len(changes), "changes": changes}

    # ---------- Statistics ----------

    def get_summary_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source=None,
    ) -> dict:
        q = self._db.query(Transaction).filter(
            Transaction.is_deleted == 0,
            Transaction.user_id == self._user_id,
        )
        if start_date:
            q = q.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            q = q.filter(Transaction.transaction_time <= end_dt)
        q = _apply_source_filter(q, source)

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

    def get_monthly_stats(self, year: int, source=None) -> list[dict]:
        sources = _normalize_sources(source)
        filters = [
            Transaction.is_deleted == 0,
            Transaction.user_id == self._user_id,
            func.strftime("%Y", Transaction.transaction_time) == str(year),
            Transaction.direction.in_(["income", "expense"]),
        ]
        if "__none__" in sources:
            filters.append(Transaction.source == "__none__")
        elif len(sources) == 1:
            filters.append(Transaction.source == sources[0])
        elif len(sources) > 1:
            filters.append(Transaction.source.in_(sources))

        rows = (
            self._db.query(
                func.strftime("%m", Transaction.transaction_time).label("month"),
                Transaction.direction,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .filter(*filters)
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

    def get_monthly_stats_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: Optional[str] = None,
        category: Optional[str] = None,
        source=None,
        search: Optional[str] = None,
    ) -> list[dict]:
        q = self._build_filter_query(
            start_date=start_date,
            end_date=end_date,
            direction=direction,
            category=category,
            source=source,
            search=search,
        ).filter(Transaction.direction.in_(["income", "expense"]))

        rows = (
            q.with_entities(
                func.strftime("%Y-%m", Transaction.transaction_time).label("month_key"),
                Transaction.direction,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .group_by("month_key", Transaction.direction)
            .order_by("month_key")
            .all()
        )

        month_data: dict[str, dict] = {}
        for row in rows:
            key = row.month_key
            if key not in month_data:
                month_data[key] = {"month": key, "income": 0.0, "expense": 0.0, "count": 0}
            if row.direction == "income":
                month_data[key]["income"] = round(row.total or 0, 2)
            else:
                month_data[key]["expense"] = round(row.total or 0, 2)
            month_data[key]["count"] += row.cnt

        for item in month_data.values():
            item["net"] = round(item["income"] - item["expense"], 2)
        return list(month_data.values())

    def get_income_stats_by_source(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: Optional[str] = None,
        category: Optional[str] = None,
        source=None,
        search: Optional[str] = None,
    ) -> list[dict]:
        q = self._build_filter_query(
            start_date=start_date,
            end_date=end_date,
            direction=direction,
            category=category,
            source=source,
            search=search,
        )
        q = q.filter(Transaction.direction == "income")

        rows = (
            q.with_entities(
                Transaction.source.label("label"),
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .group_by(Transaction.source)
            .order_by(func.sum(Transaction.amount).desc())
            .all()
        )

        grand_total = sum((r.total or 0) for r in rows) or 0.0
        return [
            {
                "label": r.label or "未标记来源",
                "amount": round(r.total or 0, 2),
                "count": r.cnt,
                "percentage": round((r.total or 0) / grand_total * 100, 2) if grand_total else 0.0,
            }
            for r in rows
        ]

    def get_income_stats_by_product(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: Optional[str] = None,
        category: Optional[str] = None,
        source=None,
        search: Optional[str] = None,
    ) -> list[dict]:
        product_label = func.coalesce(
            func.nullif(Transaction.product_alias, ""),
            func.nullif(Transaction.product, ""),
            "未命名商品",
        )
        q = self._build_filter_query(
            start_date=start_date,
            end_date=end_date,
            direction=direction,
            category=category,
            source=source,
            search=search,
        )
        q = q.filter(Transaction.direction == "income")

        rows = (
            q.with_entities(
                product_label.label("label"),
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .group_by(product_label)
            .order_by(func.sum(Transaction.amount).desc())
            .all()
        )

        grand_total = sum((r.total or 0) for r in rows) or 0.0
        return [
            {
                "label": r.label or "未命名商品",
                "amount": round(r.total or 0, 2),
                "count": r.cnt,
                "percentage": round((r.total or 0) / grand_total * 100, 2) if grand_total else 0.0,
            }
            for r in rows
        ]

    def get_category_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "expense",
        source=None,
    ) -> list[dict]:
        q = (
            self._db.query(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("cnt"),
            )
            .filter(
                Transaction.is_deleted == 0,
                Transaction.user_id == self._user_id,
                Transaction.direction == direction,
            )
        )
        if start_date:
            q = q.filter(Transaction.transaction_time >= datetime.fromisoformat(start_date))
        if end_date:
            end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)
            q = q.filter(Transaction.transaction_time <= end_dt)
        q = _apply_source_filter(q, source)

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

    def get_daily_stats(self, year: int, month: int, source=None) -> list[dict]:
        month_str = f"{year}-{month:02d}"
        sources = _normalize_sources(source)
        filters = [
            Transaction.is_deleted == 0,
            Transaction.user_id == self._user_id,
            func.strftime("%Y-%m", Transaction.transaction_time) == month_str,
            Transaction.direction.in_(["income", "expense"]),
        ]
        if "__none__" in sources:
            filters.append(Transaction.source == "__none__")
        elif len(sources) == 1:
            filters.append(Transaction.source == sources[0])
        elif len(sources) > 1:
            filters.append(Transaction.source.in_(sources))

        rows = (
            self._db.query(
                func.strftime("%Y-%m-%d", Transaction.transaction_time).label("day"),
                Transaction.direction,
                func.sum(Transaction.amount).label("total"),
            )
            .filter(*filters)
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

    # ---------- User Preferences ----------

    def get_user_preference(self, key: str, default=None):
        pref = (
            self._db.query(UserPreference)
            .filter(
                UserPreference.user_id == self._user_id,
                UserPreference.key == key,
            )
            .first()
        )
        if not pref:
            return default
        try:
            return json.loads(pref.value)
        except json.JSONDecodeError:
            return default

    def set_user_preference(self, key: str, value) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        pref = (
            self._db.query(UserPreference)
            .filter(
                UserPreference.user_id == self._user_id,
                UserPreference.key == key,
            )
            .first()
        )
        if pref:
            pref.value = encoded
            pref.updated_at = datetime.utcnow()
        else:
            pref = UserPreference(
                user_id=self._user_id,
                key=key,
                value=encoded,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self._db.add(pref)
        self._db.commit()

    # ---------- Import Batches ----------

    def create_import_batch(self, data: dict) -> dict:
        data["user_id"] = self._user_id
        batch = ImportBatch(**data)
        self._db.add(batch)
        self._db.commit()
        self._db.refresh(batch)
        return _batch_to_dict(batch)

    def update_import_batch(self, batch_id: str, data: dict) -> Optional[dict]:
        batch = self._db.query(ImportBatch).filter(
            ImportBatch.id == batch_id,
            ImportBatch.user_id == self._user_id,
        ).first()
        if not batch:
            return None
        for k, v in data.items():
            setattr(batch, k, v)
        self._db.commit()
        self._db.refresh(batch)
        return _batch_to_dict(batch)

    def get_import_batch(self, batch_id: str) -> Optional[dict]:
        batch = self._db.query(ImportBatch).filter(
            ImportBatch.id == batch_id,
            ImportBatch.user_id == self._user_id,
        ).first()
        return _batch_to_dict(batch) if batch else None

    def list_import_batches(self) -> list[dict]:
        batches = (
            self._db.query(ImportBatch)
            .filter(
                ImportBatch.user_id == self._user_id,
                ImportBatch.source != "image_recognize",
            )
            .order_by(ImportBatch.imported_at.desc())
            .all()
        )
        return [_batch_to_dict(b) for b in batches]

    def check_duplicates(self, items: list[dict]) -> list[bool]:
        """Check which items already exist (same time + amount + counterparty)."""
        results = []
        for item in items:
            tx_time = item.get("transaction_time")
            if isinstance(tx_time, str):
                try:
                    tx_time = datetime.fromisoformat(tx_time.replace(" ", "T"))
                except (ValueError, TypeError):
                    results.append(False)
                    continue
            q = self._db.query(Transaction.id).filter(
                Transaction.user_id == self._user_id,
                Transaction.is_deleted == 0,
                Transaction.amount == float(item.get("amount", 0)),
                Transaction.transaction_time == tx_time,
            )
            counterparty = item.get("counterparty", "")
            if counterparty:
                q = q.filter(Transaction.counterparty == counterparty)
            results.append(q.first() is not None)
        return results

    def check_import_duplicates(self, items: list[dict]) -> list[bool]:
        """Check duplicates for bill imports using source/source_order_id when available."""
        results = []
        for item in items:
            source = item.get("source")
            source_order_id = item.get("source_order_id")
            if source and source_order_id:
                exists = (
                    self._db.query(Transaction.id)
                    .filter(
                        Transaction.user_id == self._user_id,
                        Transaction.is_deleted == 0,
                        Transaction.source == source,
                        Transaction.source_order_id == source_order_id,
                    )
                    .first()
                    is not None
                )
                results.append(exists)
                continue
            results.extend(self.check_duplicates([item]))
        return results

    def count_today_image_imports(self) -> int:
        """Count image-source imported_rows for today (UTC) for this user."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = (
            self._db.query(func.coalesce(func.sum(ImportBatch.imported_rows), 0))
            .filter(
                ImportBatch.user_id == self._user_id,
                ImportBatch.source == "image",
                ImportBatch.imported_at >= today_start,
            )
            .scalar()
        )
        return int(result)

    def count_today_image_recognitions(self) -> int:
        """Count images recognized today (UTC) for this user.

        Counts total_rows from batches with source='image_recognize'.
        Each such batch records how many images were sent in one recognition call.
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = (
            self._db.query(func.coalesce(func.sum(ImportBatch.total_rows), 0))
            .filter(
                ImportBatch.user_id == self._user_id,
                ImportBatch.source == "image_recognize",
                ImportBatch.imported_at >= today_start,
            )
            .scalar()
        )
        return int(result)

    # ---------- Classification Rules ----------

    def list_classification_rules(self) -> list[dict]:
        rules = (
            self._db.query(ClassificationRule)
            .filter(ClassificationRule.user_id == self._user_id)
            .order_by(ClassificationRule.priority.asc(), ClassificationRule.id.asc())
            .all()
        )
        return [_rule_to_dict(rule) for rule in rules]

    def create_classification_rule(self, data: dict) -> dict:
        rule = ClassificationRule(
            user_id=self._user_id,
            name=data["name"],
            priority=data.get("priority", 100),
            is_active=data.get("is_active", True),
            match_counterparty=data.get("match_counterparty", ""),
            match_product=data.get("match_product", ""),
            match_payment_method=data.get("match_payment_method", ""),
            match_transaction_type=data.get("match_transaction_type", ""),
            category=data.get("category", ""),
            remark=data.get("remark", ""),
        )
        self._db.add(rule)
        self._db.commit()
        self._db.refresh(rule)
        return _rule_to_dict(rule)

    def update_classification_rule(self, rule_id: int, data: dict) -> Optional[dict]:
        rule = (
            self._db.query(ClassificationRule)
            .filter(
                ClassificationRule.id == rule_id,
                ClassificationRule.user_id == self._user_id,
            )
            .first()
        )
        if not rule:
            return None
        for key, value in data.items():
            setattr(rule, key, value)
        rule.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(rule)
        return _rule_to_dict(rule)

    def delete_classification_rule(self, rule_id: int) -> bool:
        rule = (
            self._db.query(ClassificationRule)
            .filter(
                ClassificationRule.id == rule_id,
                ClassificationRule.user_id == self._user_id,
            )
            .first()
        )
        if not rule:
            return False
        self._db.delete(rule)
        self._db.commit()
        return True

    # ---------- Alias Rules ----------

    def list_alias_rules(self) -> list[dict]:
        rules = (
            self._db.query(AliasRule)
            .filter(AliasRule.user_id == self._user_id)
            .order_by(AliasRule.priority.asc(), AliasRule.id.asc())
            .all()
        )
        return [_alias_rule_to_dict(rule) for rule in rules]

    def create_alias_rule(self, data: dict) -> dict:
        rule = AliasRule(
            user_id=self._user_id,
            name=data["name"],
            priority=data.get("priority", 100),
            is_active=data.get("is_active", True),
            match_counterparty=data.get("match_counterparty", ""),
            match_product=data.get("match_product", ""),
            match_payment_method=data.get("match_payment_method", ""),
            match_transaction_type=data.get("match_transaction_type", ""),
            product_alias=data.get("product_alias", ""),
        )
        self._db.add(rule)
        self._db.commit()
        self._db.refresh(rule)
        return _alias_rule_to_dict(rule)

    def update_alias_rule(self, rule_id: int, data: dict) -> Optional[dict]:
        rule = (
            self._db.query(AliasRule)
            .filter(
                AliasRule.id == rule_id,
                AliasRule.user_id == self._user_id,
            )
            .first()
        )
        if not rule:
            return None
        for key, value in data.items():
            setattr(rule, key, value)
        rule.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(rule)
        return _alias_rule_to_dict(rule)

    def delete_alias_rule(self, rule_id: int) -> bool:
        rule = (
            self._db.query(AliasRule)
            .filter(
                AliasRule.id == rule_id,
                AliasRule.user_id == self._user_id,
            )
            .first()
        )
        if not rule:
            return False
        self._db.delete(rule)
        self._db.commit()
        return True
