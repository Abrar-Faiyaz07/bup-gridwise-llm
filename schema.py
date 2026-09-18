from typing import List, Optional
from pydantic import BaseModel, Field


class BatterySpecs(BaseModel):
    capacity_kwh: float = Field(..., gt=0)
    initial_energy_kwh: float = Field(..., ge=0)
    minimum_energy_kwh: float = Field(..., ge=0)
    max_charge_kwh_per_hour: float = Field(..., gt=0)
    max_discharge_kwh_per_hour: float = Field(..., gt=0)


class HourlyData(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    demand_kwh: float = Field(..., ge=0)
    solar_kwh: float = Field(..., ge=0)
    tariff_bdt_per_kwh: float = Field(..., ge=0)


class OptimizationRequest(BaseModel):
    scenario_id: str
    operator_notes: List[str]
    hours: List[HourlyData]
    battery: BatterySpecs