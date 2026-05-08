"""
Yield prediction API endpoint.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..yield_prediction import predict_yield

router = APIRouter()


class YieldPredictionRequest(BaseModel):
    """Optional overrides for yield prediction. All fields default to Maharashtra typical values."""

    annual_rainfall_mm: Optional[float] = Field(
        None, ge=0, le=10000, description="Annual rainfall in mm"
    )
    fertilizer_per_ha_kg: Optional[float] = Field(
        None, ge=0, le=2000, description="Fertilizer applied in kg/ha"
    )
    pesticide_per_ha_kg: Optional[float] = Field(
        None, ge=0, le=100, description="Pesticide applied in kg/ha"
    )
    crop_year: Optional[int] = Field(
        None, ge=2000, le=2100, description="Crop year (e.g. 2026)"
    )
    state: Optional[str] = Field(
        None, description="Indian state name as in training data (e.g. 'Maharashtra')"
    )
    season: Optional[str] = Field(
        None, description="Season: 'Kharif', 'Rabi', 'Whole Year', etc."
    )


@router.get("/predict-yield", tags=["ML"])
async def predict_yield_default():
    """
    Predict sugarcane yield using Maharashtra Kharif defaults.
    No request body needed. Use this for the standard demo prediction (~71 tons/ha).
    """
    try:
        return predict_yield()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/predict-yield", tags=["ML"])
async def predict_yield_custom(req: YieldPredictionRequest):
    """
    Predict sugarcane yield with optional overrides.
    Any field omitted defaults to Maharashtra typical values.
    """
    try:
        return predict_yield(
            annual_rainfall_mm=req.annual_rainfall_mm,
            fertilizer_per_ha_kg=req.fertilizer_per_ha_kg,
            pesticide_per_ha_kg=req.pesticide_per_ha_kg,
            crop_year=req.crop_year,
            state=req.state,
            season=req.season,
        )
    except ValueError as e:
        # Validation errors (e.g. unknown state) → 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
