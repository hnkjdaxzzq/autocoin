import csv
import io
import json
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from autocoin.parsers.base import BillParser, ParsedTransaction


class IbkrParser(BillParser):
    SOURCE_NAME = "盈透IBKR"
    INCLUDED_SECTIONS = {"股息", "代扣税", "利息"}
    TARGET_CURRENCY = "CNY"

    def __init__(self, rate_fetcher=None):
        self._rate_fetcher = rate_fetcher or self._fetch_cny_rate
        self._rate_cache: dict[str, Decimal] = {}

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        if not filename.lower().endswith(".csv"):
            return False
        text = self._decode(file_bytes[:4096])
        return "Interactive Brokers" in text or "活动账单" in text

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        reader = csv.reader(io.StringIO(self._decode(file_bytes)))
        headers_by_section: dict[str, list[str]] = {}
        results = []

        for row_number, raw_row in enumerate(reader, start=1):
            if len(raw_row) < 2:
                continue

            section = raw_row[0].strip()
            row_type = raw_row[1].strip()
            if section not in self.INCLUDED_SECTIONS:
                continue

            if row_type == "Header":
                headers_by_section[section] = [cell.strip() for cell in raw_row[2:]]
                continue
            if row_type != "Data":
                continue

            header = headers_by_section.get(section)
            if not header:
                continue

            row = {
                header[i]: raw_row[i + 2].strip()
                for i in range(min(len(header), len(raw_row) - 2))
                if header[i]
            }

            currency = row.get("货币", "").strip()
            date_str = row.get("日期", "").strip()
            description = row.get("描述", "").strip()
            amount_raw = row.get("金额", "").strip().replace(",", "")
            if not currency or currency.startswith("总数") or not date_str or not amount_raw:
                continue

            try:
                transaction_time = datetime.strptime(date_str, "%Y-%m-%d")
                original_amount = Decimal(amount_raw)
            except (ValueError, InvalidOperation):
                continue

            direction = "income" if original_amount >= 0 else "expense"
            amount = self._convert_to_cny(abs(original_amount), currency)
            order_id = self._build_order_id(row_number, section, currency, date_str, description, amount_raw)

            results.append(
                ParsedTransaction(
                    source=self.SOURCE_NAME,
                    source_order_id=order_id,
                    merchant_order_id=order_id,
                    transaction_time=transaction_time,
                    transaction_type="股息收入",
                    category="股息收入",
                    counterparty=self.SOURCE_NAME,
                    counterparty_account="",
                    product=description,
                    direction=direction,
                    amount=float(amount),
                    payment_method=self.SOURCE_NAME,
                    status="",
                    remark=f"{section} {currency} {amount_raw}",
                )
            )

        return results

    def _decode(self, file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8-sig", errors="replace")

    def _build_order_id(
        self,
        row_number: int,
        section: str,
        currency: str,
        date_str: str,
        description: str,
        amount: str,
    ) -> str:
        seed = "|".join([str(row_number), section, currency, date_str, description, amount])
        guid = uuid.uuid5(uuid.NAMESPACE_URL, f"autocoin:ibkr:{seed}")
        return f"{date_str}_{guid}"

    def _convert_to_cny(self, amount: Decimal, currency: str) -> Decimal:
        normalized_currency = self._normalize_currency(currency)
        if normalized_currency == self.TARGET_CURRENCY:
            return amount

        rate = self._rate_cache.get(normalized_currency)
        if rate is None:
            rate = Decimal(str(self._rate_fetcher(normalized_currency)))
            self._rate_cache[normalized_currency] = rate
        return amount * rate

    def _normalize_currency(self, currency: str) -> str:
        upper = currency.strip().upper()
        return "CNY" if upper == "CNH" else upper

    def _fetch_cny_rate(self, currency: str) -> Decimal:
        params = urlencode({"base": currency, "symbols": self.TARGET_CURRENCY})
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
            return Decimal(str(payload["rates"][self.TARGET_CURRENCY]))
        except (HTTPError, URLError, KeyError, InvalidOperation, json.JSONDecodeError) as exc:
            raise ValueError(f"获取 {currency} 到 CNY 汇率失败: {exc}") from exc
