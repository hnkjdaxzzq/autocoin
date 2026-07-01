from datetime import datetime, timedelta
import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.transaction import Transaction
from autocoin.models.user import User

router = APIRouter(prefix="/special-data-processing", tags=["special-data-processing"])


class RefundConfirmItem(BaseModel):
    refund_id: int
    selected_expense_id: Optional[int] = None
    mark_neutral: bool = True


class RefundConfirmRequest(BaseModel):
    items: list[RefundConfirmItem]


class WealthConfirmRequest(BaseModel):
    ids: list[int]


PUNCT_TRANSLATION = str.maketrans({
    "，": ",",
    "。": ".",
    "：": ":",
    "；": ";",
    "！": "!",
    "？": "?",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "｛": "{",
    "｝": "}",
    "、": ",",
    "－": "-",
    "—": "-",
    "–": "-",
    "－": "-",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
})


def _tx_to_response(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "source": tx.source,
        "transaction_time": tx.transaction_time.isoformat() if tx.transaction_time else None,
        "category": tx.category,
        "counterparty": tx.counterparty,
        "product": tx.product,
        "direction": tx.direction,
        "amount": tx.amount,
        "payment_method": tx.payment_method,
        "remark": tx.remark,
        "finishrefundcheck": tx.finishrefundcheck,
    }


def _wealth_query(db: Session, user_id: int):
    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.is_deleted == 0,
            Transaction.direction != "neutral",
            Transaction.source == "alipay",
            Transaction.counterparty == "余额宝",
            Transaction.product.ilike("%余额宝%"),
        )
    )


def _normalize_product(value: Optional[str]) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.translate(PUNCT_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _strip_refund_marker(source: str, product: Optional[str]) -> str:
    text = unicodedata.normalize("NFKC", product or "")
    if source == "alipay":
        text = re.sub(r"^\s*退款\s*-\s*", "", text)
    elif source == "汇丰PULSE":
        text = re.sub(r"\s*退款\s*$", "", text)
    return text


def _is_suspected_refund(tx: Transaction) -> bool:
    if tx.source == "wechat":
        return tx.direction in ("income", "neutral")
    if tx.source == "汇丰PULSE":
        return tx.direction == "income"
    if tx.source == "alipay":
        return tx.direction in ("income", "neutral")
    return False


def _suspected_query(db: Session, user_id: int):
    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.is_deleted == 0,
            or_(
                Transaction.finishrefundcheck == 0,
                Transaction.finishrefundcheck == None,
            ),
            or_(
                (Transaction.source == "wechat") & Transaction.direction.in_(["income", "neutral"]),
                (Transaction.source == "汇丰PULSE") & (Transaction.direction == "income"),
                (Transaction.source == "alipay") & Transaction.direction.in_(["income", "neutral"]),
            ),
        )
    )


def _base_expense_candidates(db: Session, user_id: int, refund: Transaction):
    start_time = refund.transaction_time - timedelta(days=30)
    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.is_deleted == 0,
            Transaction.direction == "expense",
            Transaction.source == refund.source,
            Transaction.transaction_time >= start_time,
            Transaction.transaction_time <= refund.transaction_time,
        )
        .order_by(Transaction.transaction_time.desc(), Transaction.id.asc())
    )


def _matching_expense_candidates(db: Session, user_id: int, refund: Transaction) -> list[Transaction]:
    q = _base_expense_candidates(db, user_id, refund)
    if refund.source == "wechat":
        return (
            q.filter(
                Transaction.amount == refund.amount,
                Transaction.payment_method == refund.payment_method,
            )
            .all()
        )

    if refund.source == "汇丰PULSE":
        refund_product = _normalize_product(_strip_refund_marker(refund.source, refund.product))
        rows = (
            q.filter(
                Transaction.amount == refund.amount,
                Transaction.payment_method == refund.payment_method,
                Transaction.counterparty == refund.counterparty,
            )
            .all()
        )
        return [
            tx for tx in rows
            if _normalize_product(tx.product) == refund_product
        ]

    if refund.source == "alipay":
        refund_product = _normalize_product(_strip_refund_marker(refund.source, refund.product))
        rows = (
            q.filter(
                Transaction.amount == refund.amount,
                Transaction.payment_method == refund.payment_method,
                Transaction.counterparty == refund.counterparty,
            )
            .all()
        )
        return [
            tx for tx in rows
            if _normalize_product(tx.product) == refund_product
        ]

    return []


def _build_refund_search(db: Session, user_id: int) -> dict:
    suspected = (
        _suspected_query(db, user_id)
        .order_by(Transaction.transaction_time.desc(), Transaction.id.asc())
        .all()
    )
    items = []
    for refund in suspected:
        candidates = _matching_expense_candidates(db, user_id, refund)
        if not candidates:
            continue
        items.append({
            "refund_transaction": _tx_to_response(refund),
            "expense_candidates": [_tx_to_response(tx) for tx in candidates],
        })
    return {
        "suspected_total": len(suspected),
        "matched_total": len(items),
        "items": items,
    }


@router.post("/refunds/search")
def search_refund_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _build_refund_search(db, user.id)


@router.post("/wealth/search")
def search_wealth_candidates(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        _wealth_query(db, user.id)
        .order_by(Transaction.transaction_time.desc(), Transaction.id.asc())
        .all()
    )
    return {
        "total": len(items),
        "items": [_tx_to_response(tx) for tx in items],
    }


@router.post("/wealth/confirm")
def confirm_wealth_candidates(
    body: WealthConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = list(dict.fromkeys(body.ids))
    if not ids:
        return {"updated": 0, "total": 0}

    now = datetime.utcnow()
    try:
        rows = _wealth_query(db, user.id).filter(Transaction.id.in_(ids)).all()
        for tx in rows:
            tx.direction = "neutral"
            tx.updated_at = now
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="理财数据处理失败") from exc

    return {"updated": len(rows), "total": len(ids)}


@router.post("/refunds/confirm")
def confirm_refund_candidates(
    body: RefundConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    marked_refunds = 0
    marked_expenses = 0
    neutralized = 0

    try:
        for item in body.items:
            refund = (
                db.query(Transaction)
                .filter(
                    Transaction.id == item.refund_id,
                    Transaction.user_id == user.id,
                    Transaction.is_deleted == 0,
                )
                .first()
            )
            if not refund or not _is_suspected_refund(refund):
                continue

            candidates = _matching_expense_candidates(db, user.id, refund)
            candidate_ids = {tx.id for tx in candidates}
            selected_expense = None
            if item.selected_expense_id and item.selected_expense_id in candidate_ids:
                selected_expense = next(tx for tx in candidates if tx.id == item.selected_expense_id)

            refund.finishrefundcheck = 1
            refund.updated_at = now
            marked_refunds += 1

            if selected_expense:
                selected_expense.finishrefundcheck = 1
                selected_expense.updated_at = now
                marked_expenses += 1

            if item.mark_neutral:
                if refund.direction != "neutral":
                    refund.direction = "neutral"
                    neutralized += 1
                if selected_expense and selected_expense.direction != "neutral":
                    selected_expense.direction = "neutral"
                    neutralized += 1

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="退款数据处理失败") from exc

    return {
        "marked_refunds": marked_refunds,
        "marked_expenses": marked_expenses,
        "neutralized": neutralized,
    }
