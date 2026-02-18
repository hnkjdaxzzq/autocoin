from typing import Optional

from autocoin.repository.base import DataRepository


class StatsService:

    def __init__(self, repo: DataRepository):
        self._repo = repo

    def summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        return self._repo.get_summary_stats(start_date, end_date)

    def monthly(self, year: int) -> dict:
        months = self._repo.get_monthly_stats(year)
        return {"year": year, "months": months}

    def category(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "expense",
    ) -> dict:
        items = self._repo.get_category_stats(start_date, end_date, direction)
        total = sum(i["amount"] for i in items)
        return {"items": items, "total": round(total, 2)}

    def daily(self, year: int, month: int) -> dict:
        days = self._repo.get_daily_stats(year, month)
        return {"year": year, "month": month, "days": days}
