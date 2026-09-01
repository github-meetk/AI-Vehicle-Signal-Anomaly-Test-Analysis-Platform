"""AI Investigation Agent — explains pre-detected anomalies using deterministic tools.

IMPORTANT: The LLM does NOT determine whether a signal is anomalous.
Anomaly detection is performed by deterministic algorithms (see analysis/detector.py).
The agent investigates WHY an anomaly occurred and WHAT to do next.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.database.models import AgentRunDB, InvestigationDB
from app.models.schemas import EvidenceItem, InvestigationResult
from app.tools.investigation_tools import InvestigationTools


class InvestigationAgent:
    """Single investigation agent with deterministic tool use."""

    def __init__(self, db: Session):
        self.db = db
        self.tools = InvestigationTools(db)

    def investigate(self, anomaly_id: str) -> dict:
        investigation_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        start = time.time()
        trace_steps = []

        try:
            evidence = self.tools.collect_all_evidence(anomaly_id)
            if "error" in evidence:
                raise ValueError(evidence["error"])

            anomaly = evidence["anomaly"]
            tool_trace = self.tools.get_trace()

            for step in tool_trace:
                trace_steps.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "tool": step["tool"],
                        "input": step["input"],
                        "output_summary": step["output_summary"][:300],
                        "status": step["status"],
                        "latency_ms": step["latency_ms"],
                    }
                )

            if settings.openai_api_key:
                result = self._llm_investigate(anomaly_id, evidence)
            else:
                result = self._mock_investigate(anomaly_id, evidence)

            inv_db = InvestigationDB(
                id=investigation_id,
                anomaly_id=anomaly_id,
                summary=result.summary,
                observations=result.observations,
                supporting_evidence=[e.model_dump() for e in result.supporting_evidence],
                possible_causes=result.possible_causes,
                related_requirements=result.related_requirements,
                recommended_followup_tests=result.recommended_followup_tests,
                confidence=result.confidence,
                status="completed",
            )
            self.db.add(inv_db)

            latency = (time.time() - start) * 1000
            self.db.add(
                AgentRunDB(
                    id=str(uuid.uuid4()),
                    investigation_id=investigation_id,
                    anomaly_id=anomaly_id,
                    trace=trace_steps,
                    status="completed",
                    latency_ms=latency,
                )
            )
            self.db.commit()

            return {
                "investigation_id": investigation_id,
                "result": result.model_dump(),
                "trace": trace_steps,
                "status": "completed",
            }

        except Exception as e:
            logger.error("investigation_failed", anomaly_id=anomaly_id, error=str(e))
            latency = (time.time() - start) * 1000
            self.db.add(
                AgentRunDB(
                    id=str(uuid.uuid4()),
                    investigation_id=investigation_id,
                    anomaly_id=anomaly_id,
                    trace=trace_steps,
                    status="failed",
                    latency_ms=latency,
                    error=str(e),
                )
            )
            self.db.commit()
            return {
                "investigation_id": investigation_id,
                "error": str(e),
                "trace": trace_steps,
                "status": "failed",
            }

    def _mock_investigate(self, anomaly_id: str, evidence: dict) -> InvestigationResult:
        """Deterministic investigation when no LLM API key is configured."""
        anomaly = evidence["anomaly"]
        stats = evidence.get("primary_statistics", {})
        related = evidence.get("related_statistics", {})
        baseline = evidence.get("baseline_comparison", {})
        reqs = evidence.get("requirements", {}).get("requirements", [])
        followup = evidence.get("followup_suggestions", {}).get("suggestions", [])

        observations = []
        supporting = []

        if stats and "error" not in stats:
            obs = (
                f"{anomaly['signal']} ranged from {stats.get('min', 'N/A'):.1f} to "
                f"{stats.get('max', 'N/A'):.1f} {stats.get('unit', '')} "
                f"around t={anomaly['start_time']:.1f}s"
            )
            observations.append(obs)
            supporting.append(
                EvidenceItem(
                    signal=anomaly["signal"],
                    description=obs,
                    value=stats.get("max"),
                    timestamp=anomaly["start_time"],
                    unit=stats.get("unit"),
                )
            )

        for sig, rst in related.items():
            if isinstance(rst, dict) and "error" not in rst:
                obs = f"Related signal {sig}: mean={rst.get('mean', 0):.1f}, max={rst.get('max', 0):.1f}"
                observations.append(obs)
                supporting.append(
                    EvidenceItem(
                        signal=sig,
                        description=obs,
                        value=rst.get("max"),
                        timestamp=anomaly["start_time"],
                        unit=rst.get("unit"),
                    )
                )

        if baseline and "delta" in baseline:
            observations.append(
                f"Baseline comparison: {anomaly['signal']} delta={baseline['delta']:.2f} "
                f"vs normal scenario"
            )

        causes = []
        if anomaly["anomaly_type"] in ("RELATIONSHIP_VIOLATION", "IMPOSSIBLE_COMBINATION"):
            causes.append("Sensor inconsistency or cooling system failure")
            causes.append("Possible ECU calibration or sensor drift")
        elif anomaly["anomaly_type"] == "THRESHOLD_VIOLATION":
            causes.append("Thermal load exceeded design limits")
            causes.append("Insufficient cooling response under high current")
        elif anomaly["anomaly_type"] == "MISSING_SIGNAL":
            causes.append("Communication dropout or sensor disconnect")
        else:
            causes.append(f"Abnormal {anomaly['signal']} behavior detected by {anomaly['detection_method']}")

        req_ids = [r["id"] for r in reqs[:3]]
        followup_tests = [s["test_name"] for s in followup]

        summary = (
            f"Investigation of {anomaly['anomaly_type']} on {anomaly['signal']} "
            f"at t={anomaly['start_time']:.1f}s (severity: {anomaly['severity']}). "
            f"Observed value: {anomaly['observed_value']:.2f}. "
            f"Detection method: {anomaly['detection_method']} (deterministic)."
        )

        return InvestigationResult(
            anomaly_id=anomaly_id,
            summary=summary,
            observations=observations,
            supporting_evidence=supporting,
            possible_causes=causes,
            related_requirements=req_ids,
            recommended_followup_tests=followup_tests,
            confidence=0.78,
        )

    def _llm_investigate(self, anomaly_id: str, evidence: dict) -> InvestigationResult:
        """LLM-based investigation with structured output."""
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.1,
            ).with_structured_output(InvestigationResult)

            system_prompt = """You are an automotive E/E validation engineer investigating
a PRE-DETECTED anomaly. You must NOT claim to have detected the anomaly yourself.
The deterministic detector already found it. Your job is to explain WHY based ONLY
on the provided evidence. Do not invent numbers not present in the evidence.
Reference actual observed values from the evidence data."""

            user_prompt = f"""Investigate this pre-detected anomaly using the evidence below.
Anomaly ID: {anomaly_id}

Evidence (from deterministic tools):
{json.dumps(evidence, indent=2, default=str)[:8000]}

Provide structured investigation result with summary, observations, supporting evidence,
possible causes, related requirements, and follow-up test recommendations."""

            result = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            if isinstance(result, InvestigationResult):
                result.anomaly_id = anomaly_id
                return result
            return InvestigationResult.model_validate(result)

        except Exception as e:
            logger.warning("llm_investigation_fallback", error=str(e))
            return self._mock_investigate(anomaly_id, evidence)

    def get_investigation(self, investigation_id: str) -> dict | None:
        inv = self.db.query(InvestigationDB).filter(InvestigationDB.id == investigation_id).first()
        if not inv:
            return None
        run = (
            self.db.query(AgentRunDB)
            .filter(AgentRunDB.investigation_id == investigation_id)
            .first()
        )
        return {
            "id": inv.id,
            "anomaly_id": inv.anomaly_id,
            "summary": inv.summary,
            "observations": inv.observations,
            "supporting_evidence": inv.supporting_evidence,
            "possible_causes": inv.possible_causes,
            "related_requirements": inv.related_requirements,
            "recommended_followup_tests": inv.recommended_followup_tests,
            "confidence": inv.confidence,
            "status": inv.status,
            "trace": run.trace if run else [],
        }
