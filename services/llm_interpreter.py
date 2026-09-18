import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class StructuredAdjustment(BaseModel):
    hours: List[int] = Field(description="Ascending list of hour integers from 0 to 23")
    factor: Optional[float] = Field(default=None, description="Usable solar fraction remaining (e.g., 0.25 for 25% usable solar)")
    minimum_energy_kwh: Optional[float] = Field(default=None, description="Absolute kWh reserve required")
    max_grid_kwh: Optional[float] = Field(default=None, description="Max grid import cap in kWh")


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: str = Field(description="One of: solar_reduction, minimum_battery_reserve, no_charge_window, no_discharge_window, max_grid_window, no_op")
    structured_adjustment: Optional[StructuredAdjustment] = None
    explanation: str


class LLMInterpretationResult(BaseModel):
    directive_interpretation: List[DirectiveInterpretation]
    plan_summary: str


SYSTEM_PROMPT = """You are the GridWise Directive Interpreter.
Interpret human operator notes into exact JSON microgrid optimization directives.

Allowed directive_type values:
- solar_reduction: Reduces available solar generation by a fraction factor over specified hours (e.g., 'usable solar is 25%' -> factor = 0.25).
- minimum_battery_reserve: Raises minimum battery reserve to minimum_energy_kwh over specified hours. If given as %, calculate absolute kWh from total battery capacity.
- no_charge_window: Disables battery charging during listed hours.
- no_discharge_window: Disables battery discharging during listed hours.
- max_grid_window: Caps grid import to max_grid_kwh per hour during listed hours.
- no_op: Unrelated notes that do not affect today's schedule (applies=false, structured_adjustment=null).

Rules:
1. Return exactly one directive_interpretation per operator note in note_index order.
2. Hours are 0-indexed (0 to 23). Time windows are start-inclusive and end-exclusive (e.g., 2 PM to 4 PM maps to hours [14, 15]).
3. "6 PM until 9 PM" maps to hours [18, 19, 20].

solar_reduction: Reduces available solar generation. Set 'factor' to the usable fraction remaining. 
Example 1: "usable solar is 25%" -> factor = 0.25
Example 2: "solar generation reduced by 80%" -> factor = 0.20 (since 100% - 80% = 20% remaining)
"""


def interpret_operator_notes(operator_notes: List[str], battery_info: dict) -> LLMInterpretationResult:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    client = genai.Client(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    user_prompt = f"""
Battery Specs: Capacity = {battery_info['capacity_kwh']} kWh, Min Reserve = {battery_info['minimum_energy_kwh']} kWh.
Operator Notes to Interpret:
{json.dumps(operator_notes, indent=2)}
"""

    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=LLMInterpretationResult,
            temperature=0.0,
        ),
    )

    return LLMInterpretationResult.model_validate_json(response.text)

def sanitize_and_guardrail_directives(directives: List[DirectiveInterpretation]) -> List[dict]:
    """
    Enforces deterministic constraints on raw LLM output before passing to PuLP.
    """
    sanitized = []
    for item in directives:
        d_dict = item.model_dump()
        
        # Guardrail 1: no_op must have applies=False and structured_adjustment=None
        if d_dict["directive_type"] == "no_op" or not d_dict["applies"]:
            d_dict["applies"] = False
            d_dict["structured_adjustment"] = None
            sanitized.append(d_dict)
            continue

        adj = d_dict.get("structured_adjustment")
        if adj and "hours" in adj and adj["hours"]:
            # Guardrail 2: Ensure unique integers 0-23 in strictly ascending order
            valid_hours = sorted(list(set(
                int(h) for h in adj["hours"] if isinstance(h, (int, float)) and 0 <= int(h) <= 23
            )))
            adj["hours"] = valid_hours

            # Guardrail 3: Solar reduction factor bounds [0.0, 1.0]
            if d_dict["directive_type"] == "solar_reduction" and "factor" in adj:
                if adj["factor"] is not None:
                    adj["factor"] = max(0.0, min(1.0, float(adj["factor"])))

            d_dict["structured_adjustment"] = adj
            d_dict["applies"] = True
        else:
            # Fallback invalid directives without valid hours to no_op
            d_dict["applies"] = False
            d_dict["structured_adjustment"] = None

        sanitized.append(d_dict)
    return sanitized