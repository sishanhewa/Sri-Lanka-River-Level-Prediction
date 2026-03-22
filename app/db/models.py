from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base


class Station(Base):
    __tablename__ = "stations"

    station_id = Column(Integer, primary_key=True, index=True)
    station_name = Column(String(100), unique=True, nullable=False)
    river_basin = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    minor_flood_level = Column(Float)
    major_flood_level = Column(Float)
    upstream_station_id = Column(Integer, ForeignKey("stations.station_id"))
    created_at = Column(DateTime, server_default=func.now())


class HistoricalObservation(Base):
    __tablename__ = "historical_observations"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.station_id"), nullable=False)
    observed_at = Column(DateTime, nullable=False)
    water_level = Column(Float)
    rainfall_mm = Column(Float)
    rainfall_type = Column(String(50))
    status = Column(String(50))
    source = Column(String(50), default="historical_csv")


class LiveObservation(Base):
    __tablename__ = "live_observations"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.station_id"), nullable=False)
    observed_at = Column(DateTime, nullable=False)
    water_level = Column(Float)
    rainfall_mm = Column(Float)
    status = Column(String(50))
    raw_payload = Column(Text)
    source = Column(String(50), default="rivernet")
    created_at = Column(DateTime, server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.station_id"), nullable=False)
    prediction_time = Column(DateTime, nullable=False)
    horizon_hours = Column(Integer, nullable=False)
    predicted_water_level = Column(Float, nullable=False)
    risk_class = Column(String(20), nullable=False)
    model_version = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    scenario_name = Column(String(200))
    rainfall_input_json = Column(Text)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_runs.run_id"), nullable=False)
    station_id = Column(Integer, ForeignKey("stations.station_id"), nullable=False)
    horizon_hours = Column(Integer, nullable=False)
    predicted_water_level = Column(Float, nullable=False)
    risk_class = Column(String(20))
