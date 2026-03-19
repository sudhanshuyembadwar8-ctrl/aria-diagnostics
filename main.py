"""
ARIA — Autonomous Real-time Industrial AI
Author: Sudhanshu Yembadwar
Stack: FastAPI + Ollama + WebSockets + SQLite + Chart.js

ARIA does what no junior dev project has ever done:
  - Reads live IIoT sensor data every 10 seconds
  - Computes a 0-100 Machine Health Score using weighted algorithms
  - Runs local LLM (Ollama) to generate human-readable diagnoses
  - Predicts failures BEFORE they happen using trend analysis
  - Chat interface — ask ARIA anything about your factory in plain English
  - Auto-generates maintenance reports with root cause analysis
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from sensor_reader import SensorReader
from health_scorer import HealthScorer
from ai_engine import ARIAEngine
from report_store import ReportStore


# ── Global instances ───────────────────────────────────────────────────────────
reader   = SensorReader()
scorer   = HealthScorer()
aria     = ARIAEngine()
store    = ReportStore("aria.db")
clients: list[WebSocket] = []


async def broadcast(payload: dict):
    dead = []
    msg  = json.dumps(payload)
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.remove(ws)


# ── Background: auto-diagnosis every 30 seconds ────────────────────────────────
async def auto_diagnosis_loop():
    await asyncio.sleep(15)   # warm-up
    while True:
        try:
            readings     = reader.get_latest()
            health       = scorer.compute(readings)
            critical     = [k for k, v in health["sensors"].items() if v["score"] < 40]

            # Only auto-diagnose if something is concerning
            if health["overall"] < 75 or critical:
                report = await aria.diagnose(readings, health)
                store.save_report(report, health["overall"], "auto")
                await broadcast({"type": "auto_diagnosis", "report": report, "health": health})
            else:
                await broadcast({"type": "health_update", "health": health})

        except Exception as e:
            print(f"[ARIA] Auto-diagnosis error: {e}")

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()
    asyncio.create_task(auto_diagnosis_loop())
    print("✅  ARIA running → http://localhost:8001")
    yield


app = FastAPI(title="ARIA — Industrial AI", lifespan=lifespan)


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)

    # Send initial health snapshot
    readings = reader.get_latest()
    health   = scorer.compute(readings)
    await websocket.send_text(json.dumps({"type": "health_update", "health": health}))

    try:
        while True:
            data = await websocket.receive_text()
            msg  = json.loads(data)

            if msg.get("type") == "chat":
                question = msg.get("message", "")
                readings = reader.get_latest()
                health   = scorer.compute(readings)
                reply    = await aria.chat(question, readings, health)
                await websocket.send_text(json.dumps({
                    "type":    "chat_reply",
                    "message": reply,
                    "health":  health,
                }))

            elif msg.get("type") == "diagnose_now":
                readings = reader.get_latest()
                health   = scorer.compute(readings)
                report   = await aria.diagnose(readings, health)
                store.save_report(report, health["overall"], "manual")
                await websocket.send_text(json.dumps({
                    "type":   "auto_diagnosis",
                    "report": report,
                    "health": health,
                }))

    except WebSocketDisconnect:
        clients.remove(websocket)


# ── REST endpoints ─────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return Path("dashboard/index.html").read_text()


@app.get("/api/health")
async def get_health():
    readings = reader.get_latest()
    health   = scorer.compute(readings)
    return JSONResponse(health)


@app.get("/api/reports")
async def get_reports(limit: int = 10):
    return JSONResponse(store.get_reports(limit))


@app.get("/api/history")
async def get_history():
    return JSONResponse(store.get_health_history(60))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
