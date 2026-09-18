"""Replay the organizer's public sample pack against a running GridWise API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.guardrails import calculate_totals, validate_directives, validate_hourly_plan
from app.models import DirectiveInterpretation, HourlyPlanEntry, OptimizeRequest


def _post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _same_directive(actual: dict, expected: dict) -> bool:
    comparable = ("note_index", "applies", "directive_type", "structured_adjustment")
    return all(actual.get(key) == expected.get(key) for key in comparable)


_CASES_FILENAME = "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"


def _resolve_cases_path(user_path: Path) -> Path:
    """Find the public sample cases file regardless of repo layout.

    Resolution order:
      1. The path the user provided (absolute or relative to cwd).
      2. <script>/../../<cases>             (gridwise-api nested under LLM repo)
      3. <script>/../<cases>                (gridwise-api as sibling of LLM repo)
      4. cwd/<cases>
    """
    candidates: list[Path] = []
    raw = Path(user_path).expanduser()
    candidates.append(raw if raw.is_absolute() else (Path.cwd() / raw))
    candidates.append(ROOT.parent / _CASES_FILENAME)
    candidates.append(ROOT.parent.parent / _CASES_FILENAME)
    candidates.append(Path.cwd() / _CASES_FILENAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = "\n  ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        f"Could not locate {_CASES_FILENAME}. Looked at:\n  {searched}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(_CASES_FILENAME),
        help=(
            "Path to the public sample cases JSON. Defaults to the file shipped "
            "with the LLM repo; the script auto-resolves the well-known layout."
        ),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    cases_path = _resolve_cases_path(args.cases)
    pack = json.loads(cases_path.read_text(encoding="utf-8"))
    print(f"Using cases file: {cases_path}")
    failures: list[str] = []
    for case in pack["cases"]:
        case_id = case["id"]
        try:
            response = _post(
                f"{args.base_url.rstrip('/')}/optimize-energy", case["input"]
            )
            expected_directives = case["expected_output"]["directive_interpretation"]
            actual_directives = response["directive_interpretation"]
            if len(actual_directives) != len(expected_directives) or any(
                not _same_directive(actual, expected)
                for actual, expected in zip(actual_directives, expected_directives)
            ):
                raise AssertionError("directive interpretation differs from ground truth")

            model_request = OptimizeRequest.model_validate(case["input"])
            ground_truth = [
                DirectiveInterpretation.model_validate(item)
                for item in expected_directives
            ]
            validate_directives(ground_truth, model_request)
            plan = [
                HourlyPlanEntry.model_validate(item) for item in response["hourly_plan"]
            ]
            validate_hourly_plan(model_request, ground_truth, plan)
            grid, cost, peak = calculate_totals(model_request, plan)
            if abs(grid - response["total_grid_kwh"]) > 0.01:
                raise AssertionError("total_grid_kwh does not match hourly_plan")
            if abs(cost - response["total_cost_bdt"]) > 0.01:
                raise AssertionError("total_cost_bdt does not match hourly_plan")
            if abs(peak - response["peak_grid_kwh"]) > 0.01:
                raise AssertionError("peak_grid_kwh does not match hourly_plan")
            if abs(cost - case["expected_output"]["total_cost_bdt"]) > 0.01:
                raise AssertionError("cost is not equivalent to the public optimum")
            print(f"PASS {case_id}: cost={cost:.2f} BDT")
        except (AssertionError, KeyError, ValueError, urllib.error.URLError) as exc:
            failures.append(f"{case_id}: {exc}")
            print(f"FAIL {case_id}: {exc}")

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print(f"\nAll {len(pack['cases'])} public cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
