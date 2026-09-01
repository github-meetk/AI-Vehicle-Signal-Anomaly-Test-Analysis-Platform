from fastapi import APIRouter

from app.services.requirements import REQUIREMENTS

router = APIRouter()


@router.get("/requirements")
def list_requirements():
    return [r.model_dump() for r in REQUIREMENTS]
