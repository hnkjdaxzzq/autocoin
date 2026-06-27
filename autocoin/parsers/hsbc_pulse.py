import json
import re
import subprocess
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from autocoin.parsers.base import BillParser, ParsedTransaction


class HsbcPulseParser(BillParser):
    SOURCE_NAME = "汇丰PULSE"
    TRANSACTION_PATTERN = re.compile(
        r"^\s*(\d{2}[A-Z]{3})\s+(\d{2}[A-Z]{3})\s+(.+?)\s+([0-9][\d,]*\.\d{2}(?:CR)?)\s*$"
    )
    MONTHS = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }

    def __init__(self, text_extractor=None):
        self._text_extractor = text_extractor or self._extract_text

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        return filename.lower().endswith(".pdf") and file_bytes.startswith(b"%PDF")

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        text = self._text_extractor(file_bytes)
        statement_date = self._statement_date(text)
        rows = self._parse_rows(text)
        return [tx for tx in (self._row_to_transaction(row, statement_date) for row in rows) if tx is not None]

    def _parse_rows(self, text: str) -> list[dict]:
        rows = []
        current = None
        in_table = False

        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue

            if "Post date" in stripped and "Trans date" in stripped and "Description of transaction" in stripped and "Amount" in stripped:
                if current:
                    rows.append(current)
                    current = None
                in_table = True
                continue

            if not in_table:
                continue

            if stripped.startswith("Note:") or "REWARDCASH" in stripped or "TRANSACTION SUMMARY" in stripped:
                if current:
                    rows.append(current)
                    current = None
                in_table = False
                continue

            match = self.TRANSACTION_PATTERN.match(line)
            if match:
                if current:
                    rows.append(current)
                current = {
                    "line_number": line_number,
                    "post_date": match.group(1),
                    "trans_date": match.group(2),
                    "description": self._clean_description(match.group(3)),
                    "amount": match.group(4).replace(",", ""),
                }
                continue

            if current and self._looks_like_description_continuation(stripped):
                current["description"] = self._clean_description(f"{current['description']} {stripped}")

        if current:
            rows.append(current)
        return rows

    def _row_to_transaction(self, row: dict, statement_date: datetime) -> Optional[ParsedTransaction]:
        try:
            transaction_time = self._parse_statement_date_token(row["trans_date"], statement_date)
            post_time = self._parse_statement_date_token(row["post_date"], statement_date)
            is_refund = row["amount"].endswith("CR")
            amount = Decimal(row["amount"].removesuffix("CR"))
        except (ValueError, InvalidOperation):
            return None

        product = row["description"]
        remark = f"记账日期 {post_time.strftime('%Y-%m-%d')}"
        if is_refund:
            product = f"{product} 退款"
            remark = f"{remark} 退款"

        order_id = self._build_order_id(row)
        return ParsedTransaction(
            source=self.SOURCE_NAME,
            source_order_id=order_id,
            merchant_order_id=order_id,
            transaction_time=transaction_time,
            transaction_type="PULSE交易",
            category="PULSE交易",
            counterparty="PULSE",
            counterparty_account="",
            product=product,
            direction="income" if is_refund else "expense",
            amount=float(amount),
            payment_method="Pulse双币卡",
            status="",
            remark=remark,
        )

    def _statement_date(self, text: str) -> datetime:
        match = re.search(r"\b(\d{2})\s+([A-Z]{3})\s+(\d{4})\b", text)
        if not match:
            raise ValueError("Could not find statement date in HSBC PULSE PDF")
        return datetime(int(match.group(3)), self.MONTHS[match.group(2)], int(match.group(1)))

    def _parse_statement_date_token(self, value: str, statement_date: datetime) -> datetime:
        day = int(value[:2])
        month = self.MONTHS[value[2:5]]
        year = statement_date.year - 1 if month > statement_date.month else statement_date.year
        return datetime(year, month, day)

    def _build_order_id(self, row: dict) -> str:
        seed = json.dumps(row, ensure_ascii=False, sort_keys=True)
        guid = uuid.uuid5(uuid.NAMESPACE_URL, f"autocoin:hsbc-pulse:{seed}")
        return f"{row['trans_date']}_{guid}"

    def _clean_description(self, description: str) -> str:
        return re.sub(r"\s+", " ", description).strip()

    def _looks_like_description_continuation(self, line: str) -> bool:
        if any(token in line for token in ("PREVIOUS BALANCE", "STATEMENT BALANCE", "REWARDCASH", "SUMMARY", "Note:")):
            return False
        if any(token in line for token in ("REWARDS", "FEE/CHARGE", "FINANCE CHARGE", "BALANCE TYPE", "PURCHASES", "CREDIT/PAYMENT")):
            return False
        if "Account number" in line or "Page " in line:
            return False
        return bool(re.match(r"^[A-Z][A-Z0-9 /:-]+$", line))

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
            raise ValueError("解析汇丰 PULSE PDF 需要安装 pdftotext") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"解析汇丰 PULSE PDF 失败: {detail or exc}") from exc
        return result.stdout.decode("utf-8", errors="replace")
