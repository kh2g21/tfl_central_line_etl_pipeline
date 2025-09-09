from airflow import DAG
from airflow.decorators import task
from datetime import datetime, timedelta
import requests
import pandas as pd
from sqlalchemy import (
    create_engine, MetaData, Table, Column,
    String, Integer, Float, TIMESTAMP
)
from sqlalchemy.dialects.postgresql import insert
import time

# --- CONFIG ---
DB_URI = "postgresql+psycopg2://postgres:bdjlmttla123@postgres:5432/postgres"
TARGET_LINES = ["central"]  # list of lines to fetch

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# --- SQLAlchemy Table Schema ---
metadata = MetaData()

arrival_fact = Table(
    "arrival_fact", metadata,
    Column("arrival_id", String, primary_key=True),
    Column("route_id", String),
    Column("route_name", String),
    Column("stop_id", String),
    Column("stop_name", String),
    Column("expected_arrival", TIMESTAMP),
    Column("time_to_station", Integer),
    Column("direction", String),
    Column("platform_name", String),
    Column("vehicle_id", String),
    Column("lat", Float),
    Column("lon", Float),
    Column("minutes_to_arrival", Float),
    Column("hour", Integer),
    Column("weekday", Integer),
    Column("ingested_at", TIMESTAMP),
    schema="public"
)

# --- DAG ---
with DAG(
    "tfl_arrivals_multi_line",
    default_args=default_args,
    description="ETL pipeline for TfL arrivals for multiple lines with fixed schema",
    schedule_interval="*/5 * * * *",  # every 5 minutes
    start_date=datetime(2025, 9, 8),
    catchup=False,
    tags=["tfl", "etl", "postgres"],
) as dag:

    @task()
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
                time.sleep(0.5)  # avoid rate limits
            except requests.RequestException:
                continue
        return all_stops

    @task()
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

    @task()
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
        for col in ["expected_arrival", "ingested_at"]:
            df[col] = df[col].astype(str)

        return df.to_dict(orient="records")

    @task()
    def load_data(records):
        if not records:
            return
        df = pd.DataFrame(records)
        df["expected_arrival"] = pd.to_datetime(df["expected_arrival"])
        df["ingested_at"] = pd.to_datetime(df["ingested_at"])

        engine = create_engine(DB_URI)
        with engine.begin() as conn:
            metadata.create_all(conn)
        with engine.begin() as conn:
            for record in df.to_dict(orient="records"):
                stmt = insert(arrival_fact).values(**record)
                stmt = stmt.on_conflict_do_nothing(index_elements=["arrival_id"])
                conn.execute(stmt)

    # --- DAG FLOW ---
    stops = get_all_stops(TARGET_LINES)
    arrivals = extract_data(stops)
    transformed = transform_data(arrivals)
    load_data(transformed)
