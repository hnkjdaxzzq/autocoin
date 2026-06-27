import json
import re
import subprocess
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from autocoin.parsers.base import BillParser, ParsedTransaction


class MoomooParser(BillParser):
    SOURCE_NAME = "MOOMOO"
    TARGET_CURRENCY = "CNY"
    EXCLUDED_TYPES = {"入金", "出金", "資金調撥"}
    CASH_MARKERS = {"期初現金", "期末現金", "期末已交收現金", "期末未交收現金"}

    def __init__(self, rate_fetcher=None, text_extractor=None):
        self._rate_fetcher = rate_fetcher or self._fetch_cny_rate
        self._text_extractor = text_extractor or self._extract_text
        self._rate_cache: dict[str, Decimal] = {}

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        return filename.lower().endswith(".pdf") and file_bytes.startswith(b"%PDF")

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        return self._parse_text(self._text_extractor(file_bytes))

    def _parse_text(self, text: str) -> list[ParsedTransaction]:
        rows = []
        current_currency = ""
        current = None
        pending_remark = ""
        in_cash_section = False
        seen_cash_markers = set()
        col_positions = None

        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped == "現金變動":
                in_cash_section = True
                seen_cash_markers = set()
                current_currency = ""
                current = None
                pending_remark = ""
                col_positions = None
                continue
            if not in_cash_section:
                continue
            if stripped.startswith("Cash Sweep總覽"):
                if current:
                    rows.append(current)
                break

            seen_cash_markers.update(marker for marker in self.CASH_MARKERS if marker in stripped)

            currency_match = re.match(r"^(USD|HKD|CNH)\s+日期/時間\s+類型\s+金額\s+備註", stripped)
            if currency_match:
                if current:
                    rows.append(current)
                    current = None
                pending_remark = ""
                current_currency = currency_match.group(1)
                col_positions = {
                    "date": line.index("日期/時間"),
                    "type": line.index("類型"),
                    "amount": line.index("金額"),
                    "remark": line.index("備註"),
                }
                continue

            if not current_currency or not col_positions:
                continue

            if re.search(rf"{current_currency}\s+總計", stripped):
                if current:
                    rows.append(current)
                    current = None
                pending_remark = ""
                continue

            fields = self._split_cash_line(line, col_positions)
            if re.match(r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}$", fields["date"]):
                if current:
                    rows.append(current)
                remark = " ".join(part for part in (pending_remark, fields["remark"]) if part)
                current = {
                    "line_number": line_number,
                    "currency": current_currency,
                    "date": fields["date"],
                    "type": fields["type"],
                    "amount": fields["amount"].replace(",", ""),
                    "remark": remark,
                }
                pending_remark = ""
                continue

            remark = fields["remark"]
            if not remark or not self._looks_like_remark_continuation(remark):
                continue
            if current and self._starts_next_remark(current, remark):
                rows.append(current)
                current = None
                pending_remark = remark
            elif current:
                current["remark"] = " ".join(part for part in (current["remark"], remark) if part)
            else:
                pending_remark = " ".join(part for part in (pending_remark, remark) if part)

        if current:
            rows.append(current)

        return [tx for tx in (self._row_to_transaction(row) for row in rows) if tx is not None]

    def _split_cash_line(self, line: str, col_positions: dict) -> dict:
        date_start = col_positions["date"]
        type_start = col_positions["type"]
        amount_start = col_positions["amount"]
        remark_start = col_positions["remark"]
        return {
            "date": line[date_start:type_start].strip(),
            "type": line[type_start:amount_start].strip(),
            "amount": line[amount_start:remark_start].strip(),
            "remark": line[remark_start:].strip(),
        }

    def _row_to_transaction(self, row: dict) -> Optional[ParsedTransaction]:
        tx_type = row["type"]
        if tx_type in self.EXCLUDED_TYPES:
            return None

        try:
            transaction_time = datetime.strptime(row["date"], "%Y/%m/%d %H:%M:%S")
            original_amount = Decimal(row["amount"])
        except (ValueError, InvalidOperation):
            return None

        currency = row["currency"]
        direction = "income" if original_amount >= 0 else "expense"
        amount = self._convert_to_cny(abs(original_amount), currency)
        product = " ".join(part for part in (tx_type, row.get("remark", "")) if part)
        order_id = self._build_order_id(row)

        return ParsedTransaction(
            source=self.SOURCE_NAME,
            source_order_id=order_id,
            merchant_order_id=order_id,
            transaction_time=transaction_time,
            transaction_type="股息收入",
            category="股息收入",
            counterparty=self.SOURCE_NAME,
            counterparty_account="",
            product=product,
            direction=direction,
            amount=float(amount),
            payment_method=self.SOURCE_NAME,
            status="",
            remark=f"{tx_type} {row['amount']} {currency}",
        )

    def _looks_like_remark_continuation(self, line: str) -> bool:
        if any(marker in line for marker in self.CASH_MARKERS):
            return False
        if "總計" in line:
            return False
        return not re.match(r"^-", line)

    def _starts_next_remark(self, current: dict, remark: str) -> bool:
        if current["type"] in self.EXCLUDED_TYPES:
            return True
        if remark.startswith(("NRA withholding tax", "INTEREST FROM CASH SWEEP")):
            return True
        if current["type"] == "非美國居民預扣稅":
            return not remark.startswith(("PREMIUM", "0.", "TRUST", "dividend"))
        return False

    def _build_order_id(self, row: dict) -> str:
        seed = "|".join([
            str(row["line_number"]),
            row["currency"],
            row["date"],
            row["type"],
            row["amount"],
            row.get("remark", ""),
        ])
        guid = uuid.uuid5(uuid.NAMESPACE_URL, f"autocoin:moomoo:{seed}")
        return f"{row['date']}_{guid}"

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

    def _extract_text(self, file_bytes: bytes) -> str:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", "-", "-"],
                input=file_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except FileNotFoundError as exc:
            raise ValueError("解析 MOOMOO PDF 需要安装 pdftotext") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"解析 MOOMOO PDF 失败: {detail or exc}") from exc
        return result.stdout.decode("utf-8", errors="replace")

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
