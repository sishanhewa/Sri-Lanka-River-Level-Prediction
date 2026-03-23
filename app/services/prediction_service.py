"""
Prediction Service: Loads trained XGBoost models and generates predictions with risk classification.
"""
import os
import json
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
ENCODING_MAP_PATH = os.path.join(BASE_DIR, "models", "station_encoding_map.json")

# Load models once at import time
model_3h = joblib.load(MODEL_3H_PATH)
model_12h = joblib.load(MODEL_12H_PATH)

# Load station encoding lookup
with open(ENCODING_MAP_PATH, 'r') as f:
    STATION_ENCODING_MAP = json.load(f)

# Build a fuzzy lookup (lowercase, no spaces, th→t normalization) for name matching
_FUZZY_ENCODING_MAP = {}
for name, encodings in STATION_ENCODING_MAP.items():
    key = name.lower().replace(" ", "").replace("th", "t")
    _FUZZY_ENCODING_MAP[key] = encodings
    # Also index by raw lowercase
    _FUZZY_ENCODING_MAP[name.lower()] = encodings


def resolve_station_encoding(station_name: str) -> dict:
    """Resolve the correct station/basin/rainfall/status encodings for a given station name."""
    # Exact match first
    if station_name in STATION_ENCODING_MAP:
        return STATION_ENCODING_MAP[station_name]
    
    # Fuzzy match
    fuzzy_key = station_name.lower().replace(" ", "").replace("th", "t")
    if fuzzy_key in _FUZZY_ENCODING_MAP:
        return _FUZZY_ENCODING_MAP[fuzzy_key]
    
    # Partial containment match
    for key, encodings in _FUZZY_ENCODING_MAP.items():
        if fuzzy_key in key or key in fuzzy_key:
            return encodings
    
    # Fallback — return zeros (model will regress to global mean)
    return {"station_encoded": 0, "river_basin_encoded": 0, "rainfall_type_encoded": 0, "status_encoded": 0}


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
                        station_encoded: int = None, river_basin_encoded: int = None,
                        rainfall_type_encoded: int = None, status_encoded: int = None) -> dict:
    """Generate 3H and 12H predictions for a single station."""
    
    # Auto-resolve encodings from the lookup map if not explicitly provided
    resolved = resolve_station_encoding(station_name)
    if station_encoded is None:
        station_encoded = resolved["station_encoded"]
    if river_basin_encoded is None:
        river_basin_encoded = resolved["river_basin_encoded"]
    if rainfall_type_encoded is None:
        rainfall_type_encoded = resolved["rainfall_type_encoded"]
    if status_encoded is None:
        status_encoded = resolved["status_encoded"]
    
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

    # Store predictions in the DB
    try:
        for horizon, pred_val, risk in [(3, pred_3h, classify_risk(pred_3h, minor_flood, major_flood)),
                                         (12, pred_12h, classify_risk(pred_12h, minor_flood, major_flood))]:
            db.execute(text("""
                INSERT INTO predictions (station_id, prediction_time, horizon_hours, predicted_water_level, risk_class, model_version)
                VALUES (:sid, :pt, :h, :pwl, :rc, 'v4_dual_horizon')
            """), {"sid": station_id, "pt": datetime.utcnow(), "h": horizon, "pwl": round(pred_val, 4), "rc": risk})
        db.commit()
    except Exception:
        db.rollback()

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
        "encodings_used": {
            "station_encoded": station_encoded,
            "river_basin_encoded": river_basin_encoded,
        }
    }
