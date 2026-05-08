"""
test_gemini.py — Verify Gemini API key works (using new google-genai package).
"""

import os
from dotenv import load_dotenv
from google import genai

# Load API keys from .env file
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env file")
    exit(1)

print(f"API key loaded (starts with: {api_key[:10]}...)")

# Create Gemini client with our API key
client = genai.Client(api_key=api_key)

# Send a test prompt using the current free model
print("\nSending test prompt to Gemini...")
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello! Are you working? Reply in one short sentence."
)

print("\nGemini's response:")
print(response.text)
print("\n✅ Gemini API is working!")
