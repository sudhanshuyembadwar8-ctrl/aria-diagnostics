# ARIA — Autonomous Real-time Industrial AI

> **The world's simplest production-grade IIoT AI diagnostics system** — Built with FastAPI, Ollama, WebSockets & SQLite

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-000000?style=flat-square)
![AI](https://img.shields.io/badge/AI-Predictive_Maintenance-818cf8?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

ARIA is a **local AI system** that monitors industrial IoT sensors and uses a **locally-running LLM (Ollama)** to diagnose faults, predict failures before they happen, and answer natural language questions about your factory — all running on your own machine with zero cloud dependency.

---

## What Makes ARIA Different

Most IIoT dashboards just show data. ARIA **understands** it.

| Feature | ARIA | Typical Dashboard |
|---|---|---|
| Anomaly Detection | AI + Statistical | Rule-based only |
| Fault Diagnosis | Natural language LLM | None |
| Failure Prediction | Trend + ML scoring | None |
| Chat Interface | Ask anything | None |
| Cloud Dependency | Zero (100% local) | Usually required |
| LLM | Ollama (runs on your GPU) | None |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ARIA System                          │
│                                                             │
│  sensor_reader.py  ──→  health_scorer.py  ──→  ai_engine.py │
│       │                       │                    │        │
│  [Live IIoT data]    [0-100 Health Score]   [Ollama LLM]   │
│       │                       │                    │        │
│       └───────────────────────┴────────────────────┘        │
│                               │                             │
│                          main.py (FastAPI)                  │
│                          WebSocket Server                   │
│                               │                             │
│                    dashboard/index.html                     │
│                    [Live AI Dashboard + Chat]                │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

- **Machine Health Score** — Weighted 0-100 score across all sensors using boundary distance algorithm
- **Predictive Failure Detection** — Trend analysis predicts sensor failures before they happen, with ETA in minutes  
- **LLM Diagnosis** — Ollama runs locally on your GPU to generate human-readable fault reports
- **Natural Language Chat** — Ask ARIA "What's wrong with my factory?" and get a real answer
- **Auto-Analysis** — ARIA automatically triggers diagnosis every 30 seconds when anomalies detected
- **Reads iiot-sentinel** — Connects directly to iiot-sentinel's SQLite DB if running, otherwise simulates
- **Zero Cloud** — Everything runs locally on your machine

---

## Quickstart

```bash
# 1. Install Ollama (if not installed)
# → ollama.ai → download and install

# 2. Pull a model
ollama pull qwen3:8b   # or llama3.2, mistral, gemma2

# 3. Clone
git clone https://github.com/YOUR_USERNAME/aria-diagnostics.git
cd aria-diagnostics

# 4. Install
pip install -r requirements.txt

# 5. Run
python main.py

# 6. Open
# → http://localhost:8001
```

> ARIA works **without Ollama too** — it falls back to a smart rule-based diagnostic engine automatically.

---

## Project Structure

```
aria-diagnostics/
├── main.py            # FastAPI server + WebSocket + auto-diagnosis loop
├── sensor_reader.py   # Reads from iiot-sentinel DB or physics simulation
├── health_scorer.py   # Weighted health scoring + trend analysis + predictions
├── ai_engine.py       # Ollama LLM integration + rule-based fallback
├── report_store.py    # SQLite persistence for reports and health history
├── dashboard/
│   └── index.html     # Full AI dashboard with chat interface
├── requirements.txt
└── README.md
```

---

## Health Scoring Algorithm

ARIA computes a 0-100 health score per sensor using:

```
score = boundary_distance_score(value, warning_bounds, critical_bounds)
      - trend_penalty(last_30_readings)

boundary score:
  at critical limit  → 0
  at warning limit   → 40  
  at safe center     → 100
```

Sensors are weighted by industrial importance:
- Temperature: 25% | Vibration: 25% | Pressure: 20%
- Humidity: 10% | Power: 10% | Flow Rate: 10%

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, asyncio, WebSockets
- **AI**: Ollama (local LLM — qwen3:8b, llama3.2, mistral, gemma2)
- **Database**: SQLite (reports + health history)
- **Frontend**: Vanilla JS, Chart.js 4, CSS Variables, WebSocket
- **Companion**: Reads live data from [iiot-sentinel](https://github.com/YOUR_USERNAME/iiot-sentinel)

---

## Author

**Sudhanshu Yembadwar** — B.Tech IIoT, SVPCET Nagpur  
*"Machines talk in data. I make them speak in intelligence."*

---

## License

MIT
