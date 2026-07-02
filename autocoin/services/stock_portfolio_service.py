import math
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from autocoin.models.stock_data import StockData
from autocoin.services.stock_constants import currency_for_market
from autocoin.services.stock_market_service import StockMarketService


class StockPortfolioService:
    def __init__(self, db: Session, user_id: int, market_service: Optional[StockMarketService] = None):
        self._db = db
        self._user_id = user_id
        self._market_service = market_service or StockMarketService(db)

    def lookup_stock(self, market: str, stock_id: str) -> dict:
        info = self._market_service.lookup(market, stock_id)
        info["stock_alias"] = self.latest_alias(market, stock_id)
        return info

    def create_stock(self, body) -> dict:
        lookup_info, lookup_error = self._market_service.try_lookup(body.stock_market, body.stock_id)
        now = datetime.utcnow()
        stock = StockData(
            stock_vid=self._generate_stock_vid(),
            user_id=self._user_id,
            stock_market=body.stock_market,
            stock_id=body.stock_id,
            stock_currency=currency_for_market(body.stock_market),
            stock_entry_time=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(stock)
        self._apply_stock_body(stock, body, lookup_info, now)
        self._db.flush()
        if body.stock_alias:
            self._sync_stock_alias(body.stock_market, body.stock_id, body.stock_alias, now)
        return {"stock": stock, "lookup_error": lookup_error}

    def update_stock(self, stock_vid: str, body) -> Optional[dict]:
        stock = self._stock_by_vid(stock_vid)
        if not stock:
            return None
        lookup_info, lookup_error = self._market_service.try_lookup(body.stock_market, body.stock_id)
        now = datetime.utcnow()
        self._apply_stock_body(stock, body, lookup_info, now)
        self._db.flush()
        if body.stock_alias:
            self._sync_stock_alias(body.stock_market, body.stock_id, body.stock_alias, now)
        return {"stock": stock, "lookup_error": lookup_error}

    def delete_stock(self, stock_vid: str) -> bool:
        stock = self._stock_by_vid(stock_vid)
        if not stock:
            return False
        self._db.delete(stock)
        return True

    def summary(self, refresh_prices: bool = False, refresh_dividends: bool = False) -> dict:
        rows = (
            self._db.query(
                StockData.stock_market,
                StockData.stock_id,
                func.max(StockData.stock_name).label("stock_name"),
                func.sum(StockData.stock_amount).label("total_amount"),
                func.sum(
                    case(
                        (StockData.stock_average_price.isnot(None), StockData.stock_amount * StockData.stock_average_price),
                        else_=0,
                    )
                ).label("cost_total"),
                func.sum(
                    case(
                        (StockData.stock_average_price.isnot(None), StockData.stock_amount),
                        else_=0,
                    )
                ).label("cost_amount"),
            )
            .filter(StockData.user_id == self._user_id)
            .group_by(StockData.stock_market, StockData.stock_id)
            .order_by(StockData.stock_market.asc(), StockData.stock_id.asc())
            .all()
        )
        items = []
        for row in rows:
            item = self.summary_item(
                row.stock_market,
                row.stock_id,
                refresh_prices=refresh_prices,
                refresh_dividends=refresh_dividends,
            )
            if item:
                items.append(item)
        return {"items": items, "portfolio_summary": self.portfolio_summary(items)}

    def details(self, market: str, stock_id: str, force_refresh: bool = False) -> Optional[dict]:
        summary = self.summary_item(market, stock_id)
        if not summary:
            return None

        lookup, lookup_error = None, None
        try:
            lookup = self._market_service.lookup(market, stock_id, force_refresh=force_refresh)
        except Exception as exc:
            lookup_error = str(exc)

        records = (
            self._db.query(StockData)
            .filter(
                StockData.user_id == self._user_id,
                StockData.stock_market == market,
                StockData.stock_id == stock_id,
            )
            .order_by(
                StockData.stock_transaction_date.is_(None).asc(),
                StockData.stock_transaction_date.desc(),
                StockData.stock_entry_time.desc(),
                StockData.stock_vid.desc(),
            )
            .all()
        )
        external_sections = self._market_service.external_sections(market, stock_id, force_refresh=force_refresh)
        queried_times = [
            value
            for value in [((lookup or {}).get("queried_at"))]
            + [section.get("queried_at") for section in external_sections]
            if value
        ]
        return {
            "summary": summary,
            "lookup": lookup,
            "lookup_error": lookup_error,
            "records": [stock_to_dict(item) for item in records],
            "external_sections": external_sections,
            "updated_at": max(queried_times) if queried_times else None,
        }

    def records(self, market: str, stock_id: str, page: int = 1, page_size: int = 5) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 5)
        q = self._db.query(StockData).filter(
            StockData.user_id == self._user_id,
            StockData.stock_market == market,
            StockData.stock_id == stock_id,
        )
        total = q.count()
        records = (
            q.order_by(
                StockData.stock_transaction_date.is_(None).asc(),
                StockData.stock_transaction_date.desc(),
                StockData.stock_entry_time.desc(),
                StockData.stock_vid.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [stock_to_dict(item) for item in records],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, math.ceil(total / page_size)) if page_size else 1,
        }

    def summary_item(
        self,
        market: str,
        stock_id: str,
        refresh_prices: bool = True,
        refresh_dividends: bool = False,
    ) -> Optional[dict]:
        row = (
            self._db.query(
                StockData.stock_market,
                StockData.stock_id,
                func.max(StockData.stock_name).label("stock_name"),
                func.sum(StockData.stock_amount).label("total_amount"),
                func.sum(
                    case(
                        (StockData.stock_average_price.isnot(None), StockData.stock_amount * StockData.stock_average_price),
                        else_=0,
                    )
                ).label("cost_total"),
                func.sum(
                    case(
                        (StockData.stock_average_price.isnot(None), StockData.stock_amount),
                        else_=0,
                    )
                ).label("cost_amount"),
            )
            .filter(
                StockData.user_id == self._user_id,
                StockData.stock_market == market,
                StockData.stock_id == stock_id,
            )
            .group_by(StockData.stock_market, StockData.stock_id)
            .first()
        )
        if not row:
            return None

        alias = self.latest_alias(row.stock_market, row.stock_id)
        if refresh_prices:
            info, lookup_error = self._market_service.try_lookup(row.stock_market, row.stock_id)
        else:
            info = self._market_service.cached_lookup(row.stock_market, row.stock_id, allow_stale=True)
            lookup_error = None
        current_price = (info or {}).get("current_price")
        price_cache_stale = bool((info or {}).get("cache_stale"))
        price_from_cache = bool((info or {}).get("from_cache"))
        price_refresh_needed = (not refresh_prices) and (price_cache_stale or current_price is None)
        total_amount = float(row.total_amount or 0)
        total_cost = round(float(row.cost_total or 0), 2)
        average_cost = None
        cost_amount = float(row.cost_amount or 0)
        if cost_amount:
            average_cost = round(float(row.cost_total or 0) / cost_amount, 4)
        total_value = round(total_amount * current_price, 2) if current_price is not None else None
        current_return_rate = None
        if total_value is not None and total_cost:
            current_return_rate = round((total_value - total_cost) / total_cost * 100, 1)
        if refresh_dividends:
            self._market_service.external_sections(row.stock_market, row.stock_id, force_refresh=False)
        dividend_selection = self._market_service.cached_dividend_selection(row.stock_market, row.stock_id)
        dividend_refresh_needed = (not refresh_dividends) and dividend_selection is None
        return {
            "stock_market": row.stock_market,
            "stock_id": row.stock_id,
            "stock_name": (info or {}).get("stock_name") or row.stock_name,
            "stock_alias": alias,
            "stock_amount": round(total_amount, 6),
            "current_price": current_price,
            "total_value": total_value,
            "total_cost": total_cost,
            "current_return_rate": current_return_rate,
            "stock_currency": currency_for_market(row.stock_market),
            "stock_average_price": average_cost,
            "lookup_error": lookup_error,
            "price_from_cache": price_from_cache,
            "price_cache_stale": price_cache_stale,
            "price_refresh_needed": price_refresh_needed,
            "stock_dividend_reference_year": (dividend_selection or {}).get("年份"),
            "stock_dividend_frequency": (dividend_selection or {}).get("派息次数"),
            "stock_dividend_per_share_last_year": (dividend_selection or {}).get("每股派息金额"),
            "stock_dividend_change_rate": (dividend_selection or {}).get("环比变化"),
            "stock_dividend_refresh_needed": dividend_refresh_needed,
        }

    def portfolio_summary(self, items: list[dict]) -> dict:
        if not items:
            return {"rows": [], "converted_total": None}

        by_currency: dict[str, list[dict]] = {}
        for item in items:
            currency = item.get("stock_currency") or currency_for_market(item.get("stock_market", "CN"))
            by_currency.setdefault(currency, []).append(item)

        rows = [
            _portfolio_metric_row(currency, currency_items)
            for currency, currency_items in sorted(by_currency.items())
        ]

        rates: dict[str, float] = {}
        rate_errors: dict[str, str] = {}
        for currency in by_currency:
            try:
                rates[currency] = self._market_service.cny_rate(currency)
            except Exception as exc:
                rates[currency] = 0
                rate_errors[currency] = str(exc)
        for row in rows:
            currency = row.get("currency")
            if currency in rates and not rate_errors.get(currency):
                row["exchange_rate_to_cny"] = round(rates[currency], 6)
            if currency in rate_errors:
                row["exchange_rate_error"] = rate_errors[currency]

        converted_items = [
            item
            for item in items
            if not rate_errors.get(item.get("stock_currency") or currency_for_market(item.get("stock_market", "CN")))
        ]
        converted_row = _portfolio_metric_row(
            "CNY",
            converted_items,
            rate=1.0,
            rate_error="；".join(f"{currency}: {error}" for currency, error in sorted(rate_errors.items())) or None,
        )
        if not rate_errors:
            converted_row = {
                **converted_row,
                "asset_total_value": None,
                "holding_total_cost": None,
                "principal_return_rate": None,
                "annual_dividend": None,
                "after_tax_dividend": None,
                "holding_dividend_rate": None,
            }
            converted_values = []
            for currency, currency_items in by_currency.items():
                rate = rates.get(currency, 1.0)
                converted_values.append(_portfolio_metric_row("CNY", currency_items, rate=rate))
            converted_row["asset_value_pending"] = any(row["asset_value_pending"] for row in converted_values)
            converted_row["dividend_pending"] = any(row["dividend_pending"] for row in converted_values)
            asset_value_missing = any(row["asset_total_value"] is None for row in converted_values)
            dividend_missing = any(row["annual_dividend"] is None for row in converted_values)
            converted_row["asset_total_value"] = None if converted_row["asset_value_pending"] or asset_value_missing else round(sum(row["asset_total_value"] or 0 for row in converted_values), 2)
            converted_row["holding_total_cost"] = round(sum(row["holding_total_cost"] or 0 for row in converted_values), 2)
            converted_row["annual_dividend"] = None if converted_row["dividend_pending"] or dividend_missing else round(sum(row["annual_dividend"] or 0 for row in converted_values), 2)
            converted_row["after_tax_dividend"] = None if converted_row["dividend_pending"] or dividend_missing else round(sum(row["after_tax_dividend"] or 0 for row in converted_values), 2)
            if converted_row["holding_total_cost"] and not converted_row["asset_value_pending"] and not asset_value_missing:
                converted_row["principal_return_rate"] = round(
                    (converted_row["asset_total_value"] - converted_row["holding_total_cost"]) / converted_row["holding_total_cost"] * 100,
                    1,
                )
            if converted_row["holding_total_cost"] and not converted_row["dividend_pending"] and not dividend_missing:
                converted_row["holding_dividend_rate"] = round(
                    converted_row["annual_dividend"] / converted_row["holding_total_cost"] * 100,
                    1,
                )
        converted_row["label"] = "CNY 汇总"
        converted_row["is_converted"] = True
        return {"rows": rows, "converted_total": converted_row}

    def latest_alias(self, market: str, stock_id: str) -> Optional[str]:
        row = (
            self._db.query(StockData.stock_alias)
            .filter(
                StockData.user_id == self._user_id,
                StockData.stock_market == market,
                StockData.stock_id == stock_id,
                StockData.stock_alias.isnot(None),
                StockData.stock_alias != "",
            )
            .order_by(StockData.updated_at.desc(), StockData.stock_vid.desc())
            .first()
        )
        return row[0] if row else None

    def _stock_by_vid(self, stock_vid: str) -> Optional[StockData]:
        return (
            self._db.query(StockData)
            .filter(StockData.user_id == self._user_id, StockData.stock_vid == stock_vid)
            .first()
        )

    def _generate_stock_vid(self) -> str:
        for _ in range(8):
            stock_vid = secrets.token_hex(8)
            exists = self._db.query(StockData.stock_vid).filter(StockData.stock_vid == stock_vid).first()
            if not exists:
                return stock_vid
        raise RuntimeError("生成股票记录 ID 失败")

    def _sync_stock_alias(self, market: str, stock_id: str, alias: str, now: datetime) -> None:
        (
            self._db.query(StockData)
            .filter(
                StockData.user_id == self._user_id,
                StockData.stock_market == market,
                StockData.stock_id == stock_id,
            )
            .update(
                {
                    "stock_alias": alias,
                    "updated_at": now,
                },
                synchronize_session=False,
            )
        )

    @staticmethod
    def _apply_stock_body(stock: StockData, body, lookup_info: Optional[dict], now: datetime) -> None:
        average_price = body.stock_average_price
        if average_price is None:
            current_price = (lookup_info or {}).get("current_price")
            if current_price is not None:
                average_price = float(current_price)
        stock.stock_market = body.stock_market
        stock.stock_id = body.stock_id
        stock.stock_name = body.stock_name or (lookup_info or {}).get("stock_name")
        stock.stock_alias = body.stock_alias
        stock.stock_amount = body.stock_amount
        stock.stock_average_price = average_price
        stock.stock_currency = currency_for_market(body.stock_market)
        stock.stock_remark = body.stock_remark
        stock.stock_transaction_date = datetime.combine(body.stock_transaction_date, datetime.min.time()) if body.stock_transaction_date else None
        stock.updated_at = now


def stock_to_dict(stock: StockData) -> dict:
    return {
        "stock_vid": stock.stock_vid,
        "stock_market": stock.stock_market,
        "stock_id": stock.stock_id,
        "stock_name": stock.stock_name,
        "stock_alias": stock.stock_alias,
        "stock_amount": stock.stock_amount,
        "stock_average_price": stock.stock_average_price,
        "stock_currency": stock.stock_currency,
        "stock_remark": stock.stock_remark,
        "stock_transaction_date": stock.stock_transaction_date.date().isoformat() if stock.stock_transaction_date else None,
        "stock_entry_time": stock.stock_entry_time.isoformat() if stock.stock_entry_time else None,
        "created_at": stock.created_at.isoformat() if stock.created_at else None,
        "updated_at": stock.updated_at.isoformat() if stock.updated_at else None,
    }


def _num(value) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _portfolio_metric_row(currency: str, items: list[dict], rate: float = 1.0, rate_error: Optional[str] = None) -> dict:
    asset_value_pending = any(item.get("price_refresh_needed") for item in items)
    dividend_pending = any(item.get("stock_dividend_refresh_needed") for item in items)
    asset_value_missing = any(_num(item.get("total_value")) is None for item in items)
    dividend_missing = any(_num(item.get("stock_dividend_per_share_last_year")) is None for item in items)
    total_value = sum((_num(item.get("total_value")) or 0) * rate for item in items)
    total_cost = sum((_num(item.get("total_cost")) or 0) * rate for item in items)
    annual_dividend = sum(
        ((_num(item.get("stock_dividend_per_share_last_year")) or 0) * (_num(item.get("stock_amount")) or 0) * rate)
        for item in items
    )
    after_tax_dividend = sum(
        (
            (_num(item.get("stock_dividend_per_share_last_year")) or 0)
            * (_num(item.get("stock_amount")) or 0)
            * (0.8 if item.get("stock_market") == "US" else 1.0)
            * rate
        )
        for item in items
    )
    principal_return_rate = None
    if total_cost and not asset_value_pending and not asset_value_missing:
        principal_return_rate = (total_value - total_cost) / total_cost * 100
    holding_dividend_rate = None
    if total_cost and not dividend_pending and not dividend_missing:
        holding_dividend_rate = annual_dividend / total_cost * 100
    return {
        "currency": currency,
        "asset_total_value": None if asset_value_pending or asset_value_missing or rate_error else round(total_value, 2),
        "holding_total_cost": None if rate_error else round(total_cost, 2),
        "principal_return_rate": None if principal_return_rate is None or rate_error else round(principal_return_rate, 1),
        "annual_dividend": None if dividend_pending or dividend_missing or rate_error else round(annual_dividend, 2),
        "after_tax_dividend": None if dividend_pending or dividend_missing or rate_error else round(after_tax_dividend, 2),
        "holding_dividend_rate": None if holding_dividend_rate is None or rate_error else round(holding_dividend_rate, 1),
        "asset_value_pending": asset_value_pending,
        "dividend_pending": dividend_pending,
        "exchange_rate_to_cny": round(rate, 6) if rate and not rate_error else None,
        "exchange_rate_error": rate_error,
    }
