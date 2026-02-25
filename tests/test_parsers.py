"""Tests for Alipay and WeChat parsers."""
import csv
import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from autocoin.parsers.alipay import AlipayParser
from autocoin.parsers.wechat import WeChatParser


# ---------- Alipay ----------


def _make_alipay_csv(rows: list[list[str]], header_prefix: str = "") -> bytes:
    """Build a minimal Alipay CSV from rows.  header_prefix is optional leading junk."""
    buf = io.StringIO()
    if header_prefix:
        buf.write(header_prefix + "\n")
    writer = csv.writer(buf)
    writer.writerow([
        "交易时间", "交易分类", "交易对方", "对方账号", "商品说明",
        "收/支", "金额", "收/付款方式", "交易状态", "交易订单号",
        "商家订单号", "备注",
    ])
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("gbk")


class TestAlipayParser:
    def test_basic_parse(self):
        rows = [
            [
                "2025-01-15 12:30:00", "餐饮美食", "美团", "mt@example.com",
                "外卖订单", "支出", "25.80", "花呗", "交易成功",
                "2025011512300001", "M001", "",
            ],
            [
                "2025-01-16 09:00:00", "转账", "张三", "zhangsan",
                "转账", "收入", "100.00", "余额宝", "交易成功",
                "2025011609000001", "", "",
            ],
        ]
        parser = AlipayParser()
        result = parser.parse(_make_alipay_csv(rows))
        assert len(result) == 2
        assert result[0].source == "alipay"
        assert result[0].direction == "expense"
        assert result[0].amount == 25.80
        assert result[0].category == "餐饮美食"
        assert result[0].counterparty == "美团"
        assert result[1].direction == "income"
        assert result[1].amount == 100.00

    def test_skip_invalid_rows(self):
        rows = [
            [
                "invalid-time", "分类", "对方", "", "商品",
                "支出", "10.00", "现金", "成功",
                "ORDER001", "", "",
            ],
        ]
        parser = AlipayParser()
        result = parser.parse(_make_alipay_csv(rows))
        assert len(result) == 0  # invalid time → skipped

    def test_neutral_direction(self):
        rows = [
            [
                "2025-01-15 12:30:00", "", "对方", "", "商品",
                "不计收支", "50.00", "余额", "成功",
                "ORDER002", "", "",
            ],
        ]
        parser = AlipayParser()
        result = parser.parse(_make_alipay_csv(rows))
        assert len(result) == 1
        assert result[0].direction == "neutral"

    def test_with_header_prefix(self):
        rows = [
            [
                "2025-01-15 12:30:00", "交通出行", "滴滴", "",
                "快车", "支出", "15.00", "微信", "成功",
                "ORDER003", "", "",
            ],
        ]
        csv_bytes = _make_alipay_csv(rows, header_prefix="支付宝交易记录明细\n用户信息\n下载日期:2025-01-20")
        parser = AlipayParser()
        result = parser.parse(csv_bytes)
        assert len(result) == 1
        assert result[0].counterparty == "滴滴"

    def test_can_parse(self):
        parser = AlipayParser()
        assert parser.can_parse("test.csv", b"")
        assert not parser.can_parse("test.xlsx", b"")


# ---------- WeChat ----------


def _make_wechat_xlsx(rows: list[list], prefix_rows: int = 0) -> bytes:
    """Build a minimal WeChat XLSX."""
    wb = Workbook()
    ws = wb.active
    # Optional leading rows
    for _ in range(prefix_rows):
        ws.append(["Some WeChat metadata"])
    # Header
    ws.append([
        "交易时间", "交易类型", "交易对方", "商品", "收/支",
        "金额(元)", "支付方式", "当前状态", "交易单号", "商户单号", "备注",
    ])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestWeChatParser:
    def test_basic_parse(self):
        rows = [
            [
                "2025-01-15 12:30:00", "商户消费", "肯德基", "套餐",
                "支出", "¥35.00", "零钱", "支付成功", "TX001", "M001", "",
            ],
            [
                "2025-01-16 14:00:00", "转账", "李四", "转账",
                "收入", "¥200.00", "零钱", "已存入零钱", "TX002", "/", "",
            ],
        ]
        parser = WeChatParser()
        result = parser.parse(_make_wechat_xlsx(rows))
        assert len(result) == 2
        assert result[0].source == "wechat"
        assert result[0].direction == "expense"
        assert result[0].amount == 35.00
        assert result[0].counterparty == "肯德基"
        assert result[1].direction == "income"
        assert result[1].amount == 200.00

    def test_neutral_direction(self):
        rows = [
            [
                "2025-01-15 12:30:00", "微信红包", "群红包", "",
                "/", "¥1.00", "零钱", "已存入零钱", "/", "/", "",
            ],
        ]
        parser = WeChatParser()
        result = parser.parse(_make_wechat_xlsx(rows))
        assert len(result) == 1
        assert result[0].direction == "neutral"

    def test_with_prefix_rows(self):
        rows = [
            [
                "2025-01-15 12:30:00", "商户消费", "便利店", "饮料",
                "支出", "¥5.00", "零钱", "成功", "TX003", "", "",
            ],
        ]
        parser = WeChatParser()
        result = parser.parse(_make_wechat_xlsx(rows, prefix_rows=3))
        assert len(result) == 1
        assert result[0].amount == 5.00

    def test_can_parse(self):
        parser = WeChatParser()
        assert parser.can_parse("test.xlsx", b"")
        assert not parser.can_parse("test.csv", b"")
