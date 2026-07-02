import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from autocoin.models.stock_api_cache import StockApiCache
from autocoin.models.stock_query_cache import StockQueryCache


STOCK_CACHE_TTL = timedelta(hours=3)
MARKET_CURRENCY = {"CN": "CNY", "US": "USD"}
THS_DIVIDEND_SOURCE = "akshare.stock_fhps_detail_ths"


class StockLookupError(Exception):
    pass


def currency_for_market(market: str) -> str:
    return MARKET_CURRENCY.get(market, "CNY")


class StockMarketService:
    def __init__(self, db: Session):
        self._db = db

    def lookup(self, market: str, stock_id: str, force_refresh: bool = False) -> dict:
        market = market.upper()
        stock_id = stock_id.strip().upper()
        now = datetime.utcnow()
        if not force_refresh:
            cached_payload = self._get_cached_query_payload(market, stock_id, "lookup", now=now)
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
        self._set_query_cache(market, stock_id, "lookup", payload, now=now)
        self._sync_legacy_lookup_cache(market, stock_id, payload, now=now)
        return payload

    def try_lookup(self, market: str, stock_id: str) -> tuple[Optional[dict], Optional[str]]:
        try:
            return self.lookup(market, stock_id), None
        except Exception as exc:
            return None, str(exc)

    def cached_lookup(self, market: str, stock_id: str, allow_stale: bool = False) -> Optional[dict]:
        market = market.upper()
        stock_id = stock_id.strip().upper()
        cached = self._get_query_cache(market, stock_id, "lookup")
        if not cached:
            return None
        now = datetime.utcnow()
        is_stale = not cached.queried_at or now - cached.queried_at > STOCK_CACHE_TTL
        if is_stale and not allow_stale:
            return None
        data = self._loads_raw_api_data(cached.payload)
        if not isinstance(data, dict):
            return None
        data["from_cache"] = True
        data["cache_stale"] = is_stale
        return data

    def cleanup_expired_cache(self, now: Optional[datetime] = None) -> int:
        cutoff = (now or datetime.utcnow()) - STOCK_CACHE_TTL
        deleted = (
            self._db.query(StockApiCache)
            .filter(StockApiCache.queried_at < cutoff)
            .delete(synchronize_session=False)
        )
        deleted += (
            self._db.query(StockQueryCache)
            .filter(StockQueryCache.queried_at < cutoff)
            .delete(synchronize_session=False)
        )
        self._db.flush()
        return int(deleted or 0)

    def external_sections(self, market: str, stock_id: str, force_refresh: bool = False) -> list[dict]:
        market = market.upper()
        stock_id = stock_id.strip().upper()
        if market == "CN":
            return self._cn_external_sections(stock_id, force_refresh=force_refresh)
        if market == "US":
            return self._us_external_sections(stock_id, force_refresh=force_refresh)
        raise StockLookupError("不支持的股票市场")

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

    def _get_cache(self, market: str, stock_id: str) -> Optional[StockApiCache]:
        return (
            self._db.query(StockApiCache)
            .filter(
                StockApiCache.stock_market == market,
                StockApiCache.stock_id == stock_id,
            )
            .first()
        )

    def _get_query_cache(self, market: str, stock_id: str, query_key: str) -> Optional[StockQueryCache]:
        return (
            self._db.query(StockQueryCache)
            .filter(
                StockQueryCache.stock_market == market,
                StockQueryCache.stock_id == stock_id,
                StockQueryCache.query_key == query_key,
            )
            .first()
        )

    def _get_cached_query_payload(
        self,
        market: str,
        stock_id: str,
        query_key: str,
        now: Optional[datetime] = None,
    ) -> Optional[dict]:
        cache = self._get_query_cache(market, stock_id, query_key)
        now = now or datetime.utcnow()
        if not cache or not cache.queried_at or now - cache.queried_at > STOCK_CACHE_TTL:
            return None
        data = self._loads_raw_api_data(cache.payload)
        return data if isinstance(data, dict) else None

    def _set_query_cache(self, market: str, stock_id: str, query_key: str, payload: dict, now: Optional[datetime] = None) -> None:
        now = now or datetime.utcnow()
        cache = self._get_query_cache(market, stock_id, query_key)
        if not cache:
            cache = StockQueryCache(
                stock_market=market,
                stock_id=stock_id,
                query_key=query_key,
                created_at=now,
            )
            self._db.add(cache)
        cache.payload = self._dumps_raw_api_data(payload) or "{}"
        cache.queried_at = now
        cache.updated_at = now
        self._db.flush()

    def _sync_legacy_lookup_cache(self, market: str, stock_id: str, payload: dict, now: Optional[datetime] = None) -> None:
        now = now or datetime.utcnow()
        cache = self._get_cache(market, stock_id)
        if not cache:
            cache = StockApiCache(stock_market=market, stock_id=stock_id, created_at=now)
            self._db.add(cache)
        cache.stock_name = payload.get("stock_name") or cache.stock_name
        cache.current_price = payload.get("current_price")
        cache.stock_currency = payload.get("stock_currency") or currency_for_market(market)
        cache.raw_api_source = payload.get("raw_api_source")
        cache.raw_api_data = self._dumps_raw_api_data(payload.get("raw_api_data"))
        cache.queried_at = now
        cache.updated_at = now
        self._db.flush()

    def _fetch_remote(self, market: str, stock_id: str) -> dict:
        if market == "US":
            return self._fetch_us(stock_id)
        if market == "CN":
            return self._fetch_cn(stock_id)
        raise StockLookupError("不支持的股票市场")

    def _fetch_us(self, stock_id: str) -> dict:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise StockLookupError("yfinance 依赖未安装，暂时无法查询美股信息") from exc

        try:
            ticker = yf.Ticker(stock_id)
            info = ticker.get_info() or {}
            price = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("previousClose")
            )
            name = info.get("shortName") or info.get("longName") or stock_id
            raw_api_data = {"info": self._to_json_safe(info)}
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    raw_api_data["history_fallback"] = {
                        "columns": list(map(str, hist.columns)),
                        "last_row": self._to_json_safe(
                            {"Date": hist.index[-1], **hist.iloc[-1].to_dict()}
                        ),
                    }
        except Exception as exc:
            raise StockLookupError(f"美股行情查询失败：{exc}") from exc
        if price is None:
            raise StockLookupError("未查询到该美股的实时价格")
        return {
            "stock_name": name,
            "current_price": float(price),
            "raw_api_source": "yfinance.get_info",
            "raw_api_data": raw_api_data,
        }

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
        import akshare as ak

        code = stock_id.strip()
        data = ak.stock_zh_a_spot_em()
        if data is None or data.empty:
            raise StockLookupError("AKShare 未返回 A 股行情数据")

        code_col = "代码"
        name_col = "名称"
        price_col = "最新价"
        matched = data[data[code_col].astype(str) == code]
        if matched.empty:
            raise StockLookupError("AKShare 未查询到该 A 股代码")

        row = matched.iloc[0]
        price = row.get(price_col)
        if price is None or price == "-":
            raise StockLookupError("AKShare 未查询到该 A 股实时价格")
        return {
            "stock_name": str(row.get(name_col) or code),
            "current_price": float(price),
            "raw_api_source": "akshare.stock_zh_a_spot_em",
            "raw_api_data": self._to_json_safe(row.to_dict()),
        }

    def _fetch_cn_tencent(self, stock_id: str) -> dict:
        code = stock_id.strip()
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
        symbol = f"{prefix}{code}"
        url = f"https://qt.gtimg.cn/q={symbol}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=8) as response:
            text = response.read().decode("gbk", errors="ignore")
        if not text or "~" not in text:
            raise StockLookupError("未返回有效行情数据")
        payload = text.split('"', 2)[1] if '"' in text else text
        fields = payload.split("~")
        if len(fields) < 4:
            raise StockLookupError("行情数据格式不完整")
        name = fields[1] or code
        price = fields[3]
        if not price or price == "0.00":
            raise StockLookupError("未查询到该 A 股实时价格")
        return {
            "stock_name": name,
            "current_price": float(price),
            "raw_api_source": "tencent.qt.gtimg",
            "raw_api_data": {
                "symbol": symbol,
                "raw_text": text,
                "field_count": len(fields),
                "fields": self._to_json_safe(fields),
            },
        }

    def _section_from_call(self, title: str, source: str, stock_id: str, fn, force_refresh: bool = False) -> dict:
        market = "US" if source.startswith("yfinance.") else "CN"
        query_key = f"external:{source}"
        cached_payload = None if force_refresh else self._get_cached_query_payload(market, stock_id, query_key)
        if cached_payload:
            if source == THS_DIVIDEND_SOURCE:
                self._enrich_ths_dividend_section(cached_payload)
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
                self._enrich_ths_dividend_section(section)
            self._set_query_cache(market, stock_id, query_key, section, now=now)
            return section
        except Exception as exc:
            now = datetime.utcnow()
            section = self._error_section(title, source, str(exc))
            section["queried_at"] = now.isoformat()
            self._set_query_cache(market, stock_id, query_key, section, now=now)
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
        rows = section.get("rows") or []
        parsed_rows = [
            cls._parse_ths_dividend_row(row)
            for row in rows
            if isinstance(row, dict)
        ]
        parsed_rows.sort(
            key=lambda row: (
                cls._sortable_date(row.get("公告日期")),
                cls._sortable_date(row.get("报告期")),
            ),
            reverse=True,
        )
        section["dividend_parse"] = {
            "raw_columns": section.get("columns") or [],
            "raw_rows": rows,
            "yearly_summary_columns": ["年份", "派息次数", "每股派息金额", "环比变化"],
            "yearly_summary_rows": cls._ths_yearly_dividend_summary(parsed_rows),
            "per_share_columns": [
                "公告日期",
                "报告期",
                "除权除息日",
                "分红方案说明",
                "派息基准",
                "现金派息",
                "每股派息",
                "解析状态",
            ],
            "per_share_rows": parsed_rows,
        }
        return section

    @staticmethod
    def _parse_ths_dividend_row(row: dict) -> dict:
        scheme = (
            StockMarketService._first_row_value(row, ["分红方案说明", "分配方案", "方案", "送转分红"])
            or ""
        )
        raw_text = str(scheme or "")
        result = {
            "公告日期": StockMarketService._first_row_value(row, ["公告日期", "预案公告日", "董事会日期", "实施公告日"]),
            "报告期": StockMarketService._first_row_value(row, ["报告期", "分红年度", "年度", "年份"]),
            "除权除息日": StockMarketService._first_row_value(row, ["除权除息日", "除权除息日期", "除权日", "除息日"]),
            "分红方案说明": scheme,
            "原数据": row,
            "派息基准": None,
            "现金派息": None,
            "每股派息": None,
            "解析状态": "未识别",
        }
        if not raw_text or "派" not in raw_text:
            return result

        match = re.search(
            r"(?:每\s*)?(\d+(?:\.\d+)?)\s*(?:股)?\s*[^派]{0,16}派\s*(\d+(?:\.\d+)?)",
            raw_text,
        )
        if not match:
            return result

        base = float(match.group(1))
        cash = float(match.group(2))
        if base <= 0:
            return result
        per_share = cash / base
        result.update({
            "派息基准": f"每{base:g}股",
            "现金派息": round(cash, 6),
            "每股派息": round(per_share, 6),
            "解析状态": "已解析",
        })
        return result

    @classmethod
    def _ths_yearly_dividend_summary(cls, rows: list[dict]) -> list[dict]:
        yearly = {}
        yearly_counts = {}
        for row in rows:
            year = cls._year_from_report_period(row.get("报告期"))
            per_share = row.get("每股派息")
            if year is None or per_share is None:
                continue
            yearly[year] = yearly.get(year, 0) + float(per_share)
            yearly_counts[year] = yearly_counts.get(year, 0) + 1
        summary_by_year = {}
        for year, amount in sorted(yearly.items()):
            previous_amount = yearly.get(year - 1)
            change = None
            if previous_amount:
                change = (amount - previous_amount) / previous_amount * 100
            summary_by_year[year] = {
                "年份": year,
                "派息次数": yearly_counts.get(year, 0),
                "每股派息金额": round(amount, 6),
                "环比变化": round(change, 2) if change is not None else None,
            }
        return [summary_by_year[year] for year in sorted(summary_by_year.keys(), reverse=True)[:5]]

    @staticmethod
    def _year_from_report_period(value) -> Optional[int]:
        if value in (None, ""):
            return None
        match = re.search(r"(19|20)\d{2}", str(value))
        return int(match.group(0)) if match else None

    @staticmethod
    def _sortable_date(value) -> str:
        if value in (None, ""):
            return ""
        return str(value).strip()

    @staticmethod
    def _first_row_value(row: dict, names: list[str]):
        for name in names:
            value = row.get(name)
            if value not in (None, ""):
                return value
        normalized = {str(key).strip(): value for key, value in row.items()}
        for name in names:
            value = normalized.get(name)
            if value not in (None, ""):
                return value
        for key, value in normalized.items():
            if value in (None, ""):
                continue
            if any(name in key or key in name for name in names):
                return value
        return None

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

    @staticmethod
    def _cache_to_dict(cache: StockApiCache, from_cache: bool) -> dict:
        return {
            "stock_market": cache.stock_market,
            "stock_id": cache.stock_id,
            "stock_name": cache.stock_name,
            "current_price": cache.current_price,
            "stock_currency": cache.stock_currency,
            "raw_api_source": cache.raw_api_source,
            "raw_api_data": StockMarketService._loads_raw_api_data(cache.raw_api_data),
            "queried_at": cache.queried_at.isoformat() if cache.queried_at else None,
            "from_cache": from_cache,
        }

    @classmethod
    def _dumps_raw_api_data(cls, data) -> Optional[str]:
        if data is None:
            return None
        return json.dumps(cls._to_json_safe(data), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _loads_raw_api_data(data: Optional[str]):
        if not data:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data

    @classmethod
    def _to_json_safe(cls, value):
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): cls._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._to_json_safe(item) for item in value]
        if hasattr(value, "item"):
            try:
                return cls._to_json_safe(value.item())
            except Exception:
                pass
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)
