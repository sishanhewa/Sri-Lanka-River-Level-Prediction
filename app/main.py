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
    scheduler.add_job(fetch_and_process, 'interval', minutes=15, id='arcgis_sync', replace_existing=True)
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
