#!/usr/bin/env python3
"""
Generate a sample inverter_logs.db SQLite database with 1-row-per-minute telemetry data
over a 7-day period for testing text-to-SQL capabilities.
"""

import argparse
import os
import sys
import sqlite3
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "inverter_logs.db"

def resolve_db_path(cli_path: str | None = None) -> Path:
    if cli_path:
        return Path(cli_path).resolve()
    env_path = os.getenv("INVERTER_DB_PATH") or os.getenv("DB_PATH")
    if env_path:
        return Path(env_path).resolve()
    return DEFAULT_DB_PATH.resolve()

def init_db(db_path: Path):
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE inverter_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        grid_voltage REAL,
        ac_input_freq REAL,
        output_voltage REAL,
        output_freq REAL,
        output_power_w REAL,
        pv_voltage REAL,
        solar_output_w REAL,
        battery_voltage REAL,
        battery_soc REAL,
        battery_charging_current REAL,
        battery_discharge_current REAL,
        inverter_status TEXT NOT NULL
    );
    """)

    cursor.execute("CREATE INDEX idx_telemetry_timestamp ON inverter_telemetry(timestamp);")
    cursor.execute("CREATE INDEX idx_telemetry_status ON inverter_telemetry(inverter_status);")

    # Generate 7 days of 1-minute telemetry data (~10,080 rows)
    now = datetime.now(timezone.utc).replace(microsecond=0, second=0)
    start_time = now - timedelta(days=7)

    rows = []
    current_time = start_time

    while current_time <= now:
        ts_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        hour = current_time.hour

        # Solar output simulation (peaks around midday)
        if 6 <= hour <= 18:
            sun_intensity = max(0.0, 1.0 - ((hour - 12) / 6.0) ** 2)
            solar_output = round(sun_intensity * 3000 + random.uniform(-100, 100), 1)
            pv_voltage = round(120 + sun_intensity * 80 + random.uniform(-5, 5), 1)
        else:
            solar_output = 0.0
            pv_voltage = round(random.uniform(0, 5), 1)

        # Grid status / frequency anomaly simulation (occasional grid fault or generator struggle)
        grid_available = random.random() > 0.05
        if grid_available:
            grid_voltage = round(random.uniform(225.0, 235.0), 1)
            # Occasional frequency jitter (generator struggling e.g. < 49.5 or > 50.5 Hz)
            if random.random() < 0.03:
                ac_input_freq = round(random.choice([48.8, 49.1, 49.3, 50.8, 51.2]), 2)
            else:
                ac_input_freq = round(random.uniform(49.7, 50.3), 2)
        else:
            grid_voltage = 0.0
            ac_input_freq = 0.0

        output_voltage = round(random.uniform(228.0, 232.0), 1)
        output_freq = 50.0
        output_power = round(random.uniform(300, 2500), 1)

        # Battery state simulation
        if solar_output > output_power:
            battery_soc = min(100.0, round(50.0 + (hour - 6) * 5.0 + random.uniform(-2, 2), 1))
            battery_voltage = round(51.2 + (battery_soc / 100.0) * 3.2, 2)
            battery_charging_current = round((solar_output - output_power) / battery_voltage, 1)
            battery_discharge_current = 0.0
        else:
            battery_soc = max(20.0, round(80.0 - (hour % 12) * 3.0 + random.uniform(-2, 2), 1))
            battery_voltage = round(48.0 + (battery_soc / 100.0) * 4.0, 2)
            battery_charging_current = 0.0
            battery_discharge_current = round((output_power - solar_output) / battery_voltage, 1)

        # Status logic
        if not grid_available:
            status = "Inverting (Off-Grid)"
        elif ac_input_freq < 49.5 or ac_input_freq > 50.5:
            status = "Warning: Grid Freq Anomaly"
        elif solar_output > 500:
            status = "Solar Charging & Bypass"
        else:
            status = "Line Mode (Grid)"

        rows.append((
            ts_str, grid_voltage, ac_input_freq, output_voltage, output_freq,
            output_power, pv_voltage, solar_output, battery_voltage, battery_soc,
            battery_charging_current, battery_discharge_current, status
        ))

        current_time += timedelta(minutes=1)

    cursor.executemany("""
    INSERT INTO inverter_telemetry (
        timestamp, grid_voltage, ac_input_freq, output_voltage, output_freq,
        output_power_w, pv_voltage, solar_output_w, battery_voltage, battery_soc,
        battery_charging_current, battery_discharge_current, inverter_status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)

    conn.commit()
    conn.close()
    print(f"Database successfully generated at {db_path} with {len(rows)} telemetry rows.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sample telemetry SQLite database")
    parser.add_argument("--db-path", "--db", "-d", dest="db_path", type=str, default=None, help="Output path for SQLite database file")
    args = parser.parse_args()

    db_target = resolve_db_path(args.db_path)
    init_db(db_target)
