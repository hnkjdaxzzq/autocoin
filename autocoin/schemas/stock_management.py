from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from autocoin.services.stock_constants import normalize_stock_id, normalize_stock_market


class StockCreate(BaseModel):
    stock_market: str = Field(default="CN")
    stock_id: str = Field(min_length=1, max_length=32)
    stock_name: Optional[str] = Field(default=None, max_length=128)
    stock_alias: Optional[str] = Field(default=None, max_length=128)
    stock_amount: float = Field(gt=0)
    stock_average_price: Optional[float] = Field(default=None, ge=0)
    stock_remark: Optional[str] = Field(default=None, max_length=50)
    stock_transaction_date: Optional[date] = None

    @field_validator("stock_market")
    @classmethod
    def validate_market(cls, value: str) -> str:
        return normalize_stock_market(value)

    @field_validator("stock_id")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalize_stock_id(value)

    @field_validator("stock_name", "stock_alias", "stock_remark")
    @classmethod
    def blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class StockItem(BaseModel):
    stock_vid: str
    stock_market: str
    stock_id: str
    stock_name: Optional[str] = None
    stock_alias: Optional[str] = None
    stock_amount: float
    stock_average_price: Optional[float] = None
    stock_currency: str
    stock_remark: Optional[str] = None
    stock_transaction_date: Optional[str] = None
    stock_entry_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class StockMutationResponse(BaseModel):
    item: StockItem
    lookup_error: Optional[str] = None


class StockMessageResponse(BaseModel):
    message: str


class StockLookupResponse(BaseModel):
    stock_market: str
    stock_id: str
    stock_name: Optional[str] = None
    current_price: Optional[float] = None
    stock_currency: str
    raw_api_source: Optional[str] = None
    raw_api_data: Any = None
    queried_at: Optional[str] = None
    from_cache: bool = False
    cache_stale: Optional[bool] = None
    stock_alias: Optional[str] = None


class StockSummaryItem(BaseModel):
    stock_market: str
    stock_id: str
    stock_name: Optional[str] = None
    stock_alias: Optional[str] = None
    stock_amount: float
    current_price: Optional[float] = None
    total_value: Optional[float] = None
    total_cost: float
    current_return_rate: Optional[float] = None
    stock_currency: str
    stock_average_price: Optional[float] = None
    lookup_error: Optional[str] = None
    price_from_cache: bool = False
    price_cache_stale: bool = False
    price_refresh_needed: bool = False
    stock_dividend_reference_year: Optional[int] = None
    stock_dividend_frequency: Optional[int] = None
    stock_dividend_per_share_last_year: Optional[float] = None
    stock_dividend_change_rate: Optional[float] = None
    stock_dividend_refresh_needed: bool = False


class PortfolioSummaryRow(BaseModel):
    currency: str
    asset_total_value: Optional[float] = None
    holding_total_cost: Optional[float] = None
    principal_return_rate: Optional[float] = None
    annual_dividend: Optional[float] = None
    after_tax_dividend: Optional[float] = None
    holding_dividend_rate: Optional[float] = None
    asset_value_pending: bool = False
    dividend_pending: bool = False
    exchange_rate_to_cny: Optional[float] = None
    exchange_rate_error: Optional[str] = None
    label: Optional[str] = None
    is_converted: Optional[bool] = None


class PortfolioSummary(BaseModel):
    rows: list[PortfolioSummaryRow]
    converted_total: Optional[PortfolioSummaryRow] = None


class StockSummaryResponse(BaseModel):
    items: list[StockSummaryItem]
    portfolio_summary: PortfolioSummary


class ExternalSection(BaseModel):
    title: str
    source: str
    status: str
    columns: list[str]
    rows: list[dict[str, Any]]
    error: Optional[str] = None
    from_cache: bool = False
    queried_at: Optional[str] = None
    dividend_parse: Optional[dict[str, Any]] = None


class StockDetailsResponse(BaseModel):
    summary: StockSummaryItem
    lookup: Optional[StockLookupResponse] = None
    lookup_error: Optional[str] = None
    records: list[StockItem]
    external_sections: list[ExternalSection]
    updated_at: Optional[str] = None


class StockRecordsResponse(BaseModel):
    items: list[StockItem]
    total: int
    page: int
    page_size: int
    total_pages: int
