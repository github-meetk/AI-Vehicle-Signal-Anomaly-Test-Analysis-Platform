from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.signal_registry import FaultType, ScenarioType
from app.database.models import get_db
from app.services.scenario_service import ScenarioService

router = APIRouter()


class GenerateScenarioRequest(BaseModel):
    scenario_type: ScenarioType = ScenarioType.HIGH_LOAD
    fault_type: FaultType = FaultType.NONE
    injection_time: float | None = None
    seed: int | None = None
    duration: float = 300.0


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    return ScenarioService(db).list_scenarios()


@router.post("/scenarios/generate")
def generate_scenario(req: GenerateScenarioRequest, db: Session = Depends(get_db)):
    return ScenarioService(db).generate_scenario(
        scenario_type=req.scenario_type,
        fault_type=req.fault_type,
        injection_time=req.injection_time,
        seed=req.seed,
        duration=req.duration,
    )
