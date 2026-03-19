"""
health_scorer.py — Machine Health Score Engine
Computes a 0-100 health score per sensor and overall using:
  - Boundary distance scoring (how close to critical limits)
  - Weighted aggregation (vibration and temperature matter most)
  - Trend analysis (is it getting worse over time?)
  - Confidence bands
"""

from collections import deque
from datetime import datetime


# Rolling history for trend analysis
_history: dict[str, deque] = {}
HISTORY_LEN = 30


def _boundary_score(val: float, meta: dict) -> float:
    """
    Score from 0 (at critical boundary) to 100 (at base/safe center).
    Uses piecewise linear scoring:
      critical boundary → 0
      warning boundary  → 40
      safe center       → 100
    """
    crit_lo = meta["crit_lo"]
    crit_hi = meta["crit_hi"]
    warn_lo = meta["warn_lo"]
    warn_hi = meta["warn_hi"]

    # Safe range center
    center = (warn_lo + warn_hi) / 2

    if val <= crit_lo or val >= crit_hi:
        return 0.0

    if val <= warn_lo:
        # Between critical_lo and warn_lo → 0 to 40
        span = warn_lo - crit_lo
        if span == 0:
            return 40.0
        return 40.0 * (val - crit_lo) / span

    if val >= warn_hi:
        # Between warn_hi and critical_hi → 40 to 0
        span = crit_hi - warn_hi
        if span == 0:
            return 40.0
        return 40.0 * (crit_hi - val) / span

    # Inside warning bounds → 40 to 100
    half = max(center - warn_lo, warn_hi - center)
    if half == 0:
        return 100.0
    dist = abs(val - center)
    return 100.0 - 60.0 * (dist / half)


def _trend_penalty(sensor: str, score: float) -> float:
    """
    If the health score has been consistently dropping over the last
    N readings, apply a penalty (up to -15 points).
    """
    buf = _history.get(sensor)
    if not buf or len(buf) < 5:
        return 0.0

    recent = list(buf)[-5:]
    drops  = sum(1 for i in range(1, len(recent)) if recent[i] < recent[i-1])

    if drops >= 4:    return 15.0   # strong downtrend
    elif drops >= 3:  return 8.0
    elif drops >= 2:  return 3.0
    return 0.0


def _prediction(sensor: str, current_score: float) -> dict:
    """Predict if sensor will hit WARNING in the next N readings."""
    buf = _history.get(sensor)
    if not buf or len(buf) < 10:
        return {"risk": "unknown", "eta_minutes": None}

    scores = list(buf)[-10:]
    slope  = (scores[-1] - scores[0]) / len(scores)   # points per reading

    if slope >= 0 or current_score > 60:
        return {"risk": "low", "eta_minutes": None}

    # How many readings until we hit 40 (warning zone)?
    if slope < 0:
        readings_to_warning = (current_score - 40) / abs(slope)
        minutes = round(readings_to_warning * 0.5)   # ~30s per reading
        if minutes < 5:
            return {"risk": "critical", "eta_minutes": minutes}
        elif minutes < 30:
            return {"risk": "high", "eta_minutes": minutes}
        else:
            return {"risk": "medium", "eta_minutes": minutes}

    return {"risk": "low", "eta_minutes": None}


class HealthScorer:
    def compute(self, readings: dict) -> dict:
        sensor_scores = {}
        weighted_sum  = 0.0
        weight_total  = 0.0

        for key, r in readings.items():
            meta  = r
            score = round(_boundary_score(r["value"], meta), 1)

            # Update history
            if key not in _history:
                _history[key] = deque(maxlen=HISTORY_LEN)
            _history[key].append(score)

            penalty   = _trend_penalty(key, score)
            adj_score = max(0.0, round(score - penalty, 1))
            pred      = _prediction(key, adj_score)

            # Status label
            if adj_score >= 75:   label = "HEALTHY"
            elif adj_score >= 50: label = "DEGRADED"
            elif adj_score >= 25: label = "WARNING"
            else:                 label = "CRITICAL"

            sensor_scores[key] = {
                "score":      adj_score,
                "raw_score":  score,
                "trend_penalty": penalty,
                "label":      label,
                "value":      r["value"],
                "unit":       r["unit"],
                "prediction": pred,
            }

            w = meta.get("weight", 0.1)
            weighted_sum  += adj_score * w
            weight_total  += w

        overall = round(weighted_sum / weight_total, 1) if weight_total else 0.0

        if overall >= 80:   overall_label = "OPERATIONAL"
        elif overall >= 60: overall_label = "DEGRADED"
        elif overall >= 35: overall_label = "AT RISK"
        else:               overall_label = "CRITICAL FAILURE"

        # Count predictions
        high_risk = [k for k, v in sensor_scores.items()
                     if v["prediction"]["risk"] in ("critical", "high")]

        return {
            "overall":       overall,
            "overall_label": overall_label,
            "sensors":       sensor_scores,
            "high_risk":     high_risk,
            "timestamp":     datetime.utcnow().isoformat(),
        }
