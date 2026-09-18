"""Deterministic validation for untrusted model and optimizer output."""

import math
from typing import Any

from app.models import DirectiveInterpretation, HourlyPlanEntry, OptimizeRequest


TOLERANCE = 0.01


class SemanticValidationError(Exception):
    pass


class DirectiveValidationError(Exception):
    pass


class PlanValidationError(Exception):
    pass


def _finite_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate_request(data: OptimizeRequest) -> None:
    if not data.scenario_id.strip():
        raise SemanticValidationError("scenario_id cannot be blank")

    hours = [item.hour for item in data.hours]
    if sorted(hours) != list(range(24)):
        raise SemanticValidationError(
            "hours must contain each integer from 0 through 23 exactly once"
        )

    if any(not note.strip() for note in data.operator_notes):
        raise SemanticValidationError("operator_notes cannot contain empty strings")

    battery = data.battery
    if battery.minimum_energy_kwh > battery.capacity_kwh:
        raise SemanticValidationError(
            "minimum_energy_kwh cannot exceed capacity_kwh"
        )
    if battery.initial_energy_kwh > battery.capacity_kwh:
        raise SemanticValidationError("initial_energy_kwh cannot exceed capacity_kwh")
    if battery.initial_energy_kwh < battery.minimum_energy_kwh:
        raise SemanticValidationError(
            "initial_energy_kwh cannot be below minimum_energy_kwh"
        )


def _validate_hours(hours: Any) -> None:
    if not isinstance(hours, list) or not hours:
        raise DirectiveValidationError("directive hours must be a non-empty array")
    if any(type(hour) is not int for hour in hours):
        raise DirectiveValidationError("directive hours must be integers")
    if any(hour < 0 or hour > 23 for hour in hours):
        raise DirectiveValidationError("directive hours must be between 0 and 23")
    if hours != sorted(set(hours)):
        raise DirectiveValidationError("directive hours must be unique and sorted")


def validate_directives(
    directives: list[DirectiveInterpretation], request: OptimizeRequest
) -> None:
    if len(directives) != len(request.operator_notes):
        raise DirectiveValidationError(
            "one directive interpretation is required per operator note"
        )

    if [item.note_index for item in directives] != list(
        range(len(request.operator_notes))
    ):
        raise DirectiveValidationError(
            "directive entries must be returned in note_index order"
        )

    for directive in directives:
        dtype = directive.directive_type
        adjustment = directive.structured_adjustment
        if not directive.explanation.strip():
            raise DirectiveValidationError("directive explanation cannot be blank")

        if dtype == "no_op":
            if directive.applies is not False or adjustment is not None:
                raise DirectiveValidationError(
                    "no_op requires applies=false and structured_adjustment=null"
                )
            continue

        if directive.applies is not True:
            raise DirectiveValidationError("non-no_op directives require applies=true")
        if not isinstance(adjustment, dict) or "hours" not in adjustment:
            raise DirectiveValidationError(
                "non-no_op structured_adjustment requires hours"
            )
        _validate_hours(adjustment["hours"])

        if dtype == "solar_reduction":
            if set(adjustment) != {"hours", "factor"}:
                raise DirectiveValidationError("invalid solar_reduction structure")
            factor = adjustment["factor"]
            if not _finite_number(factor) or not 0 <= factor <= 1:
                raise DirectiveValidationError("solar factor must be between 0 and 1")
        elif dtype == "minimum_battery_reserve":
            if set(adjustment) != {"hours", "minimum_energy_kwh"}:
                raise DirectiveValidationError(
                    "invalid minimum_battery_reserve structure"
                )
            reserve = adjustment["minimum_energy_kwh"]
            if (
                not _finite_number(reserve)
                or reserve < 0
                or reserve > request.battery.capacity_kwh
            ):
                raise DirectiveValidationError("invalid minimum battery reserve")
        elif dtype in {"no_charge_window", "no_discharge_window"}:
            if set(adjustment) != {"hours"}:
                raise DirectiveValidationError(f"invalid {dtype} structure")
        elif dtype == "max_grid_window":
            if set(adjustment) != {"hours", "max_grid_kwh"}:
                raise DirectiveValidationError("invalid max_grid_window structure")
            limit = adjustment["max_grid_kwh"]
            if not _finite_number(limit) or limit < 0:
                raise DirectiveValidationError("invalid max_grid_kwh")


def _build_constraints(
    request: OptimizeRequest, directives: list[DirectiveInterpretation]
) -> tuple[dict[int, float], dict[int, float], set[int], set[int], dict[int, float | None]]:
    solar_factor = {hour: 1.0 for hour in range(24)}
    minimum_reserve = {
        hour: request.battery.minimum_energy_kwh for hour in range(24)
    }
    no_charge: set[int] = set()
    no_discharge: set[int] = set()
    max_grid: dict[int, float | None] = {hour: None for hour in range(24)}

    for directive in directives:
        if not directive.applies:
            continue
        adjustment = directive.structured_adjustment or {}
        hours = adjustment["hours"]
        if directive.directive_type == "solar_reduction":
            for hour in hours:
                solar_factor[hour] = min(solar_factor[hour], adjustment["factor"])
        elif directive.directive_type == "minimum_battery_reserve":
            for hour in hours:
                minimum_reserve[hour] = max(
                    minimum_reserve[hour], adjustment["minimum_energy_kwh"]
                )
        elif directive.directive_type == "no_charge_window":
            no_charge.update(hours)
        elif directive.directive_type == "no_discharge_window":
            no_discharge.update(hours)
        elif directive.directive_type == "max_grid_window":
            for hour in hours:
                current = max_grid[hour]
                limit = adjustment["max_grid_kwh"]
                max_grid[hour] = limit if current is None else min(current, limit)

    return solar_factor, minimum_reserve, no_charge, no_discharge, max_grid


def validate_hourly_plan(
    request: OptimizeRequest,
    directives: list[DirectiveInterpretation],
    plan: list[HourlyPlanEntry],
) -> None:
    if len(plan) != 24 or sorted(row.hour for row in plan) != list(range(24)):
        raise PlanValidationError(
            "hourly_plan must contain hours 0 through 23 exactly once"
        )

    plan_by_hour = {row.hour: row for row in plan}
    input_by_hour = {row.hour: row for row in request.hours}
    solar_factor, minimum_reserve, no_charge, no_discharge, max_grid = (
        _build_constraints(request, directives)
    )

    battery_energy = request.battery.initial_energy_kwh
    for hour in range(24):
        row = plan_by_hour[hour]
        source = input_by_hour[hour]
        numeric_values = (
            row.grid_kwh,
            row.solar_used_kwh,
            row.battery_kwh,
            row.battery_energy_after_kwh,
        )
        if any(not math.isfinite(value) or value < 0 for value in numeric_values):
            raise PlanValidationError(f"Invalid numeric value at hour {hour}")

        effective_solar = source.solar_kwh * solar_factor[hour]
        if row.solar_used_kwh > effective_solar + TOLERANCE:
            raise PlanValidationError(
                f"Solar usage exceeds availability at hour {hour}"
            )

        charge = row.battery_kwh if row.battery_action == "charge" else 0.0
        discharge = row.battery_kwh if row.battery_action == "discharge" else 0.0
        if row.battery_action == "idle" and row.battery_kwh > TOLERANCE:
            raise PlanValidationError(f"Idle battery has nonzero energy at hour {hour}")
        if charge > request.battery.max_charge_kwh_per_hour + TOLERANCE:
            raise PlanValidationError(f"Charge rate exceeded at hour {hour}")
        if discharge > request.battery.max_discharge_kwh_per_hour + TOLERANCE:
            raise PlanValidationError(f"Discharge rate exceeded at hour {hour}")
        if hour in no_charge and charge > TOLERANCE:
            raise PlanValidationError(f"Charging forbidden at hour {hour}")
        if hour in no_discharge and discharge > TOLERANCE:
            raise PlanValidationError(f"Discharging forbidden at hour {hour}")
        if max_grid[hour] is not None and row.grid_kwh > max_grid[hour] + TOLERANCE:
            raise PlanValidationError(f"Grid import limit exceeded at hour {hour}")

        energy_in = row.grid_kwh + row.solar_used_kwh + discharge
        energy_out = source.demand_kwh + charge
        if abs(energy_in - energy_out) > TOLERANCE:
            raise PlanValidationError(f"Energy balance violated at hour {hour}")

        expected_energy = battery_energy + charge - discharge
        if abs(expected_energy - row.battery_energy_after_kwh) > TOLERANCE:
            raise PlanValidationError(
                f"Battery state transition incorrect at hour {hour}"
            )
        if expected_energy > request.battery.capacity_kwh + TOLERANCE:
            raise PlanValidationError(f"Battery capacity exceeded at hour {hour}")
        if expected_energy < minimum_reserve[hour] - TOLERANCE:
            raise PlanValidationError(f"Battery reserve violated at hour {hour}")
        battery_energy = expected_energy

    if abs(battery_energy - request.battery.initial_energy_kwh) > TOLERANCE:
        raise PlanValidationError(
            "Battery must finish hour 23 at its initial energy level"
        )


def calculate_totals(
    request: OptimizeRequest, plan: list[HourlyPlanEntry]
) -> tuple[float, float, float]:
    tariff_by_hour = {item.hour: item.tariff_bdt_per_kwh for item in request.hours}
    total_grid = sum(row.grid_kwh for row in plan)
    total_cost = sum(row.grid_kwh * tariff_by_hour[row.hour] for row in plan)
    peak_grid = max(row.grid_kwh for row in plan)
    return round(total_grid, 6), round(total_cost, 6), round(peak_grid, 6)
