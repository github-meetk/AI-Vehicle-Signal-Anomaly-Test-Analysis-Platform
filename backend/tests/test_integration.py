"""Integration tests for API and end-to-end workflow."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use SQLite for tests
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.database.models import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestAPI:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_list_signals(self, client):
        r = client.get("/api/signals")
        assert r.status_code == 200
        assert len(r.json()) == 8

    def test_generate_and_detect(self, client):
        r = client.post(
            "/api/scenarios/generate",
            json={
                "scenario_type": "high_load",
                "fault_type": "COOLING_FAILURE",
                "injection_time": 125.0,
                "seed": 42,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["anomalies_count"] > 0

        r2 = client.get("/api/anomalies")
        assert r2.status_code == 200
        anomalies = r2.json()
        assert len(anomalies) > 0

    def test_investigate_anomaly(self, client):
        client.post(
            "/api/scenarios/generate",
            json={
                "scenario_type": "high_load",
                "fault_type": "COOLING_FAILURE",
                "injection_time": 125.0,
                "seed": 42,
            },
        )
        anomalies = client.get("/api/anomalies").json()
        anomaly_id = anomalies[0]["id"]

        r = client.post(f"/api/anomalies/{anomaly_id}/investigate")
        assert r.status_code == 200
        result = r.json()
        assert "investigation_id" in result
        assert result["result"]["summary"]
        assert len(result["trace"]) > 0

    def test_dashboard(self, client):
        r = client.get("/api/dashboard/summary")
        assert r.status_code == 200

    def test_requirements_and_tests(self, client):
        assert len(client.get("/api/requirements").json()) >= 5
        assert len(client.get("/api/tests").json()) >= 5


class TestEndToEnd:
    def test_full_workflow(self, client):
        """Generate → Detect → Investigate → Retrieve evidence."""
        gen = client.post(
            "/api/scenarios/generate",
            json={
                "scenario_type": "high_load",
                "fault_type": "COOLING_FAILURE",
                "injection_time": 125.4,
                "seed": 42,
            },
        )
        assert gen.status_code == 200

        anomalies = client.get("/api/anomalies").json()
        assert len(anomalies) > 0
        a = anomalies[0]

        signals = client.get(f"/api/anomalies/{a['id']}/signals")
        assert signals.status_code == 200
        assert "window_data" in signals.json()

        inv = client.post(f"/api/anomalies/{a['id']}/investigate")
        assert inv.status_code == 200
        inv_data = inv.json()

        inv_get = client.get(f"/api/investigations/{inv_data['investigation_id']}")
        assert inv_get.status_code == 200
