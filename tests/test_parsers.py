"""Tests for Alipay and WeChat parsers."""
import csv
import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from autocoin.parsers.alipay import AlipayParser
from autocoin.parsers.cmb_securities import CmbSecuritiesParser
from autocoin.parsers.hsbc_pulse import HsbcPulseParser
from autocoin.parsers.ibkr import IbkrParser
from autocoin.parsers.moomoo import MoomooParser
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


# ---------- CMB Securities ----------


def _make_cmb_securities_xls(rows: list[list[str]]) -> bytes:
    header = [
        "币种", "证券名称", "成交日期", "成交价格", "成交数量", "发生金额",
        "资金余额", "剩余数量", "合同编号", "流水号", "业务名称", "印花税",
        "佣金", "经手费", "证管费", "结算费", "过户费", "其他费用",
        "证券代码", "股东代码", "备注",
    ]

    def cell(value: str) -> str:
        return f'="{value}"'

    lines = ["\t".join(cell(value) for value in header)]
    lines.extend("\t".join(cell(value) for value in row) for row in rows)
    return ("\r\n".join(lines) + "\r\n").encode("gbk")


class TestCmbSecuritiesParser:
    def test_parse_dividend_rows_only(self):
        rows = [
            [
                "人民币", "天添利", "20260526", "1.0000", "0", "71.85",
                "72.85", "135195.08", "0", "2400962142", "产品红利发放",
                "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
                "880013", "980413128609", "",
            ],
            [
                "人民币", "工商银行", "20260512", "7.4800", "0", "844.50",
                "845.50", "5000", "0", "3200001562", "股息入账",
                "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00",
                "601398", "A682083458", "",
            ],
            [
                "人民币", "中国平安", "20260521", "54.5000", "500", "-27255.27",
                "1.00", "2700", "443753", "3200013111", "证券买入",
                "0.00", "3.52", "0.93", "0.55", "0.00", "0.27", "0.00",
                "601318", "A682083458", "",
            ],
        ]

        parser = CmbSecuritiesParser()
        result = parser.parse(_make_cmb_securities_xls(rows))

        assert len(result) == 2
        assert result[0].source == "招商证券"
        assert result[0].transaction_time == datetime(2026, 5, 26)
        assert result[0].product == "天添利"
        assert result[0].category == "股息收入"
        assert result[0].transaction_type == "股息收入"
        assert result[0].counterparty == "招商证券"
        assert result[0].payment_method == "招商证券"
        assert result[0].direction == "income"
        assert result[0].amount == 71.85
        assert result[0].source_order_id == "2400962142"
        assert result[0].merchant_order_id == "2400962142"
        assert result[1].product == "工商银行"

    def test_can_parse(self):
        parser = CmbSecuritiesParser()
        assert parser.can_parse("zszq.xls", _make_cmb_securities_xls([]))
        assert not parser.can_parse("zszq.xlsx", _make_cmb_securities_xls([]))


# ---------- IBKR ----------


def _make_ibkr_csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Statement", "Data", "BrokerName", "Interactive Brokers LLC"])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


class TestIbkrParser:
    def test_parse_income_expense_and_convert_to_cny(self):
        parser = IbkrParser(rate_fetcher=lambda currency: {"USD": 7.2, "HKD": 0.92}[currency])
        result = parser.parse(_make_ibkr_csv([
            ["股息", "Header", "货币", "日期", "描述", "金额"],
            ["股息", "Data", "USD", "2026-01-09", "MO 现金红利", "53"],
            ["股息", "Data", "总数", "", "", "53"],
            ["代扣税", "Header", "货币", "日期", "描述", "金额", "代码"],
            ["代扣税", "Data", "USD", "2026-01-09", "MO US 税收", "-15.9", ""],
            ["利息", "Header", "货币", "日期", "描述", "金额"],
            ["利息", "Data", "HKD", "2026-05-05", "HKD 贷方利息", "29.58"],
        ]))

        assert len(result) == 3
        assert result[0].source == "盈透IBKR"
        assert result[0].transaction_time == datetime(2026, 1, 9)
        assert result[0].product == "MO 现金红利"
        assert result[0].category == "股息收入"
        assert result[0].transaction_type == "股息收入"
        assert result[0].counterparty == "盈透IBKR"
        assert result[0].payment_method == "盈透IBKR"
        assert result[0].direction == "income"
        assert result[0].amount == 381.6
        assert result[0].remark == "股息 USD 53"
        assert result[1].direction == "expense"
        assert result[1].amount == 114.48
        assert result[1].remark == "代扣税 USD -15.9"
        assert result[2].amount == pytest.approx(27.2136)
        assert result[2].remark == "利息 HKD 29.58"

    def test_cnh_maps_to_cny_without_rate_fetch(self):
        parser = IbkrParser(rate_fetcher=lambda currency: pytest.fail(f"unexpected rate fetch: {currency}"))
        result = parser.parse(_make_ibkr_csv([
            ["利息", "Header", "货币", "日期", "描述", "金额"],
            ["利息", "Data", "CNH", "2026-05-05", "CNH 贷方利息", "12.34"],
        ]))

        assert len(result) == 1
        assert result[0].amount == 12.34
        assert result[0].direction == "income"

    def test_order_id_is_stable_for_same_row(self):
        content = _make_ibkr_csv([
            ["股息", "Header", "货币", "日期", "描述", "金额"],
            ["股息", "Data", "USD", "2026-01-09", "MO 现金红利", "53"],
        ])
        parser = IbkrParser(rate_fetcher=lambda currency: 7.2)

        first = parser.parse(content)[0]
        second = parser.parse(content)[0]

        assert first.source_order_id == second.source_order_id
        assert first.source_order_id.startswith("2026-01-09_")

    def test_can_parse(self):
        parser = IbkrParser(rate_fetcher=lambda currency: 7.2)
        assert parser.can_parse("ibkr.csv", _make_ibkr_csv([]))
        assert not parser.can_parse("ibkr.xlsx", _make_ibkr_csv([]))


# ---------- MOOMOO ----------


def _make_moomoo_text() -> str:
    return """
現金變動

  USD                                                    日期/時間                 類型          金額           備註

  期初現金                                      143,090.92
  期末現金                                      125,550.69
  期末已交收現金                                   125,550.69
  期末未交收現金                                        0.00                                                   J P MORGAN EXCHANGE TRADED
                                                         2026/05/06 15:20:29   現金分紅        +223.81      FD EQUITY PREMIUM(JEPI) dividend,
                                                                                                        USD 0.44761 per share
                                                                                                        NRA withholding tax - J P MORGAN
                                                                                                        EXCHANGE TRADED FD EQUITY
                                                         2026/05/06 15:20:29   非美國居民預扣稅    -22.38
                                                                                                        PREMIUM(JEPI) dividend, USD
                                                                                                        0.44761 per share
                                                         2026/05/27 13:17:51   出金          -100.00      ACH Withdrawal - EWB
                                                                                                        INTEREST FROM CASH SWEEP (31
                                                         2026/05/29 22:29:53   Cash Plus   +368.20
                                                                                                        days)

                                                                               USD 總計      -17,540.23

  CNH                                                    日期/時間                 類型          金額           備註
  期初現金                                           0.00
  期末現金                                           0.00
  期末已交收現金                                        0.00
  期末未交收現金                                        0.00
                                                         2026/05/30 10:00:00   現金分紅        +12.34      CNH dividend
                                                                               CNH 總計      12.34

Cash Sweep總覽
"""


class TestMoomooParser:
    def test_parse_cash_change_rows_and_convert_to_cny(self):
        parser = MoomooParser(
            rate_fetcher=lambda currency: {"USD": 7.2}[currency],
            text_extractor=lambda _: _make_moomoo_text(),
        )
        result = parser.parse(b"%PDF")

        assert len(result) == 4
        assert result[0].source == "MOOMOO"
        assert result[0].transaction_time == datetime(2026, 5, 6, 15, 20, 29)
        assert result[0].product == "現金分紅 J P MORGAN EXCHANGE TRADED FD EQUITY PREMIUM(JEPI) dividend, USD 0.44761 per share"
        assert result[0].category == "股息收入"
        assert result[0].transaction_type == "股息收入"
        assert result[0].counterparty == "MOOMOO"
        assert result[0].payment_method == "MOOMOO"
        assert result[0].direction == "income"
        assert result[0].amount == pytest.approx(1611.432)
        assert result[0].remark == "現金分紅 +223.81 USD"
        assert result[1].direction == "expense"
        assert result[1].amount == pytest.approx(161.136)
        assert result[1].remark == "非美國居民預扣稅 -22.38 USD"
        assert result[2].product == "Cash Plus INTEREST FROM CASH SWEEP (31 days)"
        assert result[3].amount == 12.34
        assert result[3].remark == "現金分紅 +12.34 CNH"

    def test_order_id_is_stable_for_same_pdf_text(self):
        parser = MoomooParser(rate_fetcher=lambda currency: 7.2, text_extractor=lambda _: _make_moomoo_text())

        first = parser.parse(b"%PDF")[0]
        second = parser.parse(b"%PDF")[0]

        assert first.source_order_id == second.source_order_id
        assert first.source_order_id.startswith("2026/05/06 15:20:29_")

    def test_can_parse(self):
        parser = MoomooParser(rate_fetcher=lambda currency: 7.2, text_extractor=lambda _: "")
        assert parser.can_parse("moomoo.pdf", b"%PDF-1.4")
        assert not parser.can_parse("moomoo.csv", b"%PDF-1.4")


# ---------- HSBC PULSE ----------


def _make_hsbc_pulse_text() -> str:
    return """
Statement Date
05 JUN 2026

Post date Trans date                                Description of transaction                       Amount   (CNY)

 27APR     24APR       MEITUAN                    CHN                     CN                                   13.99CR
                       APPLE PAY-MOBILE:7045
 27APR     25APR       DINGBINGHUA ICE CREAM      CHN                     CN                                    9.80
                       UNIONPAY QR
 19MAY     19MAY       IFS PAYMENT - THANK YOU                                                                392.86CR

                            Note: "CR" means Credit transaction / balance
"""


class TestHsbcPulseParser:
    def test_parse_transactions_and_refunds(self):
        parser = HsbcPulseParser(text_extractor=lambda _: _make_hsbc_pulse_text())
        result = parser.parse(b"%PDF")

        assert len(result) == 3
        assert result[0].source == "汇丰PULSE"
        assert result[0].transaction_time == datetime(2026, 4, 24)
        assert result[0].product == "MEITUAN CHN CN APPLE PAY-MOBILE:7045 退款"
        assert result[0].category == "PULSE交易"
        assert result[0].transaction_type == "PULSE交易"
        assert result[0].counterparty == "PULSE"
        assert result[0].payment_method == "Pulse双币卡"
        assert result[0].direction == "income"
        assert result[0].amount == 13.99
        assert result[0].remark == "记账日期 2026-04-27 退款"
        assert result[1].direction == "expense"
        assert result[1].amount == 9.8
        assert result[1].product == "DINGBINGHUA ICE CREAM CHN CN UNIONPAY QR"
        assert result[1].remark == "记账日期 2026-04-27"
        assert result[2].product == "IFS PAYMENT - THANK YOU 退款"

    def test_previous_year_for_dates_after_statement_month(self):
        parser = HsbcPulseParser(text_extractor=lambda _: """
Statement Date
05 JAN 2026
Post date Trans date Description of transaction Amount (CNY)
 02JAN     31DEC       MERCHANT                  CN                     CN                                   10.00
""")
        result = parser.parse(b"%PDF")

        assert len(result) == 1
        assert result[0].transaction_time == datetime(2025, 12, 31)
        assert result[0].remark == "记账日期 2026-01-02"

    def test_can_parse(self):
        parser = HsbcPulseParser(text_extractor=lambda _: "")
        assert parser.can_parse("pulse.pdf", b"%PDF-1.7")
        assert not parser.can_parse("pulse.csv", b"%PDF-1.7")
