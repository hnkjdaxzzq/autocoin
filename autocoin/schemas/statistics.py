from typing import Optional

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    total_income: float
    total_expense: float
    net: float
    transaction_count: int
    income_count: int
    expense_count: int


class MonthStat(BaseModel):
    month: int
    income: float
    expense: float
    net: float
    count: int


class MonthlyResponse(BaseModel):
    year: int
    months: list[MonthStat]


class CategoryStat(BaseModel):
    category: str
    amount: float
    count: int
    percentage: float


class CategoryResponse(BaseModel):
    items: list[CategoryStat]
    total: float


class DayStat(BaseModel):
    date: str
    income: float
    expense: float


class DailyResponse(BaseModel):
    year: int
    month: int
    days: list[DayStat]
