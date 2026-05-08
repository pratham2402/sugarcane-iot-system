"""
agent.py — AI agent for sugarcane irrigation recommendations.

Reads sensor data + weather + crop info, sends to Gemini, gets back a
structured irrigation recommendation. Saves output to a log file.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from fetch_context import build_context

# -------------------- CONFIG --------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in .env")

# Initialize the Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# Use the current free Gemini Flash model
MODEL_NAME = "gemini-2.5-flash"

# Where to save agent decisions
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# -------------------- PROMPT --------------------

SYSTEM_PROMPT = """You are an expert agronomist AI agent specializing in sugarcane irrigation.
Your role is to analyze field conditions and provide actionable irrigation recommendations
for a sugarcane farmer in Maharashtra, India.

You have access to:
1. Real-time sensor data from the field (soil moisture, soil temp, air temp, humidity)
2. Current weather conditions and 72-hour forecast
3. Crop information (variety, growth stage, days after planting)

IMPORTANT CONTEXT:
- Sugarcane in Maharashtra typically requires 1500-2500mm water across a 12-month growing season.
- Critical water-demand stages: Germination (0-30 days), Tillering (30-130 days), Grand Growth (130-250 days).
- Optimal soil moisture for sugarcane: 60-80% (depending on soil type).
- Below 30% soil moisture for >2 days at tillering stage causes yield loss.
- Note: The sensor's air_temperature/humidity are from the field node location;
  weather_now is from regional weather API. They may differ.

YOUR TASK:
Based on the provided context, decide:
1. Is irrigation needed RIGHT NOW? (yes/no)
2. If yes, how much water in mm? (typical: 15-30mm for tillering stage)
3. When to irrigate? (now / tonight 6pm / tomorrow morning / wait for rain)
4. Brief reasoning (2-3 sentences)
5. Any urgent alerts? (heat stress, water stress, etc.)

OUTPUT FORMAT (JSON only — no markdown, no extra text):
{
  "irrigate_now": true|false,
  "irrigation_amount_mm": <number or null>,
  "irrigation_timing": "<string>",
  "reasoning": "<2-3 sentences>",
  "alerts": ["<alert1>", "<alert2>"],
  "confidence": "high|medium|low"
}
"""


# -------------------- AGENT --------------------

def run_agent():
    """Run one agent cycle: fetch context, query Gemini, save decision."""

    print("=" * 60)
    print("Running AI agent cycle")
    print("=" * 60)

    # Step 1: Build context
    print("\n[1/4] Building context...")
    context = build_context()

    # Step 2: Build the user prompt
    print("\n[2/4] Building prompt for Gemini...")
    user_prompt = f"""Here is the current field context as JSON:

{json.dumps(context, indent=2)}

Based on this context, provide an irrigation recommendation in the JSON format specified."""

    # Step 3: Query Gemini
    print("\n[3/4] Sending to Gemini...")

# Try the main model, fall back to a different one if overloaded
    response = None
    last_error = None

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest"
    ]

    for attempt_num in range(5):
        for model_name in models_to_try:
            try:
                print(f"  Trying model: {model_name} (attempt {attempt_num + 1})")
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.3,
                        response_mime_type="application/json"
                    )
                )
                print(f"  ✓ Got response from {model_name}")
                break  # break out of the model loop
            except Exception as e:
                last_error = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "overloaded" in err_str.lower():
                    print(f"  Model {model_name} is busy, trying next...")
                    continue
                else:
                    raise  # not a "busy" error, raise it

        if response is not None:
            break  # break out of attempt loop

        # All models busy — wait and retry
        import time
        wait_seconds = 10 * (attempt_num + 1)
        print(f"  All models busy. Waiting {wait_seconds}s before retry...")
        time.sleep(wait_seconds)

    if response is None:
        print(f"\nERROR: All retry attempts failed.")
        print(f"Last error: {last_error}")
        raise SystemExit(1)

    raw_text = response.text.strip()

    # Try parsing as JSON
    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError:
        print("WARNING: Gemini did not return valid JSON. Raw response:")
        print(raw_text)
        decision = {"raw_response": raw_text, "parse_error": True}

    # Step 4: Print + save
    print("\n[4/4] Agent decision:")
    print("-" * 60)
    print(json.dumps(decision, indent=2))
    print("-" * 60)

    # Save to log file
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"decision_{timestamp_str}.json"

    log_entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "decision": decision
    }

    with open(log_file, "w") as f:
        json.dump(log_entry, f, indent=2, default=str)

    print(f"\n✅ Decision saved to: {log_file}")
    print(f"\nAgent cycle complete.\n")

    return decision


if __name__ == "__main__":
    run_agent()
