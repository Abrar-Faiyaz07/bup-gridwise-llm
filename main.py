import os
from fastapi import FastAPI, HTTPException, status
from schema import OptimizationRequest
from services.llm_interpreter import interpret_operator_notes
from services.optimizer import run_gridwise_optimization

app = FastAPI(
    title="GridWise LLM Microgrid Optimizer",
    version="1.0.0"
)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "ok"}


@app.post("/optimize-energy", status_code=status.HTTP_200_OK)
def optimize_energy(payload: OptimizationRequest):
    try:
        battery_dict = payload.battery.model_dump()
        hours_dict = [h.model_dump() for h in payload.hours]

        # Step 1: Parse natural language operator directives via Gemini LLM
        llm_result = interpret_operator_notes(payload.operator_notes, battery_dict)
        directives_json = [d.model_dump() for d in llm_result.directive_interpretation]

        # Step 2: Solve deterministic linear optimization model via PuLP
        opt_result = run_gridwise_optimization(hours_dict, battery_dict, directives_json)

        # Step 3: Return consolidated optimization response
        return {
            "scenario_id": payload.scenario_id,
            "directive_interpretation": directives_json,
            "hourly_plan": opt_result["hourly_plan"],
            "total_grid_kwh": opt_result["total_grid_kwh"],
            "total_cost_bdt": opt_result["total_cost_bdt"],
            "peak_grid_kwh": opt_result["peak_grid_kwh"],
            "plan_summary": llm_result.plan_summary,
        }

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Optimization error: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Internal engine error: {str(e)}"
        )