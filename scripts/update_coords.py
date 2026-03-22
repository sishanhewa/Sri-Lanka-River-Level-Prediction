import os
import urllib.request
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "river_prediction")

def clean_name(name):
    import re
    n = name.lower()
    match = re.search(r'\\((.*?)\\)', n)
    if match:
        n = match.group(1).strip()
    return n.strip().replace(" ", "")

print("Fetching ArcGIS coordinates...")
url = "https://services3.arcgis.com/J7ZFXmR8rSmQ3FGf/arcgis/rest/services/gauges_2_view/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    data = json.loads(urllib.request.urlopen(req).read())
    features = data.get('features', [])
    
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, dbname=DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT station_id, station_name FROM stations")
    db_stations = cur.fetchall()
    
    updated = 0
    for db_id, db_name in db_stations:
        db_clean = clean_name(db_name)
        
        # Find matching feature
        match_geom = None
        for f in features:
            gauge_raw = f['attributes'].get('gauge')
            if not gauge_raw: continue
            ar_clean = clean_name(str(gauge_raw))
            
            if db_clean in ar_clean or ar_clean in db_clean or db_name.lower() in str(gauge_raw).lower():
                geom = f.get('geometry')
                if geom and 'x' in geom and 'y' in geom:
                    match_geom = geom
                    break
                    
        if match_geom:
            cur.execute(
                "UPDATE stations SET longitude = %s, latitude = %s WHERE station_id = %s",
                (match_geom['x'], match_geom['y'], db_id)
            )
            updated += 1
            
    conn.commit()
    conn.close()
    print(f"Successfully backfilled {updated} out of {len(db_stations)} stations with exact GPS coordinates!")

except Exception as e:
    print(f"Error: {e}")
