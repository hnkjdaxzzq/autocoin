from typing import Optional

from autocoin.repository.base import DataRepository


class StatsService:

    def __init__(self, repo: DataRepository):
        self._repo = repo

    def summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        source=None,
        exclude_broker_withholding_tax: bool = False,
    ) -> dict:
        return self._repo.get_summary_stats(
            start_date,
            end_date,
            source,
            exclude_broker_withholding_tax,
        )

    def monthly(
        self,
        year: int,
        source=None,
        exclude_broker_withholding_tax: bool = False,
    ) -> dict:
        months = self._repo.get_monthly_stats(year, source, exclude_broker_withholding_tax)
        return {"year": year, "months": months}

    def category(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "expense",
        source=None,
        exclude_broker_withholding_tax: bool = False,
    ) -> dict:
        items = self._repo.get_category_stats(
            start_date,
            end_date,
            direction,
            source,
            exclude_broker_withholding_tax,
        )
        total = sum(i["amount"] for i in items)
        return {"items": items, "total": round(total, 2)}

    def daily(self, year: int, month: int, source=None) -> dict:
        days = self._repo.get_daily_stats(year, month, source)
        return {"year": year, "month": month, "days": days}
