from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


def _clean_text(value: Optional[str]) -> str:
    return (value or "").strip()


class ClassificationRuleBase(BaseModel):
    name: str
    priority: int = 100
    is_active: bool = True
    match_counterparty: str = ""
    match_product: str = ""
    match_payment_method: str = ""
    match_transaction_type: str = ""
    category: str = ""
    remark: str = ""

    @field_validator(
        "name",
        "match_counterparty",
        "match_product",
        "match_payment_method",
        "match_transaction_type",
        "category",
        "remark",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value):
        return _clean_text(value)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if value < 0:
            raise ValueError("优先级不能小于 0")
        return value

    @model_validator(mode="after")
    def validate_rule(self):
        if not any(
            [
                self.match_counterparty,
                self.match_product,
                self.match_payment_method,
                self.match_transaction_type,
            ]
        ):
            raise ValueError("至少填写一个匹配条件")
        if not any([self.category, self.remark]):
            raise ValueError("至少填写一个自动填充结果")
        return self


class ClassificationRuleCreate(ClassificationRuleBase):
    pass


class ClassificationRuleUpdate(ClassificationRuleBase):
    pass


class ClassificationRuleResponse(ClassificationRuleBase):
    id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
