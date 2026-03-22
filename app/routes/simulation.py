"""
FastAPI Routes: Simulation endpoints (placeholder for Phase 6)
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["Simulation"])


class SimulationRequest(BaseModel):
    station_id: int
    rainfall_mm_per_hour: float
    duration_hours: int = 6
    scenario_name: Optional[str] = "custom"


@router.post("/simulate")
def run_simulation(req: SimulationRequest):
    """
    Placeholder: Accept a rainfall scenario and return simulated predictions.
    Full implementation comes in Phase 6.
    """
    return {
        "status": "simulation_not_yet_implemented",
        "message": "Simulation engine will be built in Phase 6.",
        "input": req.dict(),
    }
