import urllib.request
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

# Assuming getting DB session is available or we use direct engine
from app.db.session import SessionLocal
from app.services.prediction_service import predict_for_station

logger = logging.getLogger(__name__)

ARCGIS_URL = "https://services3.arcgis.com/J7ZFXmR8rSmQ3FGf/arcgis/rest/services/gauges_2_view/FeatureServer/0/query?where=1%3D1&outFields=*&f=json"

def clean_name(name: str) -> str:
    """Normalize names to match the database exactly (e.g. ignoring spaces/brackets)."""
    import re
    n = name.lower()
    match = re.search(r'\\((.*?)\\)', n)
    if match:
        n = match.group(1).strip()
    return n.strip().replace(" ", "")

def fetch_and_process(db: Session = None):
    """
    1. Fetch live features from ArcGIS.
    2. Map gauge names to DB `station_id`.
    3. Insert into `live_observations`.
    4. Trigger 3H / 12H predictions for each updated station.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        req = urllib.request.Request(ARCGIS_URL, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read())
        features = data.get("features", [])
        
        # Pull all valid stations from DB to memory for matching
        db_stations = db.execute(text("SELECT station_id, station_name FROM stations")).fetchall()
        db_station_map = {clean_name(row[1]): row for row in db_stations}
        db_raw_names = {row[1].lower(): row for row in db_stations}

        inserted_count = 0
        predictions_updated = 0
        now = datetime.utcnow()

        for f in features:
            attr = f.get("attributes", {})
            gauge = attr.get("gauge")
            water_level = attr.get("water_level")
            rainfall = attr.get("rain_fall")

            # Validate reading exists
            if not gauge or (water_level is None and rainfall is None):
                continue
            
            # Map station name using strict matching logic developed earlier
            gauge_clean = clean_name(str(gauge))
            matched_row = None
            
            # 1. Exact or partial raw match
            for raw_name, row in db_raw_names.items():
                if raw_name in gauge.lower() or str(gauge).lower() in raw_name:
                    matched_row = row
                    break
            
            # 2. Clean Name match
            if not matched_row:
                for clean_db_name, row in db_station_map.items():
                    if clean_db_name in gauge_clean or gauge_clean in clean_db_name:
                        matched_row = row
                        break
            
            if not matched_row:
                continue
                
            station_id, station_name = matched_row

            # Insert into live_observations
            try:
                # Basic dedup check (we just enforce uniqueness by time in DB)
                db.execute(
                    text("""
                        INSERT INTO live_observations (station_id, observed_at, water_level, rainfall_mm, raw_payload, source)
                        VALUES (:sid, :obs_at, :wl, :rain, :raw, 'arcgis')
                        ON CONFLICT (station_id, observed_at) DO NOTHING
                    """),
                    {
                        "sid": station_id,
                        "obs_at": now,
                        "wl": water_level,
                        "rain": rainfall,
                        "raw": json.dumps(attr)
                    }
                )
                db.commit()
                inserted_count += 1
                
                # Fetch threshold limits for this station perfectly
                station_metadata = db.execute(text(
                    "SELECT minor_flood_level, major_flood_level FROM stations WHERE station_id = :sid"
                ), {"sid": station_id}).fetchone()

                # Generate live predictions for the newly added data!
                result = predict_for_station(
                    db=db,
                    station_id=station_id,
                    station_name=station_name,
                    minor_flood=station_metadata[0] or 0.0,
                    major_flood=station_metadata[1] or 0.0
                )
                
                if "error" not in result:
                    # Write predictions to log table
                    db.execute(text("""
                        INSERT INTO predictions (station_id, prediction_time, horizon_hours, predicted_water_level, risk_class, model_version)
                        VALUES (:sid, :ptime, 3, :p3wl, :p3rk, :mver),
                               (:sid, :ptime, 12, :p12wl, :p12rk, :mver)
                    """), {
                        "sid": station_id,
                        "ptime": result["prediction_time"],
                        "p3wl": result["predictions"]["3h"]["predicted_water_level"],
                        "p3rk": result["predictions"]["3h"]["risk_class"],
                        "p12wl": result["predictions"]["12h"]["predicted_water_level"],
                        "p12rk": result["predictions"]["12h"]["risk_class"],
                        "mver": "v4_dual_horizon"
                    })
                    db.commit()
                    predictions_updated += 1
                    
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to process {station_name}: {e}")

        logger.info(f"ArcGIS Sync Complete: Inserted {inserted_count} new records and ran {predictions_updated} predictions")
        return {"status": "success", "inserted_records": inserted_count, "predictions_run": predictions_updated}

    except Exception as e:
        logger.error(f"ArcGIS fetcher crashed: {e}")
        return {"status": "error", "message": str(e)}
    
    finally:
        if close_db:
            db.close()
