import json
from datetime import datetime
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from autocoin.services.stock_cache_service import StockCacheService


class ExchangeRateError(Exception):
    pass


class ExchangeRateService:
    def __init__(self, db: Session, cache: Optional[StockCacheService] = None):
        self._db = db
        self._cache = cache or StockCacheService(db)

    def cny_rate(self, currency: str) -> float:
        normalized = (currency or "CNY").strip().upper()
        if normalized in ("CNY", "CNH"):
            return 1.0
        now = datetime.utcnow()
        cached = self._cache.get_cached_query_payload("FX", normalized, "rate:CNY", now=now)
        if cached and cached.get("rate") is not None:
            return float(cached["rate"])

        rate = self._fetch_cny_rate(normalized)
        self._cache.set_query_cache(
            "FX",
            normalized,
            "rate:CNY",
            {"currency": normalized, "target": "CNY", "rate": rate},
            now=now,
        )
        return rate

    @staticmethod
    def _fetch_cny_rate(currency: str) -> float:
        params = urlencode({"base": currency, "symbols": "CNY"})
        url = f"https://api.frankfurter.dev/v1/latest?{params}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "AutoCoin/0.1 (+https://github.com/autocoin)",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return float(payload["rates"]["CNY"])
        except (HTTPError, URLError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExchangeRateError(f"获取 {currency} 到 CNY 汇率失败: {exc}") from exc
