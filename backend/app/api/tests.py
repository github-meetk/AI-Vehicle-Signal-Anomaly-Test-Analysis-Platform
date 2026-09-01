from fastapi import APIRouter

from app.services.requirements import TESTS

router = APIRouter()


@router.get("/tests")
def list_tests():
    return [t.model_dump() for t in TESTS]
