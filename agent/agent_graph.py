"""
agent_graph.py — LangGraph-based AI agent for sugarcane irrigation.

Phase 5 status:
  ✓ gather_context
  ✓ check_anomalies (with recent-only filter)
  ✓ get_yield_prediction
  ✓ lookup_crop_stage (minimal inline knowledge base)
  ✓ Phase 4: Gemini decision + validator guardrail
  ✓ Phase 5: action edges (irrigate / wait / alert) with valve actuation
  ⏳ Phase 6: scheduling
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypedDict

import requests
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from google import genai
from google.genai import types

from fetch_context import build_context


# -------------------- CONFIG --------------------

load_dotenv()

BACKEND_URL = "http://localhost:8000"
NODE_ID = "node-01"
ANOMALY_LOOKBACK_DAYS = 7

ANOMALY_RECENT_HOURS = 24
RAIN_SUFFICIENCY_FRACTION = 0.5

# Default irrigation duration if Gemini doesn't specify
DEFAULT_IRRIGATION_DURATION_MIN = 30

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# -------------------- STATE --------------------

class AgentState(TypedDict, total=False):
    context: Optional[dict]
    anomaly_report: Optional[dict]
    yield_prediction: Optional[dict]
    crop_stage_info: Optional[dict]
    decision: Optional[dict]
    valve_action_result: Optional[dict]   # NEW: result of POST /actuate/valve
    error: Optional[str]
    next_action: Optional[str]


# -------------------- MINIMAL KNOWLEDGE BASE --------------------

CROP_STAGES = {
    "germination": {
        "days_range": (0, 30),
        "water_mm_per_week": 15,
        "stress_thresh_pct": 35,
        "notes": "Roots establishing. Avoid waterlogging.",
    },
    "tillering": {
        "days_range": (30, 130),
        "water_mm_per_week": 28,
        "stress_thresh_pct": 30,
        "notes": "Critical stage for shoot multiplication. Water stress >2 days reduces yield.",
    },
    "grand_growth": {
        "days_range": (130, 250),
        "water_mm_per_week": 35,
        "stress_thresh_pct": 40,
        "notes": "Peak biomass accumulation. Highest water demand.",
    },
    "maturation": {
        "days_range": (250, 360),
        "water_mm_per_week": 18,
        "stress_thresh_pct": 25,
        "notes": "Reduce water to encourage sugar accumulation in stalks.",
    },
    "harvest": {
        "days_range": (360, 999),
        "water_mm_per_week": 0,
        "stress_thresh_pct": 0,
        "notes": "Stop irrigation 2-3 weeks before harvest.",
    },
}


def lookup_stage(days_after_planting: int) -> dict:
    """Return the crop stage record for given days."""
    for stage_name, info in CROP_STAGES.items():
        lo, hi = info["days_range"]
        if lo <= days_after_planting < hi:
            return {"stage": stage_name, **info}
    return {"stage": "unknown", "notes": f"No stage matched for {days_after_planting} days."}


# -------------------- GEMINI --------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in .env")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
]

DECISION_SYSTEM_PROMPT = """You are an expert agronomist AI specializing in sugarcane irrigation in Maharashtra, India.

You will receive a JSON object containing:
- sensors: real-time soil moisture, soil temp, air temp, humidity from a field node
- weather_now and weather_forecast_72h: current and forecast weather
- crop_stage_info: current growth stage with water requirement and stress threshold
- yield_prediction: seasonal yield estimate (tons/hectare)

DECISION LOGIC — apply these rules IN ORDER. Do not skip steps.

STEP 1 — Compare numbers carefully:
   Read soil_moisture_pct from sensors.
   Read stress_thresh_pct from crop_stage_info.
   - If soil_moisture_pct > stress_thresh_pct → soil is HEALTHY (above threshold)
   - If soil_moisture_pct <= stress_thresh_pct → soil is STRESSED (at or below threshold)

   IMPORTANT: A higher number means MORE moisture, which is BETTER, not worse.
   Example: moisture 38.9% with threshold 30% → 38.9 > 30 → HEALTHY → no irrigation.
   Example: moisture 25% with threshold 30% → 25 < 30 → STRESSED → consider irrigation.

STEP 2 — Compute forecast rainfall:
   Sum the rainfall in weather_forecast_72h (mm).
   Read water_mm_per_week from crop_stage_info.

STEP 3 — Decide action:
   - If soil is HEALTHY → action = "wait", water_mm = 0, timing = "skip"
   - If soil is STRESSED AND forecast rain >= half of weekly need → action = "wait", reasoning mentions rain
   - If soil is STRESSED AND forecast rain < half of weekly need → action = "irrigate"
   - Only return "alert" if data is contradictory (e.g. moisture is null, sensors say impossible values)

STEP 4 — Compute water_mm if irrigating:
   water_mm should bring soil up but not flood. Typical range 10-30mm per session.
   Hot days (air_temp > 35°C) → use higher end (25-30mm).

OUTPUT FORMAT — return JSON ONLY, no markdown, no extra prose:
{
  "action": "irrigate" | "wait" | "alert",
  "water_mm": <number, 0 if not irrigating>,
  "timing": "now" | "this_evening" | "tomorrow_morning" | "skip",
  "reasoning": "<2-3 plain-language sentences for the farmer. State the actual moisture and threshold values.>",
  "factors": {
    "soil_moisture_pct": <number>,
    "stress_threshold_pct": <number>,
    "forecast_rain_72h_mm": <number>,
    "crop_stage": "<stage name>"
  },
  "confidence": "high" | "medium" | "low"
}

Reread STEP 1 before answering. The most common mistake is reversing the comparison.
"""


# -------------------- NODES --------------------

def gather_context_node(state: AgentState) -> AgentState:
    print("\n[NODE] gather_context")
    try:
        context = build_context()
        print(
            f"  ✓ Context built: sensors={bool(context.get('sensors'))}, "
            f"weather_now={bool(context.get('weather_now'))}, "
            f"forecast={bool(context.get('weather_forecast_72h'))}"
        )
        return {"context": context, "next_action": "continue"}
    except Exception as e:
        msg = f"gather_context failed: {e}"
        print(f"  ✗ {msg}")
        return {"context": None, "error": msg, "next_action": "end"}


def check_anomalies_node(state: AgentState) -> AgentState:
    print("\n[NODE] check_anomalies")
    try:
        r = requests.get(
            f"{BACKEND_URL}/check-anomalies",
            params={"node_id": NODE_ID, "days": ANOMALY_LOOKBACK_DAYS},
            timeout=10,
        )
        r.raise_for_status()
        report = r.json()
        all_anomalies = report.get("anomalies", [])

        print(f"  ✓ {report.get('summary')}")

        now_ts = int(datetime.now(timezone.utc).timestamp())
        recent_cutoff = now_ts - (ANOMALY_RECENT_HOURS * 3600)
        recent = [a for a in all_anomalies if a.get("timestamp", 0) >= recent_cutoff]

        report["recent_anomalies_count"] = len(recent)
        report["recent_anomalies"] = recent
        report["recent_window_hours"] = ANOMALY_RECENT_HOURS

        if recent:
            print(
                f"  → {len(recent)} recent anomaly(ies) within last "
                f"{ANOMALY_RECENT_HOURS}h — routing to alert"
            )
            return {"anomaly_report": report, "next_action": "alert_sensor_issue"}
        else:
            if all_anomalies:
                print(
                    f"  → {len(all_anomalies)} historical anomaly(ies) but none recent — continuing normal flow"
                )
            else:
                print("  → no anomalies — continuing normal flow")
            return {"anomaly_report": report, "next_action": "continue"}

    except Exception as e:
        msg = f"check_anomalies failed: {e}"
        print(f"  ✗ {msg}")
        return {"anomaly_report": None, "error": msg, "next_action": "continue"}


def alert_sensor_issue_node(state: AgentState) -> AgentState:
    print("\n[NODE] alert_sensor_issue")

    report = state.get("anomaly_report") or {}
    recent = report.get("recent_anomalies", [])

    print(f"  ⚠ {len(recent)} recent anomaly(ies):")
    for a in recent[:5]:
        print(f"    - ts={a.get('timestamp')}: {a.get('reasons')}")

    decision = {
        "action": "alert",
        "type": "sensor_issue",
        "summary": (
            f"{len(recent)} anomaly(ies) detected within the last "
            f"{report.get('recent_window_hours')}h."
        ),
        "anomalies": recent,
        "reasoning": (
            "Recent sensor anomalies suggest a hardware or calibration issue. "
            "Recommend manual sensor inspection before acting on readings."
        ),
    }

    return {"decision": decision, "next_action": "end"}


def get_yield_prediction_node(state: AgentState) -> AgentState:
    print("\n[NODE] get_yield_prediction")
    try:
        r = requests.get(f"{BACKEND_URL}/predict-yield", timeout=10)
        r.raise_for_status()
        prediction = r.json()

        print(
            f"  ✓ Predicted yield: "
            f"{prediction.get('predicted_yield_tons_per_hectare')} tons/ha "
            f"(state={prediction.get('inputs', {}).get('state')}, "
            f"season={prediction.get('inputs', {}).get('season')})"
        )

        return {"yield_prediction": prediction, "next_action": "continue"}

    except Exception as e:
        msg = f"get_yield_prediction failed: {e}"
        print(f"  ✗ {msg}")
        return {"yield_prediction": None, "error": msg, "next_action": "continue"}


def lookup_crop_stage_node(state: AgentState) -> AgentState:
    print("\n[NODE] lookup_crop_stage")

    context = state.get("context") or {}
    crop = context.get("crop") or {}
    days = crop.get("days_after_planting", 90)

    info = lookup_stage(days)

    print(f"  ✓ Day {days} → stage '{info['stage']}'")
    print(
        f"    water requirement: {info.get('water_mm_per_week')}mm/week, "
        f"stress threshold: {info.get('stress_thresh_pct')}% moisture"
    )

    return {"crop_stage_info": info, "next_action": "continue"}


def decide_action_node(state: AgentState) -> AgentState:
    """Phase 4: Gemini-powered irrigation decision node."""
    print("\n[NODE] decide_action (Gemini)")

    context = state.get("context") or {}
    decision_input = {
        "sensors": context.get("sensors"),
        "weather_now": context.get("weather_now"),
        "weather_forecast_72h": context.get("weather_forecast_72h"),
        "crop": context.get("crop"),
        "crop_stage_info": state.get("crop_stage_info"),
        "yield_prediction": (state.get("yield_prediction") or {}).get(
            "predicted_yield_tons_per_hectare"
        ),
    }

    user_prompt = (
        "Field context as JSON:\n\n"
        + json.dumps(decision_input, indent=2, default=str)
        + "\n\nReturn only the JSON decision object."
    )

    response = None
    last_error = None

    for attempt in range(3):
        for model_name in GEMINI_MODELS:
            try:
                print(f"  Trying {model_name} (attempt {attempt + 1})...")
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=DECISION_SYSTEM_PROMPT,
                        temperature=0.3,
                        response_mime_type="application/json",
                    ),
                )
                print(f"  ✓ Got response from {model_name}")
                break
            except Exception as e:
                last_error = e
                err = str(e).lower()
                if "503" in err or "unavailable" in err or "overloaded" in err:
                    print(f"    {model_name} busy, trying next...")
                    continue
                else:
                    raise
        if response is not None:
            break
        wait_s = 5 * (attempt + 1)
        print(f"  All models busy, waiting {wait_s}s...")
        time.sleep(wait_s)

    if response is None:
        msg = f"Gemini call failed after retries: {last_error}"
        print(f"  ✗ {msg}")
        return {
            "decision": {
                "action": "alert",
                "type": "agent_failure",
                "reasoning": "Could not reach the LLM — falling back to alert.",
            },
            "error": msg,
            "next_action": "continue",
        }

    raw_text = response.text.strip()
    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError:
        print("  ⚠ Gemini returned non-JSON, wrapping raw text")
        decision = {
            "action": "alert",
            "type": "parse_error",
            "raw_response": raw_text,
            "reasoning": "Gemini did not return valid JSON.",
        }

    print(
        f"  → action: {decision.get('action')}, "
        f"timing: {decision.get('timing')}, "
        f"confidence: {decision.get('confidence')}"
    )
    return {"decision": decision, "next_action": "continue"}


def validate_decision_node(state: AgentState) -> AgentState:
    """Phase 4 guardrail: validate Gemini's decision against deterministic rules."""
    print("\n[NODE] validate_decision (guardrail)")

    decision = state.get("decision") or {}
    sensors = (state.get("context") or {}).get("sensors") or {}
    forecast = (state.get("context") or {}).get("weather_forecast_72h") or {}
    stage_info = state.get("crop_stage_info") or {}

    if decision.get("action") == "alert":
        print("  → already an alert, no validation needed")
        return {"decision": decision, "next_action": "continue"}

    moisture = sensors.get("soil_moisture")
    threshold = stage_info.get("stress_thresh_pct")
    weekly_need_mm = stage_info.get("water_mm_per_week", 0)

    forecast_rain_mm = 0
    if isinstance(forecast, dict):
        if "total_rainfall_mm" in forecast:
            forecast_rain_mm = forecast["total_rainfall_mm"]
        elif "rainfall_mm" in forecast:
            forecast_rain_mm = forecast["rainfall_mm"]
        elif "list" in forecast:
            for block in forecast.get("list", []):
                rain = block.get("rain", {})
                forecast_rain_mm += rain.get("3h", 0) if isinstance(rain, dict) else 0

    if moisture is None or threshold is None:
        print(f"  ⚠ Missing data for validation (moisture={moisture}, threshold={threshold})")
        decision["validator"] = {"status": "skipped", "reason": "missing data"}
        return {"decision": decision, "next_action": "continue"}

    print(f"  Validator inputs:")
    print(f"    soil_moisture     = {moisture}%")
    print(f"    stress_threshold  = {threshold}%")
    print(f"    forecast_rain_72h = {forecast_rain_mm:.1f} mm")
    print(f"    weekly_need       = {weekly_need_mm} mm")

    soil_is_healthy = moisture > threshold
    rain_is_sufficient = forecast_rain_mm >= (weekly_need_mm * RAIN_SUFFICIENCY_FRACTION)

    if soil_is_healthy:
        correct_action = "wait"
        correct_reason = (
            f"Soil moisture {moisture}% is above the stress threshold {threshold}% "
            f"for the {stage_info.get('stage', 'current')} stage. No irrigation needed."
        )
    elif rain_is_sufficient:
        correct_action = "wait"
        correct_reason = (
            f"Soil moisture {moisture}% is below threshold {threshold}%, "
            f"but {forecast_rain_mm:.1f}mm rain forecast in next 72h is sufficient. "
            "Waiting for rain."
        )
    else:
        correct_action = "irrigate"
        correct_reason = (
            f"Soil moisture {moisture}% is at or below stress threshold {threshold}% "
            f"for the {stage_info.get('stage', 'current')} stage, "
            f"and forecast rain ({forecast_rain_mm:.1f}mm) is insufficient. "
            "Irrigation recommended."
        )

    gemini_action = decision.get("action")

    if gemini_action == correct_action:
        print(f"  ✓ Gemini's '{gemini_action}' agrees with rules — no override")
        decision["validator"] = {
            "status": "agreed",
            "rule_action": correct_action,
        }
    else:
        print(f"  ⚠ OVERRIDE: Gemini said '{gemini_action}' but rules say '{correct_action}'")
        decision["validator"] = {
            "status": "overridden",
            "gemini_action": gemini_action,
            "gemini_reasoning": decision.get("reasoning"),
            "rule_action": correct_action,
            "rule_reasoning": correct_reason,
        }
        decision["action"] = correct_action
        decision["reasoning"] = correct_reason
        if correct_action == "wait":
            decision["water_mm"] = 0
            decision["timing"] = "skip"
        decision.setdefault("factors", {})
        decision["factors"]["soil_moisture_pct"] = moisture
        decision["factors"]["stress_threshold_pct"] = threshold
        decision["factors"]["forecast_rain_72h_mm"] = round(forecast_rain_mm, 1)
        decision["factors"]["crop_stage"] = stage_info.get("stage")

    return {"decision": decision, "next_action": "continue"}


# -------------------- PHASE 5: ACTION NODES --------------------

def irrigate_node(state: AgentState) -> AgentState:
    """
    Phase 5: actuate the simulated valve.
    Calls POST /actuate/valve with the agent's water_mm and reasoning.
    """
    print("\n[NODE] irrigate (calling valve)")

    decision = state.get("decision") or {}
    water_mm = decision.get("water_mm") or 0
    reasoning = decision.get("reasoning", "Agent decided to irrigate.")

    # Estimate duration: rough rule of ~1 minute per 1 mm with our pump assumption
    # Real system would compute from flow rate; here we just use a sensible default
    duration_min = max(10, min(60, int(water_mm * 1.2))) if water_mm else DEFAULT_IRRIGATION_DURATION_MIN

    payload = {
        "node_id": NODE_ID,
        "action": "open",
        "duration_min": duration_min,
        "water_mm": water_mm,
        "requested_by": "agent",
        "reasoning": reasoning,
    }

    try:
        r = requests.post(
            f"{BACKEND_URL}/actuate/valve",
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        result = r.json()

        print(f"  ✓ Valve opened: action_id={result.get('action_id')}, "
              f"duration={duration_min} min, water_mm={water_mm}")
        print(f"    backend message: {result.get('message')}")

        return {"valve_action_result": result, "next_action": "end"}

    except Exception as e:
        msg = f"valve actuation failed: {e}"
        print(f"  ✗ {msg}")
        return {
            "valve_action_result": {"status": "failed", "error": str(e)},
            "error": msg,
            "next_action": "end",
        }


def wait_node(state: AgentState) -> AgentState:
    """
    Phase 5: log a 'wait' decision. No backend call needed.
    """
    print("\n[NODE] wait (no irrigation needed)")

    decision = state.get("decision") or {}
    print(f"  ✓ Decision: wait. {decision.get('reasoning', '')}")

    return {"next_action": "end"}


def alert_action_node(state: AgentState) -> AgentState:
    """
    Phase 5: log an 'alert' decision. No backend call needed.
    Could later send notifications via Web Push or Telegram.
    """
    print("\n[NODE] alert_action (notify farmer)")

    decision = state.get("decision") or {}
    alert_type = decision.get("type", "general")
    print(f"  ⚠ Alert type: {alert_type}")
    print(f"    {decision.get('reasoning', '')}")

    return {"next_action": "end"}


# -------------------- ROUTING --------------------

def route_after_anomaly(state: AgentState) -> str:
    return state.get("next_action") or "continue"


def route_after_validation(state: AgentState) -> str:
    """Branch based on the (possibly-overridden) decision action."""
    action = (state.get("decision") or {}).get("action", "alert")
    if action == "irrigate":
        return "irrigate"
    elif action == "wait":
        return "wait"
    else:
        return "alert"


# -------------------- GRAPH --------------------

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("gather_context", gather_context_node)
    graph.add_node("check_anomalies", check_anomalies_node)
    graph.add_node("alert_sensor_issue", alert_sensor_issue_node)
    graph.add_node("get_yield_prediction", get_yield_prediction_node)
    graph.add_node("lookup_crop_stage", lookup_crop_stage_node)
    graph.add_node("decide", decide_action_node)
    graph.add_node("validate_decision", validate_decision_node)
    graph.add_node("irrigate", irrigate_node)
    graph.add_node("wait_for_rain", wait_node)
    graph.add_node("alert_farmer", alert_action_node)

    graph.add_edge(START, "gather_context")
    graph.add_edge("gather_context", "check_anomalies")

    graph.add_conditional_edges(
        "check_anomalies",
        route_after_anomaly,
        {
            "alert_sensor_issue": "alert_sensor_issue",
            "continue": "get_yield_prediction",
            "end": END,
        },
    )

    graph.add_edge("get_yield_prediction", "lookup_crop_stage")
    graph.add_edge("lookup_crop_stage", "decide")
    graph.add_edge("decide", "validate_decision")

    graph.add_conditional_edges(
        "validate_decision",
        route_after_validation,
        {
            "irrigate": "irrigate",
            "wait": "wait_for_rain",
            "alert": "alert_farmer",
        },
    )

    graph.add_edge("alert_sensor_issue", END)
    graph.add_edge("irrigate", END)
    graph.add_edge("wait_for_rain", END)
    graph.add_edge("alert_farmer", END)

    return graph.compile()


# -------------------- RUNNER --------------------

def run_agent_cycle():
    print("=" * 60)
    print("LangGraph Agent — Phase 5 cycle starting")
    print("=" * 60)

    app = build_graph()
    final_state: AgentState = app.invoke({})

    print("\n" + "=" * 60)
    print("FINAL DECISION:")
    print("=" * 60)
    print(json.dumps(final_state.get("decision"), indent=2, default=str))

    valve_result = final_state.get("valve_action_result")
    if valve_result:
        print("\n" + "-" * 60)
        print("VALVE ACTION RESULT:")
        print("-" * 60)
        print(json.dumps(valve_result, indent=2, default=str))

    print("=" * 60)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"langgraph_{timestamp_str}.json"

    with open(log_file, "w") as f:
        json.dump(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "context": final_state.get("context"),
                "anomaly_report": final_state.get("anomaly_report"),
                "yield_prediction": final_state.get("yield_prediction"),
                "crop_stage_info": final_state.get("crop_stage_info"),
                "decision": final_state.get("decision"),
                "valve_action_result": final_state.get("valve_action_result"),
                "error": final_state.get("error"),
            },
            f,
            indent=2,
            default=str,
        )

    print(f"\n✅ Cycle log saved to: {log_file}\n")

    return final_state


if __name__ == "__main__":
    run_agent_cycle()
