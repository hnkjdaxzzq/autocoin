import csv
import io
from datetime import datetime

from autocoin.parsers.base import BillParser, ParsedTransaction


class AlipayParser(BillParser):
    SOURCE_NAME = "alipay"
    DIRECTION_MAP = {"收入": "income", "支出": "expense", "不计收支": "neutral"}
    HEADER_SENTINEL = "交易时间"

    def can_parse(self, filename: str, file_bytes: bytes) -> bool:
        return filename.lower().endswith(".csv")

    def parse(self, file_bytes: bytes) -> list[ParsedTransaction]:
        # Alipay exports are GBK encoded
        text = file_bytes.decode("gbk", errors="replace")
        lines = text.splitlines()

        # Find the header row by scanning for the sentinel value
        data_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith(self.HEADER_SENTINEL):
                data_start = i
                break

        if data_start is None:
            raise ValueError("Could not find header row in Alipay CSV file")

        reader = csv.DictReader(
            io.StringIO("\n".join(lines[data_start:])),
            skipinitialspace=True,
        )

        results = []
        for row in reader:
            # Strip embedded whitespace/tabs from order IDs
            order_id = row.get("交易订单号", "").strip()
            if not order_id or order_id == "交易订单号":
                continue  # skip blank rows

            direction_raw = row.get("收/支", "").strip()
            direction = self.DIRECTION_MAP.get(direction_raw, "neutral")

            amount_str = row.get("金额", "0").strip()
            try:
                amount = float(amount_str)
            except ValueError:
                amount = 0.0

            time_str = row.get("交易时间", "").strip()
            try:
                transaction_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue  # skip rows with unparseable datetime

            category = row.get("交易分类", "").strip()

            results.append(
                ParsedTransaction(
                    source="alipay",
                    source_order_id=order_id,
                    merchant_order_id=row.get("商家订单号", "").strip(),
                    transaction_time=transaction_time,
                    transaction_type=category,
                    category=category,
                    counterparty=row.get("交易对方", "").strip(),
                    counterparty_account=row.get("对方账号", "").strip(),
                    product=row.get("商品说明", "").strip(),
                    direction=direction,
                    amount=amount,
                    payment_method=row.get("收/付款方式", "").strip(),
                    status=row.get("交易状态", "").strip(),
                    remark=row.get("备注", "").strip(),
                )
            )

        return results
