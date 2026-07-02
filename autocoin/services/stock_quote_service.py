from urllib.request import Request, urlopen


class StockQuoteError(Exception):
    pass


class StockQuoteService:
    def __init__(self, json_safe):
        self._json_safe = json_safe

    def fetch_remote(self, market: str, stock_id: str) -> dict:
        if market == "US":
            return self.fetch_us(stock_id)
        if market == "CN":
            return self.fetch_cn(stock_id)
        raise StockQuoteError("不支持的股票市场")

    def fetch_us(self, stock_id: str) -> dict:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise StockQuoteError("yfinance 依赖未安装，暂时无法查询美股信息") from exc

        try:
            ticker = yf.Ticker(stock_id)
            info = ticker.get_info() or {}
            price = (
                info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("previousClose")
            )
            name = info.get("shortName") or info.get("longName") or stock_id
            raw_api_data = {"info": self._json_safe(info)}
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    raw_api_data["history_fallback"] = {
                        "columns": list(map(str, hist.columns)),
                        "last_row": self._json_safe(
                            {"Date": hist.index[-1], **hist.iloc[-1].to_dict()}
                        ),
                    }
        except Exception as exc:
            raise StockQuoteError(f"美股行情查询失败：{exc}") from exc
        if price is None:
            raise StockQuoteError("未查询到该美股的实时价格")
        return {
            "stock_name": name,
            "current_price": float(price),
            "raw_api_source": "yfinance.get_info",
            "raw_api_data": raw_api_data,
        }

    def fetch_cn(self, stock_id: str) -> dict:
        errors = []
        try:
            return self.fetch_cn_akshare(stock_id)
        except ImportError as exc:
            errors.append(f"AKShare 依赖未安装：{exc}")
        except Exception as exc:
            errors.append(f"AKShare 查询失败：{exc}")

        try:
            return self.fetch_cn_tencent(stock_id)
        except Exception as exc:
            errors.append(f"腾讯行情查询失败：{exc}")

        raise StockQuoteError("；".join(errors) or "A 股行情查询失败")

    def fetch_cn_akshare(self, stock_id: str) -> dict:
        import akshare as ak

        code = stock_id.strip()
        data = ak.stock_zh_a_spot_em()
        if data is None or data.empty:
            raise StockQuoteError("AKShare 未返回 A 股行情数据")

        code_col = "代码"
        name_col = "名称"
        price_col = "最新价"
        matched = data[data[code_col].astype(str) == code]
        if matched.empty:
            raise StockQuoteError("AKShare 未查询到该 A 股代码")

        row = matched.iloc[0]
        price = row.get(price_col)
        if price is None or price == "-":
            raise StockQuoteError("AKShare 未查询到该 A 股实时价格")
        return {
            "stock_name": str(row.get(name_col) or code),
            "current_price": float(price),
            "raw_api_source": "akshare.stock_zh_a_spot_em",
            "raw_api_data": self._json_safe(row.to_dict()),
        }

    def fetch_cn_tencent(self, stock_id: str) -> dict:
        code = stock_id.strip()
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
        symbol = f"{prefix}{code}"
        url = f"https://qt.gtimg.cn/q={symbol}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=8) as response:
            text = response.read().decode("gbk", errors="ignore")
        if not text or "~" not in text:
            raise StockQuoteError("未返回有效行情数据")
        payload = text.split('"', 2)[1] if '"' in text else text
        fields = payload.split("~")
        if len(fields) < 4:
            raise StockQuoteError("行情数据格式不完整")
        name = fields[1] or code
        price = fields[3]
        if not price or price == "0.00":
            raise StockQuoteError("未查询到该 A 股实时价格")
        return {
            "stock_name": name,
            "current_price": float(price),
            "raw_api_source": "tencent.qt.gtimg",
            "raw_api_data": {
                "symbol": symbol,
                "raw_text": text,
                "field_count": len(fields),
                "fields": self._json_safe(fields),
            },
        }
