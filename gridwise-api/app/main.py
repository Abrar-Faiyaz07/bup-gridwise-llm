import asyncio

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.guardrails import (
    DirectiveValidationError,
    PlanValidationError,
    SemanticValidationError,
    calculate_totals,
    validate_directives,
    validate_hourly_plan,
    validate_request,
)
from app.models import OptimizeRequest, OptimizeResponse
from app.services import (
    LLMServiceError,
    OptimizationError,
    interpret_operator_notes,
    optimize_energy,
)


app = FastAPI(title="GridWise Energy Optimization API", version="2.0.0")


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": "Invalid request structure"})


@app.exception_handler(SemanticValidationError)
async def semantic_validation_handler(
    request: Request, exc: SemanticValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DirectiveValidationError)
async def directive_validation_handler(
    request: Request, exc: DirectiveValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "LLM interpretation failed deterministic validation"},
    )


@app.exception_handler(LLMServiceError)
async def llm_service_handler(request: Request, exc: LLMServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Language model interpretation failed"},
    )


@app.exception_handler(OptimizationError)
async def optimization_handler(
    request: Request, exc: OptimizationError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Unable to produce a feasible energy plan"},
    )


@app.exception_handler(PlanValidationError)
async def plan_validation_handler(
    request: Request, exc: PlanValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Optimizer returned an invalid plan"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest) -> OptimizeResponse:
    validate_request(request)
    directives = await interpret_operator_notes(request)
    validate_directives(directives, request)

    hourly_plan = await asyncio.to_thread(optimize_energy, request, directives)
    validate_hourly_plan(request, directives, hourly_plan)
    total_grid_kwh, total_cost_bdt, peak_grid_kwh = calculate_totals(
        request, hourly_plan
    )

    applied = sum(item.applies for item in directives)
    return OptimizeResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=directives,
        hourly_plan=hourly_plan,
        total_grid_kwh=total_grid_kwh,
        total_cost_bdt=total_cost_bdt,
        peak_grid_kwh=peak_grid_kwh,
        plan_summary=(
            f"Applied {applied} operator directive(s), satisfied all energy and "
            "battery constraints, minimized grid cost, and restored the initial "
            "battery level at the end of hour 23."
        ),
    )
