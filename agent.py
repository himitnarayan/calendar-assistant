import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
from datetime import datetime, timedelta

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-pro")

# Parse intent from user input
import json
import re

def parse_appointment_request(user_input):
    prompt = f"""
You are an intelligent calendar assistant.

Extract and return ONLY the following fields from the input:
- summary (string)
- start_time (ISO8601 string with Asia/Kolkata timezone)
- end_time (ISO8601 string with Asia/Kolkata timezone)

Input: "{user_input}"

Output ONLY valid JSON like this:
{{
  "summary": "Meeting with John",
  "start_time": "2025-07-02T15:00:00+05:30",
  "end_time": "2025-07-02T16:00:00+05:30"
}}
If data is missing, set values to null.
No markdown, no explanation, JSON only.
"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # ✅ Strip triple backticks and language label
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    print("🔍 Gemini raw response:", response.text)
    try:
        return json.loads(raw)
    except Exception as e:
        print("❌ Parsing error:", e)
        print("🔍 Cleaned response:", raw)
        return None

