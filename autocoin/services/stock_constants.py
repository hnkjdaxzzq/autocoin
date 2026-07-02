DEFAULT_STOCK_MARKET = "CN"
DEFAULT_STOCK_CURRENCY = "CNY"
MARKET_CURRENCY = {"CN": "CNY", "US": "USD"}
SUPPORTED_STOCK_MARKETS = tuple(MARKET_CURRENCY.keys())
STOCK_MARKET_ERROR = "所属市场只能是 CN 或 US"


def normalize_stock_market(market: str) -> str:
    normalized = (market or DEFAULT_STOCK_MARKET).strip().upper()
    if normalized not in MARKET_CURRENCY:
        raise ValueError(STOCK_MARKET_ERROR)
    return normalized


def normalize_stock_id(stock_id: str) -> str:
    return (stock_id or "").strip().upper()


def currency_for_market(market: str) -> str:
    normalized = (market or DEFAULT_STOCK_MARKET).strip().upper()
    return MARKET_CURRENCY.get(normalized, DEFAULT_STOCK_CURRENCY)
