import math
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.transaction import TransactionListResponse

router = APIRouter(prefix="/broker-income-analysis", tags=["broker-income-analysis"])

PREF_KEY_SELECTED_SOURCES = "broker_income_analysis.selected_sources"
DEFAULT_SELECTED_SOURCES = ["招商证券", "盈透IBKR", "MOOMOO", "汇丰PULSE"]


class SourcePreference(BaseModel):
    sources: list[str]


def get_repo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SQLiteRepository:
    return SQLiteRepository(db, user.id)


@router.get("/preferences/sources", response_model=SourcePreference)
def get_source_preference(repo: SQLiteRepository = Depends(get_repo)):
    sources = repo.get_user_preference(PREF_KEY_SELECTED_SOURCES, DEFAULT_SELECTED_SOURCES)
    if not isinstance(sources, list):
        sources = DEFAULT_SELECTED_SOURCES
    return SourcePreference(sources=sources)


@router.put("/preferences/sources", response_model=SourcePreference)
def update_source_preference(
    body: SourcePreference,
    repo: SQLiteRepository = Depends(get_repo),
):
    repo.set_user_preference(PREF_KEY_SELECTED_SOURCES, body.sources)
    return body


@router.get("/transactions", response_model=TransactionListResponse)
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


@router.get("/categories")
def list_categories(
    source: Optional[str] = None,
    repo: SQLiteRepository = Depends(get_repo),
):
    return {"categories": repo.list_categories(source=source)}


@router.get("/monthly")
def monthly(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source: Optional[str] = None,
    repo: SQLiteRepository = Depends(get_repo),
):
    return {
        "year": 0,
        "months": repo.get_monthly_stats_range(
            start_date=start_date,
            end_date=end_date,
            source=source,
        ),
    }
