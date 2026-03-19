"""
sensor_reader.py — Reads sensor data from iiot-sentinel SQLite DB.
Falls back to physics simulation if DB not found.
This means ARIA works standalone OR connected to iiot-sentinel.
"""

import math
import os
import random
import sqlite3
import time
from datetime import datetime


SENTINEL_DB = os.path.join(os.path.dirname(__file__), "..", "iiot-sentinel", "sentinel.db")

SENSOR_META = {
    "temperature": {"unit": "°C",    "warn_lo": 40,  "warn_hi": 90,  "crit_lo": 20,  "crit_hi": 110, "weight": 0.25},
    "humidity":    {"unit": "%RH",   "warn_lo": 30,  "warn_hi": 75,  "crit_lo": 15,  "crit_hi": 90,  "weight": 0.10},
    "pressure":    {"unit": "bar",   "warn_lo": 2.5, "warn_hi": 6.0, "crit_lo": 1.0, "crit_hi": 8.0, "weight": 0.20},
    "vibration":   {"unit": "mm/s",  "warn_lo": 0,   "warn_hi": 4.5, "crit_lo": 0,   "crit_hi": 7.1, "weight": 0.25},
    "power":       {"unit": "kW",    "warn_lo": 5,   "warn_hi": 30,  "crit_lo": 2,   "crit_hi": 40,  "weight": 0.10},
    "flow_rate":   {"unit": "L/min", "warn_lo": 50,  "warn_hi": 130, "crit_lo": 20,  "crit_hi": 160, "weight": 0.10},
}

# Simulation state
_sim = {k: {"v": {"temperature":72,"humidity":55,"pressure":4.2,"vibration":2.1,"power":18.5,"flow_rate":85}[k], "t":0}
        for k in SENSOR_META}


def _simulate_all() -> dict:
    readings = {}
    for key, meta in SENSOR_META.items():
        s = _sim[key]
        s["t"] += 1
        drift = 8 * math.sin(s["t"] / 120 * math.pi) * {"temperature":1,"humidity":0.75,"pressure":0.0625,"vibration":0.1875,"power":0.375,"flow_rate":1.25}[key]
        s["v"] += ({"temperature":72,"humidity":55,"pressure":4.2,"vibration":2.1,"power":18.5,"flow_rate":85}[key] + drift - s["v"]) * 0.15
        s["v"] += random.gauss(0, {"temperature":0.4,"humidity":0.5,"pressure":0.05,"vibration":0.15,"power":0.3,"flow_rate":0.8}[key])
        val = round(s["v"], 2)

        if val <= meta["crit_lo"] or val >= meta["crit_hi"]:   status = "CRITICAL"
        elif val <= meta["warn_lo"] or val >= meta["warn_hi"]: status = "WARNING"
        else:                                                   status = "NORMAL"

        readings[key] = {"value": val, "unit": meta["unit"], "status": status, **meta}

    return readings


def _read_from_sentinel() -> dict | None:
    """Try to read latest values from iiot-sentinel's SQLite DB."""
    if not os.path.exists(SENTINEL_DB):
        return None
    try:
        conn = sqlite3.connect(SENTINEL_DB)
        conn.row_factory = sqlite3.Row
        cur  = conn.cursor()
        readings = {}
        for key, meta in SENSOR_META.items():
            row = cur.execute(
                "SELECT value, unit, status FROM sensor_log WHERE sensor=? ORDER BY id DESC LIMIT 1",
                (key,)
            ).fetchone()
            if row:
                readings[key] = {"value": row["value"], "unit": row["unit"], "status": row["status"], **meta}
        conn.close()
        return readings if len(readings) == len(SENSOR_META) else None
    except Exception:
        return None


class SensorReader:
    def get_latest(self) -> dict:
        live = _read_from_sentinel()
        return live if live else _simulate_all()

    @property
    def source(self) -> str:
        return "iiot-sentinel" if os.path.exists(SENTINEL_DB) else "simulation"
