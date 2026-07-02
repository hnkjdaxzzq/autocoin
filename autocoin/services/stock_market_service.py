from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from autocoin.services.exchange_rate_service import ExchangeRateError, ExchangeRateService
from autocoin.services.stock_cache_service import STOCK_CACHE_TTL, StockCacheService
from autocoin.services.stock_constants import (
    MARKET_CURRENCY,
    currency_for_market,
    normalize_stock_id,
    normalize_stock_market,
)
from autocoin.services.stock_dividend_service import StockDividendService
from autocoin.services.stock_quote_service import StockQuoteError, StockQuoteService


THS_DIVIDEND_SOURCE = "akshare.stock_fhps_detail_ths"


class StockLookupError(Exception):
    pass


class StockMarketService:
    def __init__(self, db: Session):
        self._db = db
        self._cache = StockCacheService(db)
        self._dividend = StockDividendService()
        self._exchange_rate = ExchangeRateService(db, cache=self._cache)
        self._quote = StockQuoteService(self._to_json_safe)

    def lookup(self, market: str, stock_id: str, force_refresh: bool = False) -> dict:
        market = normalize_stock_market(market)
        stock_id = normalize_stock_id(stock_id)
        now = datetime.utcnow()
        if not force_refresh:
            cached_payload = self._cache.get_cached_query_payload(market, stock_id, "lookup", now=now)
            if cached_payload:
                cached_payload["from_cache"] = True
                return cached_payload

        info = self._fetch_remote(market, stock_id)
        payload = {
            "stock_market": market,
            "stock_id": stock_id,
            "stock_name": info.get("stock_name"),
            "current_price": info.get("current_price"),
            "stock_currency": currency_for_market(market),
            "raw_api_source": info.get("raw_api_source"),
            "raw_api_data": self._to_json_safe(info.get("raw_api_data")),
            "queried_at": now.isoformat(),
            "from_cache": False,
        }
        self._cache.set_query_cache(market, stock_id, "lookup", payload, now=now)
        self._cache.sync_legacy_lookup_cache(market, stock_id, payload, now=now)
        return payload

    def try_lookup(self, market: str, stock_id: str) -> tuple[Optional[dict], Optional[str]]:
        try:
            return self.lookup(market, stock_id), None
        except Exception as exc:
            return None, str(exc)

    def cached_lookup(self, market: str, stock_id: str, allow_stale: bool = False) -> Optional[dict]:
        market = normalize_stock_market(market)
        stock_id = normalize_stock_id(stock_id)
        cached = self._cache.get_query_cache(market, stock_id, "lookup")
        if not cached:
            return None
        now = datetime.utcnow()
        is_stale = not cached.queried_at or now - cached.queried_at > STOCK_CACHE_TTL
        if is_stale and not allow_stale:
            return None
        data = self._cache.loads_payload(cached.payload)
        if not isinstance(data, dict):
            return None
        data["from_cache"] = True
        data["cache_stale"] = is_stale
        return data

    def cny_rate(self, currency: str) -> float:
        try:
            return self._exchange_rate.cny_rate(currency)
        except ExchangeRateError as exc:
            raise StockLookupError(str(exc)) from exc

    def cleanup_expired_cache(self, now: Optional[datetime] = None) -> int:
        return self._cache.cleanup_expired_cache(now=now)

    def external_sections(self, market: str, stock_id: str, force_refresh: bool = False) -> list[dict]:
        market = normalize_stock_market(market)
        stock_id = normalize_stock_id(stock_id)
        if market == "CN":
            return self._cn_external_sections(stock_id, force_refresh=force_refresh)
        if market == "US":
            return self._us_external_sections(stock_id, force_refresh=force_refresh)
        raise StockLookupError("不支持的股票市场")

    def cached_dividend_selection(self, market: str, stock_id: str) -> Optional[dict]:
        market = normalize_stock_market(market)
        stock_id = normalize_stock_id(stock_id)
        if market == "CN":
            section = self._cache.get_cached_query_payload("CN", stock_id, f"external:{THS_DIVIDEND_SOURCE}")
            if not isinstance(section, dict) or section.get("status") != "ok":
                return None
            self._dividend.enrich_ths_dividend_section(section)
            rows = ((section.get("dividend_parse") or {}).get("yearly_summary_rows") or [])
            return self._dividend.select_dividend_summary_row(rows)
        if market == "US":
            section = self._cache.get_cached_query_payload("US", stock_id, "external:yfinance.Ticker.get_dividends")
            if not isinstance(section, dict) or section.get("status") != "ok":
                return None
            rows = self._dividend.us_yearly_dividend_summary(section.get("rows") or [])
            return self._dividend.select_dividend_summary_row(rows)
        return None

    def _cn_external_sections(self, stock_id: str, force_refresh: bool = False) -> list[dict]:
        try:
            import akshare as ak
        except ImportError as exc:
            error = f"AKShare 依赖未安装：{exc}"
            return [
                self._error_section("巨潮资讯历史分红", "akshare.stock_dividend_cninfo", error),
                self._error_section("新浪财经分红历史", "akshare.stock_history_dividend_detail", error),
                self._error_section("东方财富分红送配详情", "akshare.stock_fhps_detail_em", error),
                self._error_section("同花顺分红情况", "akshare.stock_fhps_detail_ths", error),
            ]

        return [
            self._section_from_call(
                "巨潮资讯历史分红",
                "akshare.stock_dividend_cninfo",
                stock_id,
                lambda: ak.stock_dividend_cninfo(symbol=stock_id),
                force_refresh=force_refresh,
            ),
            self._section_from_call(
                "新浪财经分红历史",
                "akshare.stock_history_dividend_detail",
                stock_id,
                lambda: ak.stock_history_dividend_detail(symbol=stock_id, indicator="分红"),
                force_refresh=force_refresh,
            ),
            self._section_from_call(
                "东方财富分红送配详情",
                "akshare.stock_fhps_detail_em",
                stock_id,
                lambda: ak.stock_fhps_detail_em(symbol=stock_id),
                force_refresh=force_refresh,
            ),
            self._section_from_call(
                "同花顺分红情况",
                THS_DIVIDEND_SOURCE,
                stock_id,
                lambda: ak.stock_fhps_detail_ths(symbol=stock_id),
                force_refresh=force_refresh,
            ),
        ]

    def _us_external_sections(self, stock_id: str, force_refresh: bool = False) -> list[dict]:
        try:
            import yfinance as yf
        except ImportError as exc:
            error = f"yfinance 依赖未安装：{exc}"
            return [
                self._error_section("Yahoo Finance 基础信息", "yfinance.Ticker.get_info", error),
                self._error_section("Yahoo Finance 历史股息", "yfinance.Ticker.get_dividends", error),
                self._error_section("Yahoo Finance 公司行为", "yfinance.Ticker.actions", error),
                self._error_section("Yahoo Finance 非零分红/拆股历史", "yfinance.Ticker.history(actions=True)", error),
            ]

        ticker = yf.Ticker(stock_id)
        return [
            self._section_from_call(
                "Yahoo Finance 基础信息",
                "yfinance.Ticker.get_info",
                stock_id,
                lambda: self._dict_to_rows(ticker.get_info() or {}),
                force_refresh=force_refresh,
            ),
            self._section_from_call(
                "Yahoo Finance 历史股息",
                "yfinance.Ticker.get_dividends",
                stock_id,
                lambda: self._series_to_rows(ticker.get_dividends(period="max"), "dividend"),
                force_refresh=force_refresh,
            ),
            self._section_from_call(
                "Yahoo Finance 公司行为",
                "yfinance.Ticker.actions",
                stock_id,
                lambda: ticker.actions,
                force_refresh=force_refresh,
            ),
            self._section_from_call(
                "Yahoo Finance 非零分红/拆股历史",
                "yfinance.Ticker.history(actions=True)",
                stock_id,
                lambda: self._nonzero_action_rows(ticker.history(period="max", actions=True)),
                force_refresh=force_refresh,
            ),
        ]

    def _fetch_remote(self, market: str, stock_id: str) -> dict:
        if market == "US":
            return self._fetch_us(stock_id)
        if market == "CN":
            return self._fetch_cn(stock_id)
        raise StockLookupError("不支持的股票市场")

    def _fetch_us(self, stock_id: str) -> dict:
        try:
            return self._quote.fetch_us(stock_id)
        except StockQuoteError as exc:
            raise StockLookupError(str(exc)) from exc

    def _fetch_cn(self, stock_id: str) -> dict:
        errors = []
        try:
            return self._fetch_cn_akshare(stock_id)
        except ImportError as exc:
            errors.append(f"AKShare 依赖未安装：{exc}")
        except Exception as exc:
            errors.append(f"AKShare 查询失败：{exc}")

        try:
            return self._fetch_cn_tencent(stock_id)
        except Exception as exc:
            errors.append(f"腾讯行情查询失败：{exc}")

        raise StockLookupError("；".join(errors) or "A 股行情查询失败")

    def _fetch_cn_akshare(self, stock_id: str) -> dict:
        try:
            return self._quote.fetch_cn_akshare(stock_id)
        except StockQuoteError as exc:
            raise StockLookupError(str(exc)) from exc

    def _fetch_cn_tencent(self, stock_id: str) -> dict:
        try:
            return self._quote.fetch_cn_tencent(stock_id)
        except StockQuoteError as exc:
            raise StockLookupError(str(exc)) from exc

    def _section_from_call(self, title: str, source: str, stock_id: str, fn, force_refresh: bool = False) -> dict:
        market = "US" if source.startswith("yfinance.") else "CN"
        query_key = f"external:{source}"
        cached_payload = None if force_refresh else self._cache.get_cached_query_payload(market, stock_id, query_key)
        if cached_payload:
            if source == THS_DIVIDEND_SOURCE:
                self._dividend.enrich_ths_dividend_section(cached_payload)
            cached_payload["from_cache"] = True
            return cached_payload
        try:
            now = datetime.utcnow()
            columns, rows = self._tabular_data(fn())
            section = {
                "title": title,
                "source": source,
                "status": "ok",
                "columns": columns,
                "rows": rows,
                "error": None,
                "from_cache": False,
                "queried_at": now.isoformat(),
            }
            if source == THS_DIVIDEND_SOURCE:
                self._dividend.enrich_ths_dividend_section(section)
            self._cache.set_query_cache(market, stock_id, query_key, section, now=now)
            return section
        except Exception as exc:
            now = datetime.utcnow()
            section = self._error_section(title, source, str(exc))
            section["queried_at"] = now.isoformat()
            self._cache.set_query_cache(market, stock_id, query_key, section, now=now)
            return section

    @staticmethod
    def _error_section(title: str, source: str, error: str) -> dict:
        return {
            "title": title,
            "source": source,
            "status": "error",
            "columns": [],
            "rows": [],
            "error": error,
            "from_cache": False,
            "queried_at": None,
        }

    @classmethod
    def _enrich_ths_dividend_section(cls, section: dict) -> dict:
        return StockDividendService.enrich_ths_dividend_section(section)

    @staticmethod
    def _parse_ths_dividend_row(row: dict) -> dict:
        return StockDividendService.parse_ths_dividend_row(row)

    @classmethod
    def _ths_yearly_dividend_summary(cls, rows: list[dict]) -> list[dict]:
        return StockDividendService.ths_yearly_dividend_summary(rows)

    @classmethod
    def _us_yearly_dividend_summary(cls, rows: list[dict]) -> list[dict]:
        return StockDividendService.us_yearly_dividend_summary(rows)

    @staticmethod
    def _select_dividend_summary_row(rows: list[dict]) -> Optional[dict]:
        return StockDividendService.select_dividend_summary_row(rows)

    @staticmethod
    def _year_from_report_period(value) -> Optional[int]:
        return StockDividendService.year_from_report_period(value)

    @staticmethod
    def _sortable_date(value) -> str:
        return StockDividendService.sortable_date(value)

    @staticmethod
    def _first_row_value(row: dict, names: list[str]):
        return StockDividendService.first_row_value(row, names)

    @classmethod
    def _tabular_data(cls, data) -> tuple[list[str], list[dict]]:
        if data is None:
            return [], []
        if isinstance(data, list):
            rows = cls._to_json_safe(data)
            if not rows:
                return [], []
            columns = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
            return columns, rows
        if isinstance(data, dict):
            rows = [cls._to_json_safe(data)]
            return list(rows[0].keys()), rows
        if hasattr(data, "to_frame") and not hasattr(data, "columns"):
            data = data.to_frame()
        if hasattr(data, "columns") and hasattr(data, "to_dict"):
            frame = cls._frame_with_index(data)
            columns = [str(col) for col in frame.columns]
            rows = cls._to_json_safe(frame.to_dict(orient="records"))
            return columns, rows
        return ["value"], [{"value": cls._to_json_safe(data)}]

    @staticmethod
    def _frame_with_index(frame):
        index = getattr(frame, "index", None)
        if index is not None and type(index).__name__ != "RangeIndex":
            frame = frame.reset_index()
            first_col = frame.columns[0]
            if str(first_col).lower() in ("index", "date", "datetime"):
                frame = frame.rename(columns={first_col: "date"})
        return frame

    @classmethod
    def _dict_to_rows(cls, data: dict) -> list[dict]:
        return [
            {"field": str(key), "value": cls._to_json_safe(value)}
            for key, value in sorted(data.items(), key=lambda item: str(item[0]))
        ]

    @classmethod
    def _series_to_rows(cls, series, value_name: str) -> list[dict]:
        rows = []
        for index, value in series.items():
            rows.append({
                "date": cls._to_json_safe(index),
                value_name: cls._to_json_safe(value),
            })
        return rows

    @classmethod
    def _nonzero_action_rows(cls, history):
        if history is None or getattr(history, "empty", False):
            return history
        action_cols = [
            col for col in history.columns
            if str(col) in ("Dividends", "Stock Splits", "Capital Gains")
        ]
        if not action_cols:
            return history.iloc[0:0]
        actions = history[action_cols]
        try:
            return actions[(actions != 0).any(axis=1)]
        except Exception:
            return actions

    @classmethod
    def _to_json_safe(cls, value):
        return StockCacheService.to_json_safe(value)
