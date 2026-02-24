from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.statistics import (
    CategoryResponse,
    DailyResponse,
    MonthlyResponse,
    SummaryResponse,
)
from autocoin.services.stats_service import StatsService

router = APIRouter(prefix="/statistics", tags=["statistics"])


def get_service(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StatsService:
    return StatsService(SQLiteRepository(db, user.id))


@router.get("/summary", response_model=SummaryResponse)
def summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service: StatsService = Depends(get_service),
):
    return service.summary(start_date, end_date)


@router.get("/monthly", response_model=MonthlyResponse)
def monthly(year: int, service: StatsService = Depends(get_service)):
    return service.monthly(year)


@router.get("/category", response_model=CategoryResponse)
def category(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    direction: str = "expense",
    service: StatsService = Depends(get_service),
):
    return service.category(start_date, end_date, direction)


@router.get("/daily", response_model=DailyResponse)
def daily(year: int, month: int, service: StatsService = Depends(get_service)):
    return service.daily(year, month)
