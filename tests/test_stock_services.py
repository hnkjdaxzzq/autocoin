from datetime import datetime, timedelta

import pytest

from autocoin.database import SessionLocal, init_db
from autocoin.models.stock_api_cache import StockApiCache
from autocoin.models.stock_data import StockData
from autocoin.models.stock_query_cache import StockQueryCache
from autocoin.models.user import User
from autocoin.schemas.stock_management import StockCreate
from autocoin.services.exchange_rate_service import ExchangeRateService
from autocoin.services.stock_cache_service import STOCK_CACHE_TTL, StockCacheService
from autocoin.services.stock_dividend_service import StockDividendService
from autocoin.services.stock_market_service import StockMarketService
from autocoin.services.stock_portfolio_service import StockPortfolioService
from autocoin.services.stock_quote_service import StockQuoteError, StockQuoteService


@pytest.fixture()
def db():
    init_db()
    session = SessionLocal()
    _clear_stock_service_tables(session)
    try:
        yield session
    finally:
        session.rollback()
        _clear_stock_service_tables(session)
        session.close()


def _clear_stock_service_tables(session):
    for model in (StockData, StockApiCache, StockQueryCache, User):
        session.query(model).delete()
    session.commit()


def test_stock_cache_service_writes_lookup_legacy_and_cleans_expired(db):
    cache = StockCacheService(db)
    now = datetime.utcnow()
    payload = {
        "stock_name": "浦发银行",
        "current_price": 12.3,
        "stock_currency": "CNY",
        "raw_api_source": "unit-test",
        "raw_api_data": {"nested": {"ok": True}},
    }

    cache.set_query_cache("CN", "600000", "lookup", payload, now=now)
    cache.sync_legacy_lookup_cache("CN", "600000", payload, now=now)

    assert cache.get_cached_query_payload("CN", "600000", "lookup", now=now) == payload
    legacy = cache.get_legacy_lookup_cache("CN", "600000")
    assert legacy.stock_name == "浦发银行"
    assert legacy.current_price == 12.3
    assert legacy.stock_currency == "CNY"

    expired_at = now - STOCK_CACHE_TTL - timedelta(seconds=1)
    fresh_at = now - timedelta(minutes=1)
    db.add(
        StockQueryCache(
            stock_market="CN",
            stock_id="000001",
            query_key="external:ths_bonus",
            payload="{}",
            queried_at=expired_at,
            created_at=expired_at,
            updated_at=expired_at,
        )
    )
    db.add(
        StockApiCache(
            stock_market="US",
            stock_id="JEPI",
            stock_name="JEPI",
            current_price=55.0,
            stock_currency="USD",
            queried_at=fresh_at,
            created_at=fresh_at,
            updated_at=fresh_at,
        )
    )
    db.commit()

    assert cache.cleanup_expired_cache(now=now) == 1
    assert db.query(StockQueryCache).filter_by(stock_id="000001").first() is None
    assert db.query(StockApiCache).filter_by(stock_id="JEPI").first() is not None


def test_stock_create_schema_normalizes_market_code_and_blank_text():
    body = StockCreate(
        stock_market="us",
        stock_id=" jepi ",
        stock_name=" ",
        stock_alias="  dividend income ",
        stock_amount=1,
        stock_remark=" ",
    )

    assert body.stock_market == "US"
    assert body.stock_id == "JEPI"
    assert body.stock_name is None
    assert body.stock_alias == "dividend income"
    assert body.stock_remark is None


def test_stock_dividend_service_parses_yearly_summary_and_selection():
    section = {
        "columns": ["公告日期", "报告期", "分红方案说明"],
        "rows": [
            {"公告日期": "2026-04-01", "报告期": "2025-12-31", "分红方案说明": "每10股派5元"},
            {"公告日期": "2025-04-01", "报告期": "2024-12-31", "分红方案说明": "10股派4元"},
            {"公告日期": "2025-03-01", "报告期": "2024-06-30", "分红方案说明": "每10股派1元"},
        ],
    }

    enriched = StockDividendService.enrich_ths_dividend_section(section)
    parsed_rows = enriched["dividend_parse"]["per_share_rows"]
    yearly_rows = enriched["dividend_parse"]["yearly_summary_rows"]

    assert parsed_rows[0]["每股派息"] == 0.5
    assert yearly_rows[0]["年份"] == 2025
    assert yearly_rows[0]["每股派息金额"] == 0.5
    assert yearly_rows[1]["年份"] == 2024
    assert yearly_rows[1]["派息次数"] == 2
    assert yearly_rows[1]["每股派息金额"] == 0.5
    assert StockDividendService.select_dividend_summary_row(yearly_rows)["年份"] == 2024

    us_summary = StockDividendService.us_yearly_dividend_summary(
        [
            {"date": "2025-01-01", "dividend": 0.4},
            {"date": "2025-04-01", "dividend": "0.6"},
            {"date": "2024-01-01", "dividend": 0.5},
        ]
    )
    assert us_summary[0]["年份"] == 2025
    assert us_summary[0]["每股派息金额"] == 1.0
    assert us_summary[0]["派息次数"] == 2


def test_exchange_rate_service_uses_direct_rate_and_query_cache(monkeypatch, db):
    calls = []

    def fake_fetch(currency):
        calls.append(currency)
        return 7.2

    monkeypatch.setattr(ExchangeRateService, "_fetch_cny_rate", staticmethod(fake_fetch))
    service = ExchangeRateService(db)

    assert service.cny_rate("CNY") == 1.0
    assert service.cny_rate("cnh") == 1.0
    assert calls == []

    assert service.cny_rate("usd") == 7.2
    assert service.cny_rate("USD") == 7.2
    assert calls == ["USD"]
    cached = StockCacheService(db).get_cached_query_payload("FX", "USD", "rate:CNY")
    assert cached == {"currency": "USD", "target": "CNY", "rate": 7.2}


def test_stock_quote_service_fetch_cn_falls_back_to_tencent(monkeypatch):
    quote = StockQuoteService(lambda value: value)

    def fail_akshare(stock_id):
        raise RuntimeError(f"AKShare failed for {stock_id}")

    monkeypatch.setattr(quote, "fetch_cn_akshare", fail_akshare)
    monkeypatch.setattr(
        quote,
        "fetch_cn_tencent",
        lambda stock_id: {
            "stock_name": "浦发银行",
            "current_price": 12.3,
            "raw_api_source": "tencent.qt.gtimg",
            "raw_api_data": {"stock_id": stock_id},
        },
    )

    assert quote.fetch_cn("600000")["raw_api_source"] == "tencent.qt.gtimg"
    with pytest.raises(StockQuoteError, match="不支持的股票市场"):
        quote.fetch_remote("HK", "0005")


def test_stock_market_lookup_uses_query_cache_and_syncs_legacy(monkeypatch, db):
    service = StockMarketService(db)
    calls = []

    def fake_fetch(market, stock_id):
        calls.append((market, stock_id))
        return {
            "stock_name": "JEPI",
            "current_price": 55.0,
            "raw_api_source": "unit-test",
            "raw_api_data": {"ok": True},
        }

    monkeypatch.setattr(service, "_fetch_remote", fake_fetch)

    first = service.lookup("US", "JEPI")
    second = service.lookup("US", "JEPI")

    assert calls == [("US", "JEPI")]
    assert first["from_cache"] is False
    assert second["from_cache"] is True
    assert second["stock_currency"] == "USD"
    assert StockCacheService(db).get_legacy_lookup_cache("US", "JEPI").stock_currency == "USD"


def test_stock_portfolio_service_summary_groups_currency_and_converts_to_cny(db):
    user = User(username="stock-service-user", password_hash="test")
    db.add(user)
    db.flush()
    now = datetime.utcnow()
    db.add_all(
        [
            StockData(
                stock_vid="cn00000000000001",
                user_id=user.id,
                stock_market="CN",
                stock_id="600000",
                stock_name="浦发银行",
                stock_amount=10,
                stock_average_price=10,
                stock_currency="CNY",
                stock_entry_time=now,
                created_at=now,
                updated_at=now,
            ),
            StockData(
                stock_vid="us00000000000001",
                user_id=user.id,
                stock_market="US",
                stock_id="JEPI",
                stock_name="JEPI",
                stock_amount=2,
                stock_average_price=50,
                stock_currency="USD",
                stock_entry_time=now,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db.commit()

    service = StockPortfolioService(db, user.id, market_service=FakeMarketService())
    result = service.summary(refresh_prices=False, refresh_dividends=False)

    assert [item["stock_id"] for item in result["items"]] == ["600000", "JEPI"]
    rows_by_currency = {row["currency"]: row for row in result["portfolio_summary"]["rows"]}
    assert rows_by_currency["CNY"]["asset_total_value"] == 120.0
    assert rows_by_currency["USD"]["asset_total_value"] == 110.0
    assert rows_by_currency["USD"]["exchange_rate_to_cny"] == 7.2
    converted = result["portfolio_summary"]["converted_total"]
    assert converted["asset_total_value"] == 912.0
    assert converted["holding_total_cost"] == 820.0
    assert converted["annual_dividend"] == pytest.approx(19.4)
    assert converted["after_tax_dividend"] == pytest.approx(16.52)
    assert converted["principal_return_rate"] == pytest.approx(11.2)


class FakeMarketService:
    def cached_lookup(self, market, stock_id, allow_stale=False):
        payloads = {
            "600000": {"stock_name": "浦发银行", "current_price": 12.0, "from_cache": True},
            "JEPI": {"stock_name": "JEPI", "current_price": 55.0, "from_cache": True},
        }
        return payloads[stock_id]

    def try_lookup(self, market, stock_id):
        return self.cached_lookup(market, stock_id), None

    def cached_dividend_selection(self, market, stock_id):
        return {
            "600000": {"年份": 2025, "派息次数": 1, "每股派息金额": 0.5, "环比变化": None},
            "JEPI": {"年份": 2025, "派息次数": 12, "每股派息金额": 1.0, "环比变化": None},
        }[stock_id]

    def external_sections(self, market, stock_id, force_refresh=False):
        return []

    def cny_rate(self, currency):
        return {"CNY": 1.0, "USD": 7.2}[currency]
