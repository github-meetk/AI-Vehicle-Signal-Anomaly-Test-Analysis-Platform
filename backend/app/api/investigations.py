from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.investigation_agent import InvestigationAgent
from app.database.models import get_db

router = APIRouter()


@router.get("/investigations/{investigation_id}")
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    result = InvestigationAgent(db).get_investigation(investigation_id)
    if not result:
        raise HTTPException(404, "Investigation not found")
    return result
