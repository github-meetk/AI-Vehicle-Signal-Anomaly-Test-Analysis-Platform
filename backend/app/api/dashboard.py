import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.models import get_db
from app.services.scenario_service import ScenarioService

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    return ScenarioService(db).get_dashboard_summary().model_dump()


@router.get("/dashboard/evaluation")
def dashboard_evaluation():
    results_path = Path("evaluation/results/latest_metrics.json")
    ai_path = Path("evaluation/results/ai_evaluation.json")
    metrics = []
    ai_eval = {}
    if results_path.exists():
        with open(results_path) as f:
            metrics = json.load(f)
    if ai_path.exists():
        with open(ai_path) as f:
            ai_eval = json.load(f)
    return {"detection_metrics": metrics, "ai_evaluation": ai_eval}


@router.get("/dashboard/data-quality")
def data_quality_summary(db: Session = Depends(get_db)):
    from app.database.models import ScenarioDB

    scenarios = db.query(ScenarioDB).all()
    return {
        "scenarios": len(scenarios),
        "avg_quality_score": (
            sum(s.quality_score for s in scenarios if s.quality_score) / len(scenarios)
            if scenarios
            else 0
        ),
        "scenarios_detail": [
            {
                "id": s.id,
                "quality_score": s.quality_score,
                "fault_type": s.fault_type,
            }
            for s in scenarios
        ],
    }
