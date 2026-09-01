from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.investigation_agent import InvestigationAgent
from app.database.models import get_db
from app.services.scenario_service import AnomalyService, ScenarioService

router = APIRouter()


@router.get("/anomalies")
def list_anomalies(scenario_id: str | None = None, db: Session = Depends(get_db)):
    return AnomalyService(db).list_anomalies(scenario_id)


@router.get("/anomalies/{anomaly_id}")
def get_anomaly(anomaly_id: str, db: Session = Depends(get_db)):
    result = AnomalyService(db).get_anomaly(anomaly_id)
    if not result:
        raise HTTPException(404, "Anomaly not found")
    return result


@router.get("/anomalies/{anomaly_id}/signals")
def get_anomaly_signals(anomaly_id: str, db: Session = Depends(get_db)):
    svc = AnomalyService(db)
    scenario_svc = ScenarioService(db)
    result = svc.get_anomaly_signals(anomaly_id, scenario_svc)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/anomalies/{anomaly_id}/investigate")
def investigate_anomaly(anomaly_id: str, db: Session = Depends(get_db)):
    agent = InvestigationAgent(db)
    result = agent.investigate(anomaly_id)
    if result.get("status") == "failed":
        raise HTTPException(500, result.get("error", "Investigation failed"))
    return result
