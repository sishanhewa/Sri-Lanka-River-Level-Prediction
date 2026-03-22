"""
Database Setup & Historical Data Backfill Script.
Creates the database, runs schema.sql, and loads the CSV into PostgreSQL.
"""
import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "river_prediction")

STATION_MAPPING = {
    'NagalagamStreet': 'Nagalagam Street',
    'Kalawellawa(Millakanda)': 'Kalawellawa (Millakanda)',
}


def create_database():
    """Create the database if it does not exist."""
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname="postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
    if not cur.fetchone():
        cur.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"Database '{DB_NAME}' created.")
    else:
        print(f"Database '{DB_NAME}' already exists.")
    cur.close()
    conn.close()


def run_schema():
    """Execute schema.sql to create all tables."""
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME)
    cur = conn.cursor()
    schema_path = os.path.join(os.path.dirname(__file__), "..", "app", "db", "schema.sql")
    with open(schema_path, "r") as f:
        cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()
    print("Schema created successfully.")


def backfill_stations_and_history():
    """Load raw CSV, extract unique stations, insert into stations table, then backfill observations."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "extracted_data_new copy 3.csv")
    df = pd.read_csv(csv_path)

    # Unify station names
    df['station'] = df['station'].replace(STATION_MAPPING)
    df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
    df = df.dropna(subset=['datetime'])

    for col in ['water_level', 'rainfall_mm', 'minor_flood_level', 'major_flood_level']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME)
    cur = conn.cursor()

    # 1. Insert unique stations
    stations = df.groupby('station').agg({
        'river_basin': 'first',
        'minor_flood_level': 'first',
        'major_flood_level': 'first',
    }).reset_index()

    station_id_map = {}
    for _, row in stations.iterrows():
        cur.execute(
            """INSERT INTO stations (station_name, river_basin, minor_flood_level, major_flood_level)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (station_name) DO NOTHING
               RETURNING station_id""",
            (row['station'], row.get('river_basin'), row.get('minor_flood_level'), row.get('major_flood_level'))
        )
        result = cur.fetchone()
        if result:
            station_id_map[row['station']] = result[0]
        else:
            cur.execute("SELECT station_id FROM stations WHERE station_name = %s", (row['station'],))
            station_id_map[row['station']] = cur.fetchone()[0]

    conn.commit()
    print(f"Inserted {len(station_id_map)} stations.")

    # 2. Bulk insert historical observations
    inserted = 0
    for _, row in df.iterrows():
        sid = station_id_map.get(row['station'])
        if not sid:
            continue
        try:
            cur.execute(
                """INSERT INTO historical_observations (station_id, observed_at, water_level, rainfall_mm, rainfall_type, status)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (station_id, observed_at) DO NOTHING""",
                (sid, row['datetime'], row.get('water_level'), row.get('rainfall_mm'),
                 row.get('rainfall_type'), row.get('status'))
            )
            inserted += 1
        except Exception as e:
            pass  # Skip problematic rows

        if inserted % 5000 == 0:
            conn.commit()

    conn.commit()
    cur.close()
    conn.close()
    print(f"Backfilled {inserted} historical observations.")


if __name__ == "__main__":
    print("=== Step 1: Creating Database ===")
    create_database()
    print("=== Step 2: Running Schema ===")
    run_schema()
    print("=== Step 3: Backfilling Historical Data ===")
    backfill_stations_and_history()
    print("=== Done! Database is ready. ===")
