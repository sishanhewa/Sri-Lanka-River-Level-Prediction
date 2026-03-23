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
    """Return recent observed levels for charting, merging historical and live."""
    safe_days = str(min(days, 90))
    # Query both historical and live tables so the chart includes real-time telemetry
    query = """
        SELECT observed_at, water_level, rainfall_mm FROM (
            SELECT observed_at, water_level, rainfall_mm
            FROM historical_observations
            WHERE station_id = :sid AND observed_at >= NOW() - INTERVAL '{days} days'
            UNION ALL
            SELECT observed_at, water_level, rainfall_mm
            FROM live_observations
            WHERE station_id = :sid AND observed_at >= NOW() - INTERVAL '{days} days'
        ) combined
        ORDER BY observed_at ASC
    """.replace("{days}", safe_days)
    
    rows = db.execute(text(query), {"sid": station_id}).fetchall()
    return [
        {"observed_at": r[0].isoformat() if r[0] else None, "water_level": r[1], "rainfall_mm": r[2]}
        for r in rows
    ]

@router.get("/status/all")
def get_all_station_status(db: Session = Depends(get_db)):
    """Return all stations with their latest observation, prediction risk, and 24H rainfall."""
    rows = db.execute(text("""
        WITH LatestObs AS (
            SELECT station_id, water_level, rainfall_mm,
                   ROW_NUMBER() OVER(PARTITION BY station_id ORDER BY observed_at DESC) as rn
            FROM live_observations
        ),
        Rainfall24H AS (
            SELECT station_id, SUM(rainfall_mm) as rain_24h
            FROM live_observations
            WHERE observed_at >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '24 hours'
            GROUP BY station_id
        ),
        LatestPred AS (
            SELECT station_id, predicted_water_level, risk_class, horizon_hours,
                   ROW_NUMBER() OVER(PARTITION BY station_id, horizon_hours ORDER BY prediction_time DESC) as rn
            FROM predictions
        )
        SELECT s.station_id, s.station_name, s.river_basin, s.minor_flood_level, s.major_flood_level,
               lo.water_level, lo.rainfall_mm, COALESCE(r24.rain_24h, 0) as rain_24h,
               p12.risk_class as risk_12h, p12.predicted_water_level as pred_12h,
               p3.risk_class as risk_3h, p3.predicted_water_level as pred_3h
        FROM stations s
        LEFT JOIN LatestObs lo ON s.station_id = lo.station_id AND lo.rn = 1
        LEFT JOIN Rainfall24H r24 ON s.station_id = r24.station_id
        LEFT JOIN LatestPred p12 ON s.station_id = p12.station_id AND p12.horizon_hours = 12 AND p12.rn = 1
        LEFT JOIN LatestPred p3 ON s.station_id = p3.station_id AND p3.horizon_hours = 3 AND p3.rn = 1
        ORDER BY s.station_name
    """)).fetchall()
    
    return [
        {
            "station_id": r[0], "station_name": r[1], "river_basin": r[2],
            "minor_flood_level": r[3], "major_flood_level": r[4],
            "current_level": r[5], "rainfall_mm": r[6], "rainfall_24h": r[7],
            "risk_12h": r[8], "pred_12h": r[9],
            "risk_3h": r[10], "pred_3h": r[11]
        }
        for r in rows
    ]


@router.get("/{station_id}/accuracy")
def get_forecast_accuracy(station_id: int, hours: int = 48, db: Session = Depends(get_db)):
    """
    Compare past AI predictions against actual water levels recorded at the target time.
    For each past prediction (3H and 12H), looks up the closest actual observation
    within ±30 minutes of the prediction's target timestamp.
    Returns null for 'actual' when no observation exists (API was offline).
    """
    safe_hours = str(min(hours, 168))
    sql = text("""
        WITH preds AS (
            SELECT 
                prediction_time,
                horizon_hours,
                predicted_water_level,
                prediction_time + (horizon_hours * INTERVAL '1 hour') AS target_time
            FROM predictions
            WHERE station_id = :sid
              AND prediction_time >= (NOW() AT TIME ZONE 'UTC') - INTERVAL ':h hours'
        ),
        all_obs AS (
            SELECT observed_at, water_level FROM historical_observations WHERE station_id = :sid
            UNION ALL
            SELECT observed_at, water_level FROM live_observations WHERE station_id = :sid
        )
        SELECT 
            p.prediction_time,
            p.target_time,
            p.horizon_hours,
            p.predicted_water_level,
            o.water_level AS actual_water_level
        FROM preds p
        LEFT JOIN LATERAL (
            SELECT water_level
            FROM all_obs
            WHERE ABS(EXTRACT(EPOCH FROM (observed_at - p.target_time))) < 1800
            ORDER BY ABS(EXTRACT(EPOCH FROM (observed_at - p.target_time))) ASC
            LIMIT 1
        ) o ON true
        ORDER BY p.target_time ASC, p.horizon_hours ASC
    """.replace(":h", safe_hours))
    rows = db.execute(sql, {"sid": station_id}).fetchall()

    result = []
    for r in rows:
        predicted = r[3]
        actual = r[4]
        error = round(abs(predicted - actual), 4) if actual is not None else None
        result.append({
            "prediction_time": r[0].isoformat() if r[0] else None,
            "target_time": r[1].isoformat() if r[1] else None,
            "horizon_hours": r[2],
            "predicted": round(predicted, 4) if predicted else None,
            "actual": round(actual, 4) if actual else None,
            "error": error,
        })
    return result

