import json
import math
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from autocoin.models.stock_api_cache import StockApiCache
from autocoin.models.stock_query_cache import StockQueryCache


STOCK_CACHE_TTL = timedelta(hours=3)


class StockCacheService:
    def __init__(self, db: Session):
        self._db = db

    def get_query_cache(self, market: str, stock_id: str, query_key: str) -> Optional[StockQueryCache]:
        return (
            self._db.query(StockQueryCache)
            .filter(
                StockQueryCache.stock_market == market,
                StockQueryCache.stock_id == stock_id,
                StockQueryCache.query_key == query_key,
            )
            .first()
        )

    def get_cached_query_payload(
        self,
        market: str,
        stock_id: str,
        query_key: str,
        now: Optional[datetime] = None,
    ) -> Optional[dict]:
        cache = self.get_query_cache(market, stock_id, query_key)
        now = now or datetime.utcnow()
        if not cache or not cache.queried_at or now - cache.queried_at > STOCK_CACHE_TTL:
            return None
        data = self.loads_payload(cache.payload)
        return data if isinstance(data, dict) else None

    def set_query_cache(
        self,
        market: str,
        stock_id: str,
        query_key: str,
        payload: dict,
        now: Optional[datetime] = None,
    ) -> None:
        now = now or datetime.utcnow()
        cache = self.get_query_cache(market, stock_id, query_key)
        if not cache:
            cache = StockQueryCache(
                stock_market=market,
                stock_id=stock_id,
                query_key=query_key,
                created_at=now,
            )
            self._db.add(cache)
        cache.payload = self.dumps_payload(payload) or "{}"
        cache.queried_at = now
        cache.updated_at = now
        self._db.flush()

    def sync_legacy_lookup_cache(self, market: str, stock_id: str, payload: dict, now: Optional[datetime] = None) -> None:
        now = now or datetime.utcnow()
        cache = self.get_legacy_lookup_cache(market, stock_id)
        if not cache:
            cache = StockApiCache(stock_market=market, stock_id=stock_id, created_at=now)
            self._db.add(cache)
        cache.stock_name = payload.get("stock_name") or cache.stock_name
        cache.current_price = payload.get("current_price")
        cache.stock_currency = payload.get("stock_currency") or "CNY"
        cache.raw_api_source = payload.get("raw_api_source")
        cache.raw_api_data = self.dumps_payload(payload.get("raw_api_data"))
        cache.queried_at = now
        cache.updated_at = now
        self._db.flush()

    def get_legacy_lookup_cache(self, market: str, stock_id: str) -> Optional[StockApiCache]:
        return (
            self._db.query(StockApiCache)
            .filter(
                StockApiCache.stock_market == market,
                StockApiCache.stock_id == stock_id,
            )
            .first()
        )

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

    @classmethod
    def dumps_payload(cls, data) -> Optional[str]:
        if data is None:
            return None
        return json.dumps(cls.to_json_safe(data), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def loads_payload(data: Optional[str]):
        if not data:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data

    @classmethod
    def to_json_safe(cls, value):
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): cls.to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls.to_json_safe(item) for item in value]
        if hasattr(value, "item"):
            try:
                return cls.to_json_safe(value.item())
            except Exception:
                pass
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)
