"""
FastAPI Routes: Station endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db

router = APIRouter(prefix="/stations", tags=["Stations"])


@router.get("/")
def list_stations(db: Session = Depends(get_db)):
    """Return all stations with their flood thresholds."""
    rows = db.execute(text(
        "SELECT station_id, station_name, river_basin, latitude, longitude, "
        "minor_flood_level, major_flood_level FROM stations ORDER BY station_name"
    )).fetchall()
    return [
        {
            "station_id": r[0], "station_name": r[1], "river_basin": r[2],
            "latitude": r[3], "longitude": r[4],
            "minor_flood_level": r[5], "major_flood_level": r[6],
        }
        for r in rows
    ]


@router.get("/{station_id}/latest")
def get_latest_observation(station_id: int, db: Session = Depends(get_db)):
    """Return the most recent observation for a station."""
    row = db.execute(text("""
        (SELECT observed_at, water_level, rainfall_mm, 'historical' as src
         FROM historical_observations WHERE station_id = :sid ORDER BY observed_at DESC LIMIT 1)
        UNION ALL
        (SELECT observed_at, water_level, rainfall_mm, 'live' as src
         FROM live_observations WHERE station_id = :sid ORDER BY observed_at DESC LIMIT 1)
        ORDER BY observed_at DESC LIMIT 1
    """), {"sid": station_id}).fetchone()
    if not row:
        return {"error": "No observations found"}
    return {
        "observed_at": row[0].isoformat() if row[0] else None,
        "water_level": row[1],
        "rainfall_mm": row[2],
        "source": row[3],
    }


@router.get("/{station_id}/history")
def get_history(station_id: int, days: int = 7, db: Session = Depends(get_db)):
    """Return recent observed levels for charting."""
    rows = db.execute(text("""
        SELECT observed_at, water_level, rainfall_mm
        FROM historical_observations
        WHERE station_id = :sid AND observed_at >= NOW() - INTERVAL ':days days'
        ORDER BY observed_at ASC
    """.replace(":days", str(min(days, 90)))), {"sid": station_id}).fetchall()
    return [
        {"observed_at": r[0].isoformat() if r[0] else None, "water_level": r[1], "rainfall_mm": r[2]}
        for r in rows
    ]
