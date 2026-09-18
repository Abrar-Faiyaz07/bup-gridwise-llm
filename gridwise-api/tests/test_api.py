from fastapi.testclient import TestClient

import app.main as main_module
from app.models import DirectiveInterpretation


def request_payload() -> dict:
    return {
        "scenario_id": "TEST-1",
        "operator_notes": ["The cafeteria menu changes tomorrow."],
        "hours": [
            {
                "hour": hour,
                "demand_kwh": 100,
                "solar_kwh": 0,
                "tariff_bdt_per_kwh": 5 if hour < 12 else 10,
            }
            for hour in range(24)
        ],
        "battery": {
            "capacity_kwh": 100,
            "initial_energy_kwh": 50,
            "minimum_energy_kwh": 20,
            "max_charge_kwh_per_hour": 20,
            "max_discharge_kwh_per_hour": 20,
        },
    }


async def fake_interpreter(_request):
    return [
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type="no_op",
            structured_adjustment=None,
            explanation="The note is unrelated to today's energy schedule.",
        )
    ]


def test_health() -> None:
    with TestClient(main_module.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_optimize_contract(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "interpret_operator_notes", fake_interpreter)
    with TestClient(main_module.app) as client:
        response = client.post("/optimize-energy", json=request_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "scenario_id",
        "directive_interpretation",
        "hourly_plan",
        "total_grid_kwh",
        "total_cost_bdt",
        "peak_grid_kwh",
        "plan_summary",
    }
    assert body["scenario_id"] == "TEST-1"
    assert len(body["directive_interpretation"]) == 1
    assert len(body["hourly_plan"]) == 24
    assert body["hourly_plan"][-1]["battery_energy_after_kwh"] == 50


def test_malformed_json_is_400() -> None:
    with TestClient(main_module.app) as client:
        response = client.post(
            "/optimize-energy",
            content=b"{not-json",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request structure"}


def test_semantic_error_is_422(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "interpret_operator_notes", fake_interpreter)
    payload = request_payload()
    payload["hours"][23]["hour"] = 22
    with TestClient(main_module.app) as client:
        response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 422


def test_missing_field_is_400() -> None:
    payload = request_payload()
    del payload["battery"]
    with TestClient(main_module.app) as client:
        response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400
