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