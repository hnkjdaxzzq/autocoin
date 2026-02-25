import io
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.transaction import (
    BatchDeleteRequest,
    BatchUpdateRequest,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_repo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SQLiteRepository:
    return SQLiteRepository(db, user.id)


@router.get("", response_model=TransactionListResponse)
def list_transactions(
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
    repo: SQLiteRepository = Depends(get_repo),
):
    page_size = min(page_size, 200)
    items, total = repo.list_transactions(
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        category=category,
        source=source,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    summary = repo.get_filtered_summary(
        start_date=start_date,
        end_date=end_date,
        direction=direction,
        category=category,
        source=source,
        search=search,
    )
    total_pages = math.ceil(total / page_size) if page_size else 1
    return TransactionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        summary=summary,
    )


@router.post("", response_model=TransactionResponse, status_code=201)
def create_transaction(
    body: TransactionCreate,
    repo: SQLiteRepository = Depends(get_repo),
):
    try:
        tx = repo.create_transaction(body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return tx


# --- Specific paths MUST come before /{id} to avoid path conflict ---

@router.get("/export/csv")
def export_csv(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    direction: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    repo: SQLiteRepository = Depends(get_repo),
):
    """Export filtered transactions as CSV file."""
    import csv
    items, _ = repo.list_transactions(
        page=1, page_size=100000,
        start_date=start_date, end_date=end_date,
        direction=direction, category=category,
        source=source, search=search,
        sort_by="transaction_time", sort_dir="desc",
    )
    buf = io.StringIO()
    buf.write('\ufeff')  # BOM for Excel
    writer = csv.writer(buf)
    writer.writerow(["交易时间", "来源", "分类", "交易对方", "商品说明", "收支方向", "金额", "支付方式", "备注"])
    dir_map = {"income": "收入", "expense": "支出", "neutral": "不计收支"}
    src_map = {"alipay": "支付宝", "wechat": "微信支付", "manual": "手动录入", "image": "图片导入"}
    for tx in items:
        writer.writerow([
            tx.get("transaction_time", ""),
            src_map.get(tx.get("source", ""), tx.get("source", "")),
            tx.get("category", ""),
            tx.get("counterparty", ""),
            tx.get("product", ""),
            dir_map.get(tx.get("direction", ""), tx.get("direction", "")),
            tx.get("amount", 0),
            tx.get("payment_method", ""),
            tx.get("remark", ""),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=autocoin_export.csv"},
    )


@router.get("/export/excel")
def export_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    direction: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    repo: SQLiteRepository = Depends(get_repo),
):
    """Export filtered transactions as Excel file."""
    from openpyxl import Workbook
    items, _ = repo.list_transactions(
        page=1, page_size=100000,
        start_date=start_date, end_date=end_date,
        direction=direction, category=category,
        source=source, search=search,
        sort_by="transaction_time", sort_dir="desc",
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "账单明细"
    headers = ["交易时间", "来源", "分类", "交易对方", "商品说明", "收支方向", "金额", "支付方式", "备注"]
    ws.append(headers)
    dir_map = {"income": "收入", "expense": "支出", "neutral": "不计收支"}
    src_map = {"alipay": "支付宝", "wechat": "微信支付", "manual": "手动录入", "image": "图片导入"}
    for tx in items:
        ws.append([
            tx.get("transaction_time", ""),
            src_map.get(tx.get("source", ""), tx.get("source", "")),
            tx.get("category", ""),
            tx.get("counterparty", ""),
            tx.get("product", ""),
            dir_map.get(tx.get("direction", ""), tx.get("direction", "")),
            tx.get("amount", 0),
            tx.get("payment_method", ""),
            tx.get("remark", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=autocoin_export.xlsx"},
    )


@router.get("/categories")
def list_categories(repo: SQLiteRepository = Depends(get_repo)):
    """Return distinct categories for current user."""
    categories = repo.list_categories()
    return {"categories": categories}


@router.post("/batch/delete")
def batch_delete(body: BatchDeleteRequest, repo: SQLiteRepository = Depends(get_repo)):
    """Soft-delete multiple transactions."""
    deleted = 0
    for tid in body.ids:
        if repo.soft_delete_transaction(tid):
            deleted += 1
    return {"deleted": deleted, "total": len(body.ids)}


@router.post("/batch/update")
def batch_update(body: BatchUpdateRequest, repo: SQLiteRepository = Depends(get_repo)):
    """Batch update category/direction for multiple transactions."""
    updated = 0
    update_data = {}
    if body.category is not None:
        update_data["category"] = body.category
    if body.direction is not None:
        update_data["direction"] = body.direction
    for tid in body.ids:
        if repo.update_transaction(tid, update_data):
            updated += 1
    return {"updated": updated, "total": len(body.ids)}


# --- Path parameter routes (must be after specific paths) ---

@router.get("/{id}", response_model=TransactionResponse)
def get_transaction(id: int, repo: SQLiteRepository = Depends(get_repo)):
    tx = repo.get_transaction(id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.put("/{id}", response_model=TransactionResponse)
def update_transaction(
    id: int,
    body: TransactionUpdate,
    repo: SQLiteRepository = Depends(get_repo),
):
    tx = repo.update_transaction(id, body.model_dump(exclude_none=True))
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.delete("/{id}")
def delete_transaction(id: int, repo: SQLiteRepository = Depends(get_repo)):
    ok = repo.soft_delete_transaction(id)
    if not ok:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"ok": True}
