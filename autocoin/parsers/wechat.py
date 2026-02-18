from datetime import datetime
from io import BytesIO

import openpyxl

from autocoin.parsers.base import BillParser, ParsedTransaction


class WeChatParser(BillParser):
    SOURCE_NAME = "wechat"
    DIRECTION_MAP = {"收入": "income", "支出": "expense", "/": "neutral"}
    HEADER_CELL_VALUE = "交易时间"

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        return filename.lower().endswith(".xlsx")

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))

        # Find the header row by scanning for "交易时间" in the first cell
        header_idx = None
        for i, row in enumerate(rows):
            if row and str(row[0]).strip() == self.HEADER_CELL_VALUE:
                header_idx = i
                break

        if header_idx is None:
            raise ValueError("Could not find header row in WeChat XLSX file")

        header = [str(c).strip() if c is not None else "" for c in rows[header_idx]]

        results = []
        for raw_row in rows[header_idx + 1:]:
            if not raw_row or not raw_row[0]:
                continue

            row = {
                header[i]: str(c).strip() if c is not None else ""
                for i, c in enumerate(raw_row)
                if i < len(header)
            }

            time_str = row.get("交易时间", "").strip()
            if not time_str:
                continue

            try:
                transaction_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

            # Strip ¥ prefix from amount
            amount_str = row.get("金额(元)", "0").lstrip("¥").strip()
            try:
                amount = float(amount_str)
            except ValueError:
                amount = 0.0

            direction_raw = row.get("收/支", "").strip()
            direction = self.DIRECTION_MAP.get(direction_raw, "neutral")

            order_id = row.get("交易单号", "").strip()
            # Generate synthetic ID for rows with '/' as order ID to avoid unique constraint issues
            if not order_id or order_id == "/":
                order_id = f"wechat_synth_{transaction_time.strftime('%Y%m%d%H%M%S')}_{amount}"

            tx_type = row.get("交易类型", "").strip()

            results.append(
                ParsedTransaction(
                    source="wechat",
                    source_order_id=order_id,
                    merchant_order_id=row.get("商户单号", "").strip(),
                    transaction_time=transaction_time,
                    transaction_type=tx_type,
                    category=tx_type,
                    counterparty=row.get("交易对方", "").strip(),
                    counterparty_account="",
                    product=row.get("商品", "").strip(),
                    direction=direction,
                    amount=amount,
                    payment_method=row.get("支付方式", "").strip(),
                    status=row.get("当前状态", "").strip(),
                    remark=row.get("备注", "").strip(),
                )
            )

        return results
