import json
import os
from pathlib import Path

import pytest

from app.guardrails import calculate_totals, validate_directives, validate_hourly_plan
from app.models import DirectiveInterpretation, OptimizeRequest
from app.services import optimize_energy


def _sample_path() -> Path:
    configured = os.getenv("PUBLIC_SAMPLE_CASES_PATH")
    if not configured:
        pytest.skip("Set PUBLIC_SAMPLE_CASES_PATH to run organizer public cases")
    path = Path(configured)
    if not path.is_file():
        pytest.fail(f"Public sample file does not exist: {path}")
    return path


def test_all_public_sample_optimizations() -> None:
    pack = json.loads(_sample_path().read_text(encoding="utf-8"))
    for case in pack["cases"]:
        request = OptimizeRequest.model_validate(case["input"])
        directives = [
            DirectiveInterpretation.model_validate(item)
            for item in case["expected_output"]["directive_interpretation"]
        ]
        validate_directives(directives, request)
        plan = optimize_energy(request, directives)
        validate_hourly_plan(request, directives, plan)
        totals = calculate_totals(request, plan)
        expected = case["expected_output"]
        assert abs(totals[1] - expected["total_cost_bdt"]) <= 0.01, case["id"]
