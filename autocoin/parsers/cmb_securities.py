import csv
import io
from datetime import datetime

from autocoin.parsers.base import BillParser, ParsedTransaction


class CmbSecuritiesParser(BillParser):
    SOURCE_NAME = "招商证券"
    HEADER_SENTINEL = "成交日期"
    INCLUDED_BUSINESS_NAMES = {"产品红利发放", "股息入账"}

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        if not filename.lower().endswith(".xls"):
            return False
        return self.HEADER_SENTINEL in self._decode(file_bytes[:2048])

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        text = self._decode(file_bytes)
        reader = csv.reader(io.StringIO(text), delimiter="\t")
        rows = [
            [self._clean_cell(cell) for cell in row]
            for row in reader
            if any(str(cell).strip() for cell in row)
        ]

        header_idx = None
        for i, row in enumerate(rows):
            if self.HEADER_SENTINEL in row:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Could not find header row in CMB Securities file")

        header = rows[header_idx]
        results = []
        for raw_row in rows[header_idx + 1:]:
            row = {
                header[i]: raw_row[i]
                for i in range(min(len(header), len(raw_row)))
                if header[i]
            }

            if row.get("业务名称") not in self.INCLUDED_BUSINESS_NAMES:
                continue

            time_str = row.get("成交日期", "").strip()
            try:
                transaction_time = datetime.strptime(time_str, "%Y%m%d")
            except ValueError:
                continue

            order_id = row.get("流水号", "").strip()
            if not order_id:
                order_id = f"cmb_securities_{transaction_time.strftime('%Y%m%d')}_{row.get('证券代码', '')}_{row.get('发生金额', '')}"

            try:
                amount = abs(float(row.get("发生金额", "0").replace(",", "").strip() or 0))
            except ValueError:
                amount = 0.0

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
                    product=row.get("证券名称", "").strip(),
                    direction="income",
                    amount=amount,
                    payment_method=self.SOURCE_NAME,
                    status=row.get("业务名称", "").strip(),
                    remark=row.get("备注", "").strip(),
                )
            )

        return results

    def _decode(self, file_bytes: bytes) -> str:
        return file_bytes.decode("gbk", errors="replace")

    def _clean_cell(self, value) -> str:
        text = str(value or "").strip()
        if text.startswith('="') and text.endswith('"'):
            return text[2:-1].strip()
        return text.strip('"').strip()
