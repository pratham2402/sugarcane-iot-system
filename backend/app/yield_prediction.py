"""
Yield prediction module — loads V2 XGBoost model trained on Kaggle Indian crop dataset.
"""

import json
import os
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd

# Module-level cache — loaded once at import
_MODEL = None
_FEATURE_COLUMNS = None
_METADATA = None

# Maharashtra defaults (from agronomy literature)
DEFAULTS = {
    "annual_rainfall_mm": 1100,
    "fertilizer_per_ha_kg": 140,
    "pesticide_per_ha_kg": 0.27,
    "state": "Maharashtra",
    "season": "Kharif     ",  # 5 trailing spaces — preserved from training
}

BACKEND_DIR = Path(__file__).resolve().parent.parent  # /home/pi/sugarcane-iot-system-main/backend


def load_model():
    """Load model artefacts. Idempotent — safe to call multiple times."""
    global _MODEL, _FEATURE_COLUMNS, _METADATA

    if _MODEL is not None:
        return  # already loaded

    model_path = BACKEND_DIR / "yield_model.pkl"
    cols_path = BACKEND_DIR / "feature_columns.pkl"
    meta_path = BACKEND_DIR / "model_metadata.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}")
    if not cols_path.exists():
        raise FileNotFoundError(f"Feature columns file not found at {cols_path}")

    with open(model_path, "rb") as f:
        _MODEL = pickle.load(f)
    with open(cols_path, "rb") as f:
        _FEATURE_COLUMNS = pickle.load(f)

    if meta_path.exists():
        with open(meta_path, "r") as f:
            _METADATA = json.load(f)
    else:
        _METADATA = {}


def build_feature_vector(
    annual_rainfall_mm: float = None,
    fertilizer_per_ha_kg: float = None,
    pesticide_per_ha_kg: float = None,
    crop_year: int = None,
    state: str = None,
    season: str = None,
) -> pd.DataFrame:
    """Build a single-row DataFrame matching the model's 37 feature columns."""
    load_model()

    # Apply defaults for missing inputs
    annual_rainfall_mm = annual_rainfall_mm if annual_rainfall_mm is not None else DEFAULTS["annual_rainfall_mm"]
    fertilizer_per_ha_kg = fertilizer_per_ha_kg if fertilizer_per_ha_kg is not None else DEFAULTS["fertilizer_per_ha_kg"]
    pesticide_per_ha_kg = pesticide_per_ha_kg if pesticide_per_ha_kg is not None else DEFAULTS["pesticide_per_ha_kg"]
    crop_year = crop_year if crop_year is not None else datetime.now().year
    state = state if state is not None else DEFAULTS["state"]
    season = season if season is not None else DEFAULTS["season"]

    # Initialize all 37 features to 0
    features = {col: 0 for col in _FEATURE_COLUMNS}

    # Numerical features
    features["Annual_Rainfall"] = annual_rainfall_mm
    features["Fertilizer_per_ha"] = fertilizer_per_ha_kg
    features["Pesticide_per_ha"] = pesticide_per_ha_kg
    features["Crop_Year"] = crop_year

    # One-hot: state
    state_col = f"State_{state}"
    if state_col in features:
        features[state_col] = 1
    else:
        raise ValueError(f"Unknown state: {state}. Must be one of the 27 trained states.")

    # One-hot: season (note trailing spaces from training)
    season_col = f"Season_{season}"
    if season_col in features:
        features[season_col] = 1
    else:
        # Try with trailing spaces if user passed "Kharif" without padding
        for col in _FEATURE_COLUMNS:
            if col.startswith("Season_") and col.replace("Season_", "").strip() == season.strip():
                features[col] = 1
                season_col = col
                break
        else:
            raise ValueError(f"Unknown season: '{season}'.")

    # Build single-row DataFrame in correct column order
    df = pd.DataFrame([features])[_FEATURE_COLUMNS]
    return df


def predict_yield(
    annual_rainfall_mm: float = None,
    fertilizer_per_ha_kg: float = None,
    pesticide_per_ha_kg: float = None,
    crop_year: int = None,
    state: str = None,
    season: str = None,
) -> dict:
    """Predict sugarcane yield (tons/ha) using V2 model."""
    load_model()

    X = build_feature_vector(
        annual_rainfall_mm=annual_rainfall_mm,
        fertilizer_per_ha_kg=fertilizer_per_ha_kg,
        pesticide_per_ha_kg=pesticide_per_ha_kg,
        crop_year=crop_year,
        state=state,
        season=season,
    )

    prediction = float(_MODEL.predict(X)[0])

    return {
        "predicted_yield_tons_per_hectare": round(prediction, 2),
        "inputs": {
            "annual_rainfall_mm": annual_rainfall_mm if annual_rainfall_mm is not None else DEFAULTS["annual_rainfall_mm"],
            "fertilizer_per_ha_kg": fertilizer_per_ha_kg if fertilizer_per_ha_kg is not None else DEFAULTS["fertilizer_per_ha_kg"],
            "pesticide_per_ha_kg": pesticide_per_ha_kg if pesticide_per_ha_kg is not None else DEFAULTS["pesticide_per_ha_kg"],
            "crop_year": crop_year if crop_year is not None else datetime.now().year,
            "state": state if state is not None else DEFAULTS["state"],
            "season": (season if season is not None else DEFAULTS["season"]).strip(),
        },
        "model_info": {
    "type": "XGBRegressor V2",
    "features_count": len(_FEATURE_COLUMNS),
    "cv_r2": round(_METADATA.get("cv_r2_mean", 0), 3),
    "cv_r2_std": round(_METADATA.get("cv_r2_std", 0), 3),
    "test_r2": round(_METADATA.get("test_r2", 0), 3),
    "rmse_tons_per_ha": round(_METADATA.get("rmse_tons_per_ha", 0), 2),
    "mae_tons_per_ha": round(_METADATA.get("mae_tons_per_ha", 0), 2),
    "training_samples": _METADATA.get("training_samples", "N/A"),
    "trained_on": "Kaggle Indian Crop Yield dataset",
        },
        "confidence_note": (
    f"Cross-validated R²={round(_METADATA.get('cv_r2_mean',0),2)}, "
    f"test R²={round(_METADATA.get('test_r2',0),2)}, "
    f"RMSE={round(_METADATA.get('rmse_tons_per_ha',0),2)} tons/ha. "
    "Predictions are seasonal estimates based on rainfall, fertilizer, pesticide use, state and season."
),
    }
