"""
FastAPI Routes: Prediction endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.services.prediction_service import predict_for_station

router = APIRouter(prefix="/stations", tags=["Predictions"])


@router.get("/{station_id}/prediction")
def get_prediction(station_id: int, db: Session = Depends(get_db)):
    """Return live 3H and 12H predictions for a station."""
    # Fetch station metadata
    station = db.execute(text(
        "SELECT station_name, minor_flood_level, major_flood_level FROM stations WHERE station_id = :sid"
    ), {"sid": station_id}).fetchone()

    if not station:
        return {"error": "Station not found"}

    result = predict_for_station(
        db=db,
        station_id=station_id,
        station_name=station[0],
        minor_flood=station[1] or 0,
        major_flood=station[2] or 0,
    )
    return result


@router.get("/{station_id}/forecast")
def get_forecast(station_id: int, db: Session = Depends(get_db)):
    """Return multi-horizon forecast array."""
    station = db.execute(text(
        "SELECT station_name, minor_flood_level, major_flood_level FROM stations WHERE station_id = :sid"
    ), {"sid": station_id}).fetchone()

    if not station:
        return {"error": "Station not found"}

    result = predict_for_station(
        db=db,
        station_id=station_id,
        station_name=station[0],
        minor_flood=station[1] or 0,
        major_flood=station[2] or 0,
    )
    return {
        "station_id": station_id,
        "station_name": station[0],
        "horizons": [
            {"hours": 3, **result["predictions"]["3h"]},
            {"hours": 12, **result["predictions"]["12h"]},
        ],
        "model_version": result["model_version"],
    }
