import asyncio
import json

import app.services as services
from app.models import OptimizeRequest


def _request() -> OptimizeRequest:
    return OptimizeRequest.model_validate(
        {
            "scenario_id": "LLM-TEST",
            "operator_notes": ["The cafeteria menu changes tomorrow."],
            "hours": [
                {
                    "hour": hour,
                    "demand_kwh": 10,
                    "solar_kwh": 0,
                    "tariff_bdt_per_kwh": 5,
                }
                for hour in range(24)
            ],
            "battery": {
                "capacity_kwh": 20,
                "initial_energy_kwh": 10,
                "minimum_energy_kwh": 5,
                "max_charge_kwh_per_hour": 5,
                "max_discharge_kwh_per_hour": 5,
            },
        }
    )


def test_structured_output_request_and_parsing(monkeypatch) -> None:
    captured = {}
    model_output = {
        "directives": [
            {
                "note_index": 0,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": "This note is unrelated to today's energy schedule.",
            }
        ]
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {"type": "text", "text": json.dumps(model_output)}
                        ],
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, payload=json)
            return FakeResponse()

    services._interpretation_cache.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    monkeypatch.setattr(services.httpx, "AsyncClient", FakeClient)

    directives = asyncio.run(services.interpret_operator_notes(_request()))
    assert directives[0].directive_type == "no_op"
    assert captured["url"].endswith("/v1beta/interactions")
    assert captured["payload"]["model"] == "gemini-3.5-flash-lite"
    response_format = captured["payload"]["response_format"]
    assert response_format["mime_type"] == "application/json"
    assert response_format["schema"]["type"] == "object"
    assert captured["payload"]["store"] is False
    assert captured["headers"]["x-goog-api-key"] == "test-secret"
