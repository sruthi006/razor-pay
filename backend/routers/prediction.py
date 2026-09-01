from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import model_service
from backend.schemas import PredictionRequest, PredictionResponse
from backend.services.model_service import ModelService

router = APIRouter(tags=["prediction"])


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest, service: ModelService = Depends(model_service)) -> dict:
    try:
        return service.score(request)
    except PermissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
