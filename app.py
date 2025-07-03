import os
import re
import json
import pytz
import streamlit as st
from datetime import datetime, timedelta
from dateutil.parser import isoparse
from dotenv import load_dotenv
import google.generativeai as genai
from timezonefinder import TimezoneFinder
import geocoder

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

# Show Example Button
if st.button("💡 Show Example"):
    st.session_state["example_input"] = "Schedule a 30-minute meeting with Alex tomorrow at 4 PM in New York"

# User input
user_input = st.text_area(
    "📝 Your Request",
    placeholder="e.g., Schedule a 90-minute call with Meera on July 5 from 4:30am. I am in Tokyo, Japan.",
    value=st.session_state.get("example_input", "")
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
            st.error("❌ Could not find valid JSON in the response.")
            with st.expander("🔍 Debug Info"):
                st.subheader("Raw Gemini Response")
                st.code(raw)
            return None
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        st.error("❌ Failed to parse Gemini response.")
        with st.expander("🔍 Debug Info"):
            st.subheader("Raw Gemini Response")
            st.code(raw)
            st.exception(e)
        return None

def get_timezone_from_location():
    try:
        g = geocoder.ip('me')
        if g.ok and g.latlng:
            lat, lng = g.latlng
            tf = TimezoneFinder()
            tz = tf.timezone_at(lat=lat, lng=lng)
            if tz:
                return tz
    except:
        pass
    return DEFAULT_TIMEZONE

def resolve_relative_date_string(text, base_dt=None, timezone=DEFAULT_TIMEZONE):
    if base_dt is None:
        base_dt = datetime.now(pytz.timezone(timezone))

    replacements = {
        "day after tomorrow": (base_dt + timedelta(days=2)),
        "tomorrow": (base_dt + timedelta(days=1)),
        "today": base_dt,
        "yesterday": (base_dt - timedelta(days=1)),
    }

    for keyword, dt in sorted(replacements.items(), key=lambda x: -len(x[0])):
        formatted = dt.strftime("%B %-d, %Y") if os.name != 'nt' else dt.strftime("%B %#d, %Y")
        text = re.sub(rf'\b{keyword}\b', formatted, text, flags=re.IGNORECASE)

    return text

def build_prompt(request: str) -> str:
    current_year = datetime.now().year
    return f"""
You are an AI that extracts calendar appointments in structured JSON format.

Return ONLY JSON with these fields:
- summary: short title (e.g., "Team Sync")
- start_time: ISO 8601 datetime format
- duration_minutes: integer (duration of the event in minutes)
- timezone: user's timezone like "Asia/Kolkata" if mentioned, else null

Assume:
- Default duration is 30 minutes if not mentioned
- Resolve expressions like "today", "tomorrow", "next Friday" to actual date and time
- Default to current year: {current_year}

Request:
{request}
"""

def extract_appointment_details(prompt: str, retry=False):
    response = model.generate_content(prompt)
    parsed_json = sanitize_and_parse_json(response.text)

    if parsed_json is None:
        return None

    summary = parsed_json.get("summary") or "Meeting"
    start_str = parsed_json.get("start_time")
    duration = parsed_json.get("duration_minutes", 30)
    tz_str = parsed_json.get("timezone")

    if not start_str:
        if not retry:
            st.warning("⚠️ Gemini response was missing a start time. Trying again...")
            return extract_appointment_details(prompt, retry=True)
        else:
            st.error("❌ I couldn’t understand your request.")
            with st.expander("🔍 Debug Info"):
                st.subheader("Parsed JSON (incomplete)")
                st.json(parsed_json)
            return None

    try:
        start = isoparse(start_str)
        end = start + timedelta(minutes=int(duration))
    except Exception as e:
        st.error("❌ Failed to parse time or duration.")
        st.exception(e)
        return None

    return {
        "summary": summary,
        "start": start,
        "end": end,
        "timezone": tz_str,
    }

def looks_valid_request(text: str) -> bool:
    text = text.lower()
    time_pattern = r'\b\d{1,2}(:\d{2})?\s*(am|pm)?\b'
    date_keywords = ['today', 'tomorrow', 'monday', 'tuesday', 'july', 'august', 'next', 'on']
    has_time = re.search(time_pattern, text) or any(word in text for word in ['morning', 'evening', 'noon', 'night'])
    has_date = any(word in text for word in date_keywords)
    return bool(has_time and has_date)

# Booking logic
if st.button("📓 Book Appointment"):
    if not user_input.strip():
        st.warning("⚠️ Please enter a valid appointment request.")
    elif not looks_valid_request(user_input):
        st.info("💡 Your request seems incomplete. Please mention a date and time. For example:\n\n`Schedule a 30-minute meeting with Alex tomorrow at 4 PM in New York`")
    else:
        with st.spinner("🔍 Talking to Gemini..."):
            try:
                cleaned_input = resolve_relative_date_string(user_input)
                prompt = build_prompt(cleaned_input)
                result = extract_appointment_details(prompt)

                if result is None:
                    st.stop()

                summary = result["summary"]
                start = result["start"]
                end = result["end"]
                tz_str = result["timezone"]

                if tz_str:
                    tz = pytz.timezone(tz_str)
                else:
                    tz = pytz.timezone(get_timezone_from_location())

                start = start.astimezone(tz)
                end = end.astimezone(tz)

                if is_time_slot_available(start, end):
                    link = create_event(summary, start, end)
                    st.success("✅ Appointment booked successfully!")
                    st.markdown(f"[📅 View in Calendar]({link})")
                else:
                    found = False
                    for _ in range(5):  # Try up to 5 alternative slots
                        start, end = suggest_next_available_slot(start_from=start)
                        if start and end and is_time_slot_available(start, end):
                            link = create_event(summary, start, end)
                            st.success("✅ Booked next available slot:")
                            st.markdown(f"🕒 {start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%H:%M')} ({start.tzinfo})")
                            st.markdown(f"[📅 View in Calendar]({link})")
                            found = True
                            break
                    if not found:
                        st.error("❌ No available time slots found after checking multiple options.")

            except Exception as e:
                st.error("⚠️ An unexpected error occurred while processing the request.")
                st.exception(e)
