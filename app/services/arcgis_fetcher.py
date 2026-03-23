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

ARCGIS_URL = "https://services3.arcgis.com/J7ZFXmR8rSmQ3FGf/arcgis/rest/services/gauges_2_view/FeatureServer/0/query?where=1%3D1&outFields=*&orderByFields=CreationDate%20DESC&f=json"

def clean_name(name: str) -> str:
    """Normalize names to match the database exactly."""
    import re
    n = name.lower()
    match = re.search(r'\\((.*?)\\)', n)
    if match:
        n = match.group(1).strip()
    return n.strip().replace(" ", "").replace("th", "t")

def fetch_and_process(db: Session = None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        db_stations = db.execute(text("SELECT station_id, station_name FROM stations")).fetchall()
        db_station_map = {clean_name(row[1]): row for row in db_stations}
        db_raw_names = {row[1].lower(): row for row in db_stations}

        inserted_count = 0
        predictions_updated = 0
        
        updated_station_ids = set()
        matched_station_info = {}

        offset = 0
        has_more = True
        all_features = []
        
        while has_more and offset < 5000:
            paginated_url = f"{ARCGIS_URL}&resultOffset={offset}&resultRecordCount=1000"
            req = urllib.request.Request(paginated_url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read())
            features = data.get("features", [])
            
            if not features:
                break
                
            all_features.extend(features)
            has_more = data.get("exceededTransferLimit", len(features) == 1000)
            offset += 1000

        for f in all_features:
            attr = f.get("attributes", {})
            gauge = attr.get("gauge")
            water_level = attr.get("water_level")
            rainfall = attr.get("rain_fall")
            creation_date_ms = attr.get("CreationDate") or attr.get("EditDate")
            
            # Default to now if API failed to provide time, else convert ms to datetime
            if creation_date_ms:
                try:
                    obs_at = datetime.utcfromtimestamp(creation_date_ms / 1000.0)
                except:
                    obs_at = datetime.utcnow()
            else:
                obs_at = datetime.utcnow()

            # Validate reading exists
            if not gauge or (water_level is None and rainfall is None):
                continue
            
            gauge_clean = clean_name(str(gauge))
            matched_row = None
            
            for raw_name, row in db_raw_names.items():
                if raw_name in gauge.lower() or str(gauge).lower() in raw_name:
                    matched_row = row
                    break
            
            if not matched_row:
                for clean_db_name, row in db_station_map.items():
                    if clean_db_name in gauge_clean or gauge_clean in clean_db_name:
                        matched_row = row
                        break
            
            if not matched_row:
                continue
                
            station_id, station_name = matched_row
            matched_station_info[station_id] = matched_row

            # Insert into live_observations
            try:
                db.execute(
                    text("""
                        INSERT INTO live_observations (station_id, observed_at, water_level, rainfall_mm, raw_payload, source)
                        VALUES (:sid, :obs_at, :wl, :rain, :raw, 'arcgis')
                        ON CONFLICT (station_id, observed_at) DO NOTHING
                    """),
                    {
                        "sid": station_id,
                        "obs_at": obs_at,
                        "wl": water_level,
                        "rain": rainfall,
                        "raw": json.dumps(attr)
                    }
                )
                inserted_count += 1
                updated_station_ids.add(station_id)
            except Exception as e:
                logger.error(f"Failed to insert {gauge}: {e}")
                db.rollback()
                continue
                
        db.commit()

        # Run AI predictions ONLY ONCE for each modified station
        for sid in updated_station_ids:
            try:
                s_name = matched_station_info[sid][1]
                station_meta = db.execute(text("SELECT minor_flood_level, major_flood_level FROM stations WHERE station_id = :sid"), {"sid": sid}).fetchone()
                
                result = predict_for_station(
                    db=db,
                    station_id=sid,
                    station_name=s_name,
                    minor_flood=station_meta[0] or 0.0,
                    major_flood=station_meta[1] or 0.0
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

        # Log the sync event to the database
        db.execute(text("""
            INSERT INTO sync_logs (status, inserted_records, predictions_run, message) 
            VALUES ('success', :inserted, :preds, :msg)
        """), {
            "inserted": inserted_count,
            "preds": predictions_updated,
            "msg": f"Inserted {inserted_count} new records and ran {predictions_updated} predictions"
        })
        db.commit()

        logger.info(f"ArcGIS Sync Complete: Inserted {inserted_count} new records and ran {predictions_updated} predictions")
        return {"status": "success", "inserted_records": inserted_count, "predictions_run": predictions_updated}

    except Exception as e:
        logger.error(f"ArcGIS fetcher crashed: {e}")
        if db:
            try:
                db.execute(text("""
                    INSERT INTO sync_logs (status, inserted_records, predictions_run, message) 
                    VALUES ('error', 0, 0, :msg)
                """), {"msg": str(e)})
                db.commit()
            except Exception as log_e:
                logger.error(f"Failed to write error to sync_logs: {log_e}")
                
        return {"status": "error", "message": str(e)}
    
    finally:
        if close_db:
            db.close()
