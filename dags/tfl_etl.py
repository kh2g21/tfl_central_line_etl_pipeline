import requests
import pandas as pd
from datetime import datetime
import time
from sqlalchemy import create_engine, MetaData
from sqlalchemy.dialects.postgresql import insert

DB_URI = "postgresql+psycopg2://postgres:************@postgres:5432/postgres"

def get_all_stops(lines):
    all_stops = []
    for line in lines:
        url = f"https://api.tfl.gov.uk/Line/{line}/StopPoints"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            stops = resp.json()
            all_stops.extend([
                {"id": stop["id"], "name": stop["commonName"], "lat": stop.get("lat"), "lon": stop.get("lon")}
                for stop in stops
            ])
            time.sleep(0.5)
        except requests.RequestException:
            continue
    return all_stops

def extract_data(stops):
    all_arrivals = []
    for stop in stops:
        url = f"https://api.tfl.gov.uk/StopPoint/{stop['id']}/Arrivals"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            arrivals = resp.json()
            for a in arrivals:
                a["stop_id"] = stop["id"]
                a["stop_name"] = stop["name"]
                a["lat"] = stop["lat"]
                a["lon"] = stop["lon"]
            all_arrivals.extend(arrivals)
            time.sleep(0.5)
        except requests.RequestException:
            continue
    return all_arrivals

def transform_data(arrivals):
    if not arrivals:
        return None
    df = pd.DataFrame(arrivals)
    if df.empty:
        return None

    df = df[[
        "id", "lineId", "lineName", "stop_id", "stop_name",
        "expectedArrival", "timeToStation", "towards",
        "platformName", "vehicleId", "lat", "lon"
    ]]
    df.rename(columns={
        "id": "arrival_id",
        "lineId": "route_id",
        "lineName": "route_name",
        "expectedArrival": "expected_arrival",
        "towards": "direction",
        "platformName": "platform_name",
        "vehicleId": "vehicle_id",
        "timeToStation": "time_to_station"
    }, inplace=True)

    df["expected_arrival"] = pd.to_datetime(df["expected_arrival"])
    df["minutes_to_arrival"] = (df["expected_arrival"] - pd.Timestamp.utcnow()).dt.total_seconds() / 60
    df["hour"] = df["expected_arrival"].dt.hour
    df["weekday"] = df["expected_arrival"].dt.weekday
    df["ingested_at"] = datetime.utcnow()

    df.drop_duplicates(subset="arrival_id", inplace=True)

    return df

def load_data(df, arrival_fact, metadata):
    if df is None or df.empty:
        return

    engine = create_engine(DB_URI)
    with engine.begin() as conn:
        metadata.create_all(conn)
    with engine.begin() as conn:
        for record in df.to_dict(orient="records"):
            stmt = insert(arrival_fact).values(**record)
            stmt = stmt.on_conflict_do_nothing(index_elements=["arrival_id"])
            conn.execute(stmt)
