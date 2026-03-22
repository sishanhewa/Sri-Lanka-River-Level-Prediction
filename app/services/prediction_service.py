"""
Prediction Service: Loads trained XGBoost models and generates predictions with risk classification.
"""
import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.feature_service import generate_features

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_3H_PATH = os.path.join(BASE_DIR, "models", "waterlevel_xgb_3h.joblib")
MODEL_12H_PATH = os.path.join(BASE_DIR, "models", "waterlevel_xgb_12h.joblib")

# Load models once at import time
model_3h = joblib.load(MODEL_3H_PATH)
model_12h = joblib.load(MODEL_12H_PATH)


def classify_risk(predicted_level: float, minor_threshold: float, major_threshold: float) -> str:
    """Classify flood risk based on predicted water level vs thresholds."""
    if major_threshold and predicted_level >= major_threshold:
        return "Major Flood"
    elif minor_threshold and predicted_level >= minor_threshold:
        return "Minor Flood"
    return "Normal"


def get_recent_observations(db: Session, station_id: int, limit: int = 30) -> pd.DataFrame:
    """Pull the most recent observations for a station from both historical and live tables."""
    query = text("""
        (SELECT observed_at as datetime, water_level, rainfall_mm, 'historical' as src
         FROM historical_observations WHERE station_id = :sid ORDER BY observed_at DESC LIMIT :lim)
        UNION ALL
        (SELECT observed_at as datetime, water_level, rainfall_mm, 'live' as src
         FROM live_observations WHERE station_id = :sid ORDER BY observed_at DESC LIMIT :lim)
        ORDER BY datetime DESC LIMIT :lim
    """)
    result = db.execute(query, {"sid": station_id, "lim": limit}).fetchall()
    if not result:
        return pd.DataFrame()
    return pd.DataFrame(result, columns=["datetime", "water_level", "rainfall_mm", "src"])


def predict_for_station(db: Session, station_id: int, station_name: str,
                        minor_flood: float, major_flood: float,
                        station_encoded: int = 0, river_basin_encoded: int = 0,
                        rainfall_type_encoded: int = 0, status_encoded: int = 0) -> dict:
    """Generate 3H and 12H predictions for a single station."""
    recent = get_recent_observations(db, station_id)
    if recent.empty:
        return {"error": f"No observations found for station {station_name}"}

    recent['minor_flood_level'] = minor_flood
    recent['major_flood_level'] = major_flood
    recent['station_encoded'] = station_encoded
    recent['river_basin_encoded'] = river_basin_encoded
    recent['rainfall_type_encoded'] = rainfall_type_encoded
    recent['status_encoded'] = status_encoded

    feature_vector = generate_features(recent)

    pred_3h = float(model_3h.predict(feature_vector)[0])
    pred_12h = float(model_12h.predict(feature_vector)[0])

    return {
        "station_id": station_id,
        "station_name": station_name,
        "prediction_time": datetime.utcnow().isoformat(),
        "predictions": {
            "3h": {
                "predicted_water_level": round(pred_3h, 4),
                "risk_class": classify_risk(pred_3h, minor_flood, major_flood),
            },
            "12h": {
                "predicted_water_level": round(pred_12h, 4),
                "risk_class": classify_risk(pred_12h, minor_flood, major_flood),
            },
        },
        "model_version": "v4_dual_horizon",
    }
