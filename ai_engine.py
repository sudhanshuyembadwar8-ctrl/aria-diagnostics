"""
ai_engine.py — ARIA's Brain: Ollama LLM Integration
Uses local Ollama (qwen3:8b or any available model) to:
  1. Generate human-readable fault diagnoses
  2. Predict root causes
  3. Suggest maintenance actions
  4. Answer natural language questions about the factory
Falls back to rule-based responses if Ollama is not running.
"""

import json
import re
import httpx
from datetime import datetime


OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELS      = ["qwen3:8b", "llama3.2", "llama3", "mistral", "gemma2"]  # tries in order


async def _get_available_model() -> str | None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get("http://localhost:11434/api/tags")
            if res.status_code == 200:
                names = [m["name"] for m in res.json().get("models", [])]
                for m in MODELS:
                    if any(m in n for n in names):
                        return next(n for n in names if m in n)
                return names[0] if names else None
    except Exception:
        return None


async def _ollama(prompt: str, system: str, model: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(OLLAMA_URL, json={
                "model":  model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 400},
            })
            if res.status_code == 200:
                raw = res.json().get("response", "")
                # Strip <think>...</think> blocks (qwen3 thinking mode)
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                return raw
    except Exception as e:
        print(f"[ARIA] Ollama error: {e}")
    return None


def _rule_based_diagnosis(readings: dict, health: dict) -> str:
    """Fallback when Ollama is offline — smart rule-based diagnosis."""
    overall = health["overall"]
    sensors = health["sensors"]
    issues  = [(k, v) for k, v in sensors.items() if v["score"] < 60]
    issues.sort(key=lambda x: x[1]["score"])

    if not issues:
        return (f"All systems nominal. Overall health score: {overall}/100. "
                f"No anomalies detected. Factory floor operating within safe parameters.")

    lines = [f"ARIA Diagnosis — Health Score: {overall}/100\n"]
    for sensor, data in issues[:3]:
        val   = data["value"]
        unit  = data["unit"]
        score = data["score"]
        label = data["label"]

        if sensor == "temperature":
            if val > 90:
                lines.append(f"TEMPERATURE [{val}{unit}] — {label}: Overheating detected. "
                             f"Possible cause: coolant failure, blocked ventilation, or excessive load. "
                             f"Recommend: inspect cooling system immediately.")
            else:
                lines.append(f"TEMPERATURE [{val}{unit}] — {label}: Below optimal range. "
                             f"Possible cause: heating element fault or ambient temperature drop.")

        elif sensor == "vibration":
            if val > 4.5:
                lines.append(f"VIBRATION [{val}{unit}] — {label}: Abnormal vibration detected. "
                             f"Possible cause: bearing wear, rotor imbalance, or loose mounting. "
                             f"Recommend: schedule bearing inspection within 48 hours.")
            else:
                lines.append(f"VIBRATION [{val}{unit}] — {label}: Vibration within range.")

        elif sensor == "pressure":
            if val > 6.0:
                lines.append(f"PRESSURE [{val}{unit}] — {label}: Overpressure condition. "
                             f"Possible cause: blockage in discharge line or valve failure. "
                             f"Recommend: check relief valve and pipeline for obstructions.")
            elif val < 2.5:
                lines.append(f"PRESSURE [{val}{unit}] — {label}: Underpressure. "
                             f"Possible cause: pump cavitation or fluid leak. Inspect seals.")

        elif sensor == "flow_rate":
            lines.append(f"FLOW RATE [{val}{unit}] — {label}: Flow deviation detected. "
                         f"Possible cause: partial blockage, valve position, or pump degradation.")

        elif sensor == "power":
            lines.append(f"POWER [{val}{unit}] — {label}: Power consumption anomaly. "
                         f"Possible cause: motor winding issue or increased mechanical load.")

        elif sensor == "humidity":
            lines.append(f"HUMIDITY [{val}{unit}] — {label}: Humidity out of range. "
                         f"Risk of corrosion or electrical faults if sustained.")

    pred_sensors = [k for k, v in sensors.items() if v["prediction"]["risk"] in ("critical","high")]
    if pred_sensors:
        lines.append(f"\nPREDICTIVE ALERT: {', '.join(pred_sensors)} trending toward failure. "
                     f"Proactive maintenance recommended.")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are ARIA (Autonomous Real-time Industrial AI), an expert industrial IoT engineer 
and predictive maintenance specialist. You analyze sensor data from factory equipment and provide 
precise, actionable diagnoses.

Your responses must be:
- Technical but understandable
- Specific to the sensor values given
- Include probable root causes
- Include recommended actions with urgency level
- Concise (under 200 words)
- Never generic — always reference the actual values

Format: Start with the most critical issue, then others. End with a maintenance priority."""


class ARIAEngine:

    def __init__(self):
        self._model: str | None = None

    async def _ensure_model(self) -> str | None:
        if not self._model:
            self._model = await _get_available_model()
        return self._model

    async def diagnose(self, readings: dict, health: dict) -> str:
        model = await self._ensure_model()

        sensor_summary = "\n".join([
            f"  {k}: {r['value']}{r['unit']} — status: {r['status']} — health score: {health['sensors'][k]['score']}/100"
            for k, r in readings.items()
        ])

        prompt = f"""Current factory sensor readings:
{sensor_summary}

Overall machine health score: {health['overall']}/100 — {health['overall_label']}

High-risk sensors (predicted to fail soon): {', '.join(health['high_risk']) or 'none'}

Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Provide a complete diagnostic report with:
1. Primary fault identification
2. Root cause analysis  
3. Recommended actions (with urgency: IMMEDIATE / 24H / 7 DAYS)
4. Predicted consequences if ignored"""

        if model:
            result = await _ollama(prompt, SYSTEM_PROMPT, model)
            if result:
                return result

        return _rule_based_diagnosis(readings, health)

    async def chat(self, question: str, readings: dict, health: dict) -> str:
        model = await self._ensure_model()

        sensor_summary = ", ".join([
            f"{k}={r['value']}{r['unit']}({r['status']})"
            for k, r in readings.items()
        ])

        prompt = f"""Current sensor data: {sensor_summary}
Overall health: {health['overall']}/100 ({health['overall_label']})

User question: {question}

Answer as ARIA, the factory AI. Be specific, technical, and reference actual sensor values."""

        if model:
            result = await _ollama(prompt, SYSTEM_PROMPT, model)
            if result:
                return result

        # Rule-based chat fallback
        q = question.lower()
        overall = health["overall"]
        sensors = health["sensors"]

        if any(w in q for w in ["health", "status", "how", "overall"]):
            return (f"Current overall health score is {overall}/100 — {health['overall_label']}. "
                    f"{'All sensors within safe bounds.' if overall > 75 else 'Some sensors require attention.'}")

        for sensor in readings:
            if sensor.replace("_", " ") in q or sensor in q:
                r = readings[sensor]
                s = sensors[sensor]
                return (f"{sensor.replace('_',' ').title()} is currently {r['value']}{r['unit']} "
                        f"with a health score of {s['score']}/100 ({s['label']}). "
                        f"Prediction risk: {s['prediction']['risk']}.")

        if any(w in q for w in ["worst", "critical", "danger", "bad"]):
            worst = min(sensors.items(), key=lambda x: x[1]["score"])
            return (f"The worst performing sensor is {worst[0]} with a health score of "
                    f"{worst[1]['score']}/100 ({worst[1]['label']}). "
                    f"Current value: {worst[1]['value']}{worst[1]['unit']}.")

        if any(w in q for w in ["maintenance", "fix", "repair", "action"]):
            issues = [(k,v) for k,v in sensors.items() if v["score"] < 60]
            if not issues:
                return "No maintenance actions required. All systems are healthy."
            worst = min(issues, key=lambda x: x[1]["score"])
            return (f"Priority maintenance: {worst[0].replace('_',' ')} sensor showing "
                    f"{worst[1]['label']} status at {worst[1]['score']}/100. "
                    f"Recommend inspection within {'1 hour' if worst[1]['score'] < 25 else '24 hours'}.")

        return (f"I'm ARIA, your factory AI. Current health: {overall}/100. "
                f"Ask me about any specific sensor, maintenance needs, or fault analysis.")
