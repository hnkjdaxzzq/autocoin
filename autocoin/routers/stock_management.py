from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.schemas.stock_management import (
    StockCreate,
    StockDetailsResponse,
    StockLookupResponse,
    StockMessageResponse,
    StockMutationResponse,
    StockRecordsResponse,
    StockSummaryResponse,
)
from autocoin.services.stock_constants import STOCK_MARKET_ERROR, normalize_stock_id, normalize_stock_market
from autocoin.services.stock_portfolio_service import StockPortfolioService, stock_to_dict

router = APIRouter(prefix="/stock-management", tags=["stock-management"])


@router.get("/lookup", response_model=StockLookupResponse)
def lookup_stock(
    stock_market: str = Query("CN"),
    stock_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    market, code = _normalize_market_and_code(stock_market, stock_id)
    service = StockPortfolioService(db, user.id)
    try:
        info = service.lookup_stock(market, code)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    return info


@router.post("/stocks", response_model=StockMutationResponse, status_code=201)
def create_stock(
    body: StockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = StockPortfolioService(db, user.id).create_stock(body)
    db.commit()
    stock = result["stock"]
    db.refresh(stock)
    return {"item": stock_to_dict(stock), "lookup_error": result["lookup_error"]}


@router.get("/stocks/summary", response_model=StockSummaryResponse)
def stock_summary(
    refresh_prices: bool = Query(False),
    refresh_dividends: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = StockPortfolioService(db, user.id).summary(
        refresh_prices=refresh_prices,
        refresh_dividends=refresh_dividends,
    )
    db.commit()
    return result


@router.put("/stocks/{stock_vid}", response_model=StockMutationResponse)
def update_stock(
    stock_vid: str,
    body: StockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = StockPortfolioService(db, user.id).update_stock(stock_vid, body)
    if not result:
        raise HTTPException(status_code=404, detail="未找到该股票资产")
    db.commit()
    stock = result["stock"]
    db.refresh(stock)
    return {"item": stock_to_dict(stock), "lookup_error": result["lookup_error"]}


@router.delete("/stocks/{stock_vid}", response_model=StockMessageResponse)
def delete_stock(
    stock_vid: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deleted = StockPortfolioService(db, user.id).delete_stock(stock_vid)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到该股票资产")
    db.commit()
    return {"message": "股票资产已删除"}


@router.get("/stocks/{stock_market}/{stock_id}/details", response_model=StockDetailsResponse)
def stock_details(
    stock_market: str,
    stock_id: str,
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    market, code = _normalize_market_and_code(stock_market, stock_id)

    result = StockPortfolioService(db, user.id).details(market, code, force_refresh=force_refresh)
    if not result:
        raise HTTPException(status_code=404, detail="未找到该股票资产")
    db.commit()
    return result


@router.get("/stocks/{stock_market}/{stock_id}/records", response_model=StockRecordsResponse)
def stock_records(
    stock_market: str,
    stock_id: str,
    page: int = 1,
    page_size: int = 5,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    market, code = _normalize_market_and_code(stock_market, stock_id)
    return StockPortfolioService(db, user.id).records(market, code, page=page, page_size=page_size)


def _normalize_market_and_code(stock_market: str, stock_id: str) -> tuple[str, str]:
    try:
        return normalize_stock_market(stock_market), normalize_stock_id(stock_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=STOCK_MARKET_ERROR)
