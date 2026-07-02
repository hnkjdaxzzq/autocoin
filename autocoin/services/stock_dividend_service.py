import re
from typing import Optional


class StockDividendService:
    @classmethod
    def enrich_ths_dividend_section(cls, section: dict) -> dict:
        rows = section.get("rows") or []
        parsed_rows = [
            cls.parse_ths_dividend_row(row)
            for row in rows
            if isinstance(row, dict)
        ]
        parsed_rows.sort(
            key=lambda row: (
                cls.sortable_date(row.get("公告日期")),
                cls.sortable_date(row.get("报告期")),
            ),
            reverse=True,
        )
        section["dividend_parse"] = {
            "raw_columns": section.get("columns") or [],
            "raw_rows": rows,
            "yearly_summary_columns": ["年份", "派息次数", "每股派息金额", "环比变化"],
            "yearly_summary_rows": cls.ths_yearly_dividend_summary(parsed_rows),
            "per_share_columns": [
                "公告日期",
                "报告期",
                "除权除息日",
                "分红方案说明",
                "派息基准",
                "现金派息",
                "每股派息",
                "解析状态",
            ],
            "per_share_rows": parsed_rows,
        }
        return section

    @staticmethod
    def parse_ths_dividend_row(row: dict) -> dict:
        scheme = (
            StockDividendService.first_row_value(row, ["分红方案说明", "分配方案", "方案", "送转分红"])
            or ""
        )
        raw_text = str(scheme or "")
        result = {
            "公告日期": StockDividendService.first_row_value(row, ["公告日期", "预案公告日", "董事会日期", "实施公告日"]),
            "报告期": StockDividendService.first_row_value(row, ["报告期", "分红年度", "年度", "年份"]),
            "除权除息日": StockDividendService.first_row_value(row, ["除权除息日", "除权除息日期", "除权日", "除息日"]),
            "分红方案说明": scheme,
            "原数据": row,
            "派息基准": None,
            "现金派息": None,
            "每股派息": None,
            "解析状态": "未识别",
        }
        if not raw_text or "派" not in raw_text:
            return result

        match = re.search(
            r"(?:每\s*)?(\d+(?:\.\d+)?)\s*(?:股)?\s*[^派]{0,16}派\s*(\d+(?:\.\d+)?)",
            raw_text,
        )
        if not match:
            return result

        base = float(match.group(1))
        cash = float(match.group(2))
        if base <= 0:
            return result
        per_share = cash / base
        result.update({
            "派息基准": f"每{base:g}股",
            "现金派息": round(cash, 6),
            "每股派息": round(per_share, 6),
            "解析状态": "已解析",
        })
        return result

    @classmethod
    def ths_yearly_dividend_summary(cls, rows: list[dict]) -> list[dict]:
        yearly = {}
        yearly_counts = {}
        for row in rows:
            year = cls.year_from_report_period(row.get("报告期"))
            per_share = row.get("每股派息")
            if year is None or per_share is None:
                continue
            yearly[year] = yearly.get(year, 0) + float(per_share)
            yearly_counts[year] = yearly_counts.get(year, 0) + 1
        summary_by_year = {}
        for year, amount in sorted(yearly.items()):
            previous_amount = yearly.get(year - 1)
            change = None
            if previous_amount:
                change = (amount - previous_amount) / previous_amount * 100
            summary_by_year[year] = {
                "年份": year,
                "派息次数": yearly_counts.get(year, 0),
                "每股派息金额": round(amount, 6),
                "环比变化": round(change, 2) if change is not None else None,
            }
        return [summary_by_year[year] for year in sorted(summary_by_year.keys(), reverse=True)[:5]]

    @classmethod
    def us_yearly_dividend_summary(cls, rows: list[dict]) -> list[dict]:
        yearly = {}
        yearly_counts = {}
        for row in rows:
            year = cls.year_from_report_period(row.get("date"))
            dividend = row.get("dividend")
            if year is None or dividend is None:
                continue
            try:
                amount = float(dividend)
            except (TypeError, ValueError):
                continue
            yearly[year] = yearly.get(year, 0) + amount
            yearly_counts[year] = yearly_counts.get(year, 0) + 1
        summary_by_year = {}
        for year, amount in sorted(yearly.items()):
            previous_amount = yearly.get(year - 1)
            change = None
            if previous_amount:
                change = (amount - previous_amount) / previous_amount * 100
            summary_by_year[year] = {
                "年份": year,
                "派息次数": yearly_counts.get(year, 0),
                "每股派息金额": round(amount, 6),
                "环比变化": round(change, 2) if change is not None else None,
            }
        return [summary_by_year[year] for year in sorted(summary_by_year.keys(), reverse=True)[:5]]

    @staticmethod
    def select_dividend_summary_row(rows: list[dict]) -> Optional[dict]:
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]
        latest = rows[0]
        previous = rows[1]
        latest_count = latest.get("派息次数") or 0
        previous_count = previous.get("派息次数") or 0
        if latest_count >= previous_count:
            return latest
        return previous

    @staticmethod
    def year_from_report_period(value) -> Optional[int]:
        if value in (None, ""):
            return None
        match = re.search(r"(19|20)\d{2}", str(value))
        return int(match.group(0)) if match else None

    @staticmethod
    def sortable_date(value) -> str:
        if value in (None, ""):
            return ""
        return str(value).strip()

    @staticmethod
    def first_row_value(row: dict, names: list[str]):
        for name in names:
            value = row.get(name)
            if value not in (None, ""):
                return value
        normalized = {str(key).strip(): value for key, value in row.items()}
        for name in names:
            value = normalized.get(name)
            if value not in (None, ""):
                return value
        for key, value in normalized.items():
            if value in (None, ""):
                continue
            if any(name in key or key in name for name in names):
                return value
        return None
