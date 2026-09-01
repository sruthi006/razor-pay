from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import simulation_service
from backend.schemas import SimulationRequest
from backend.services.simulation_service import SimulationService

router = APIRouter(tags=["simulation"])


@router.post("/simulate")
def simulate(request: SimulationRequest, service: SimulationService = Depends(simulation_service)) -> dict:
    try:
        return service.simulate(request)
    except PermissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
