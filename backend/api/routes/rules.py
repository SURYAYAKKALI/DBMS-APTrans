"""
Business Rules Management Endpoints
"""

from fastapi import APIRouter
from typing import List
from backend.api.schemas.models import RuleCreate, RuleResponse
from backend.consistency.rule_validator import RuleValidator

router = APIRouter(prefix="/rules", tags=["Business Consistency Rules"])

@router.get("", response_model=List[RuleResponse])
def get_rules():
    return RuleValidator.list_rules()

@router.post("", response_model=RuleResponse)
def create_rule(req: RuleCreate):
    return RuleValidator.add_rule(
        name=req.name,
        description=req.description or "",
        target_table=req.target_table,
        rule_definition=req.rule_definition,
        severity=req.severity
    )
