from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from autocoin.auth import get_current_user
from autocoin.database import get_db
from autocoin.models.user import User
from autocoin.repository.sqlite import SQLiteRepository
from autocoin.schemas.classification_rule import (
    ClassificationRuleCreate,
    ClassificationRuleResponse,
    ClassificationRuleUpdate,
)

router = APIRouter(prefix="/rules", tags=["rules"])


def get_repo(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SQLiteRepository:
    return SQLiteRepository(db, user.id)


@router.get("", response_model=list[ClassificationRuleResponse])
def list_rules(repo: SQLiteRepository = Depends(get_repo)):
    return repo.list_classification_rules()


@router.post("", response_model=ClassificationRuleResponse, status_code=201)
def create_rule(
    body: ClassificationRuleCreate,
    repo: SQLiteRepository = Depends(get_repo),
):
    return repo.create_classification_rule(body.model_dump())


@router.put("/{rule_id}", response_model=ClassificationRuleResponse)
def update_rule(
    rule_id: int,
    body: ClassificationRuleUpdate,
    repo: SQLiteRepository = Depends(get_repo),
):
    rule = repo.update_classification_rule(rule_id, body.model_dump())
    if not rule:
        raise HTTPException(status_code=404, detail="分类规则不存在")
    return rule


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, repo: SQLiteRepository = Depends(get_repo)):
    if not repo.delete_classification_rule(rule_id):
        raise HTTPException(status_code=404, detail="分类规则不存在")
    return {"ok": True}
