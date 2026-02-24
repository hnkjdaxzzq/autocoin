import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.transaction import (
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
