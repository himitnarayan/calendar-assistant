import os
import re
import json
import pytz
import streamlit as st
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from dotenv import load_dotenv
import google.generativeai as genai

from calendar_utils import (
    is_time_slot_available,
    create_event,
    suggest_next_available_slot,
)

# Load environment variables
load_dotenv()
DEFAULT_TIMEZONE = "Asia/Kolkata"
CALENDAR_MODEL = "models/gemini-1.5-pro-latest"

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(CALENDAR_MODEL)

# Streamlit UI setup
st.set_page_config(page_title="📅 Appointment Scheduler", layout="centered")
st.title("🤖 AI Appointment Scheduler")
st.markdown("Describe your appointment in natural language, and we'll book it!")

# User input
user_input = st.text_area(
    "📝 Your Request",
    placeholder="e.g., Schedule a 90-minute call with Meera on July 5 from 4:30am. I am in Tokyo, Japan.",
)

# Helpers
def apply_default_timezone_if_missing(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return pytz.timezone(DEFAULT_TIMEZONE).localize(dt)
    return dt

def sanitize_and_parse_json(raw: str):
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No valid JSON object found in response.")
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response: {e}")

def build_prompt(request: str) -> str:
    current_year = datetime.now().year
    return f"""
You are an AI that extracts calendar appointments in structured JSON.

Return ONLY JSON (no text). The JSON must include:
- summary: short title
- start_time: in ISO format
- end_time: in ISO format
- timezone: user timezone (like 'Asia/Tokyo') if given, else return null

If the user did not mention a year, default to the current year: {current_year}.
Request:
{request}
"""

# Booking handler
if st.button("📆 Book Appointment"):
    if not user_input.strip():
        st.warning("Please enter a valid request.")
    else:
        with st.spinner("🔍 Talking to Gemini..."):
            try:
                response = model.generate_content(build_prompt(user_input))
                parsed_json = sanitize_and_parse_json(response.text)

                summary = parsed_json.get("summary")
                start = isoparse(parsed_json.get("start_time"))
                end = isoparse(parsed_json.get("end_time"))
                tz_str = parsed_json.get("timezone")

                if tz_str:
                    tz = pytz.timezone(tz_str)
                    start = start.astimezone(tz)
                    end = end.astimezone(tz)
                else:
                    start = apply_default_timezone_if_missing(start)
                    end = apply_default_timezone_if_missing(end)

                if summary and start and end:
                    if is_time_slot_available(start, end):
                        link = create_event(summary, start, end)
                        st.success("✅ Appointment booked successfully!")
                        st.markdown(f"[📅 View in Calendar]({link})")
                    else:
                        st.warning("⚠️ That time is already booked. Searching for next available slot...")
                        start, end = suggest_next_available_slot(start_from=start)
                        if start and end:
                            link = create_event(summary, start, end)
                            st.success("✅ Booked next available slot:")
                            st.markdown(f"🕒 {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%H:%M')} ({start.tzinfo})")
                            st.markdown(f"[📅 View in Calendar]({link})")
                        else:
                            st.error("❌ No available slots found in the next 7 days.")
                else:
                    st.error("❌ Gemini response was incomplete or invalid.")

            except Exception as e:
                st.error("⚠️ Gemini response couldn't be processed.")
                st.exception(e)
