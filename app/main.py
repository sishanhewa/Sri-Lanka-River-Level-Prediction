from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import logging

from app.routes import stations, predictions, simulation
from app.services.arcgis_fetcher import fetch_and_process
from app.db.session import get_db

logger = logging.getLogger(__name__)

# Scheduler setup
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the scheduler on app boot
    scheduler.add_job(fetch_and_process, 'cron', minute='*/15', id='arcgis_sync', replace_existing=True)
    scheduler.start()
    yield
    # Shutdown the scheduler on app shutdown
    scheduler.shutdown()

app = FastAPI(
    title="Sri Lanka River Level Prediction API",
    description="Real-time water level predictions and flood risk classification for 39+ river monitoring stations.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS: Allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(stations.router)
app.include_router(predictions.router)
app.include_router(simulation.router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "river-prediction-api"}

@app.post("/ingest/arcgis-sync", tags=["Ingestion"])
def trigger_arcgis_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger an immediate sync of the ArcGIS live data."""
    # We run it synchronously here so the endpoint can return the result
    return fetch_and_process(db=db)

@app.get("/system/logs", tags=["System"])
def get_system_logs(db: Session = Depends(get_db)):
    """Fetch the sync logs for the last 24 hours."""
    from sqlalchemy import text
    logs = db.execute(text("SELECT sync_time, status, inserted_records, predictions_run, message FROM sync_logs WHERE sync_time >= NOW() - INTERVAL '24 HOURS' ORDER BY sync_time DESC LIMIT 100")).fetchall()
    return [{
        "sync_time": l[0],
        "status": l[1],
        "inserted_records": l[2],
        "predictions_run": l[3],
        "message": l[4]
    } for l in logs]
