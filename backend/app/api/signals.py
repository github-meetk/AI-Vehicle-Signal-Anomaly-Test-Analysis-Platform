from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.signal_registry import SIGNAL_REGISTRY
from app.database.models import get_db
from app.services.scenario_service import ScenarioService

router = APIRouter()


@router.get("/signals")
def list_signals():
    return [
        {
            "name": s.name,
            "unit": s.unit,
            "min_value": s.min_value,
            "max_value": s.max_value,
            "description": s.description,
            "expected_behavior": s.expected_behavior,
            "related_signals": s.related_signals,
        }
        for s in SIGNAL_REGISTRY.values()
    ]


@router.get("/signals/{name}")
def get_signal(name: str):
    sig = SIGNAL_REGISTRY.get(name)
    if not sig:
        raise HTTPException(404, f"Signal '{name}' not found")
    return {
        "name": sig.name,
        "unit": sig.unit,
        "min_value": sig.min_value,
        "max_value": sig.max_value,
        "description": sig.description,
        "expected_behavior": sig.expected_behavior,
        "related_signals": sig.related_signals,
    }


@router.get("/signals/data/{scenario_id}")
def get_signal_data(
    scenario_id: str,
    signals: str = Query(default="battery_temperature,battery_current"),
  db: Session = Depends(get_db),
):
    svc = ScenarioService(db)
    df = svc.get_scenario_df(scenario_id)
    if df.empty:
        raise HTTPException(404, f"No data for scenario {scenario_id}")
    sig_list = [s.strip() for s in signals.split(",")]
    cols = ["timestamp"] + [s for s in sig_list if s in df.columns]
    return df[cols].to_dict(orient="records")
