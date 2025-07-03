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

def resolve_relative_date_string(text, base_dt=None, timezone=DEFAULT_TIMEZONE):
    if base_dt is None:
        base_dt = datetime.now(pytz.timezone(timezone))

    replacements = {
        "day after tomorrow": (base_dt + timedelta(days=2)).date().isoformat(),
        "tomorrow": (base_dt + timedelta(days=1)).date().isoformat(),
        "today": base_dt.date().isoformat(),
        "yesterday": (base_dt - timedelta(days=1)).date().isoformat(),
    }

    # Handle longest phrases first
    for keyword, value in sorted(replacements.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf'\b{keyword}\b', value, text, flags=re.IGNORECASE)

    return text

def build_prompt(request: str) -> str:
    current_year = datetime.now().year
    return f"""
You are an AI that extracts calendar appointments in structured JSON.

Return ONLY JSON (no text). The JSON must include:
- summary: short title
- start_time: in ISO format (resolve any relative expressions like "tomorrow", "next Monday", etc.)
- end_time: in ISO format
- timezone: user timezone (like 'Asia/Tokyo') if given, else return null

If the user did not mention a year, default to the current year: {current_year}.
If the user used a relative date like “today” or “tomorrow”, resolve it to an actual date.

Request:
{request}
"""

def extract_appointment_details(prompt: str, retry=False):
    response = model.generate_content(prompt)
    parsed_json = sanitize_and_parse_json(response.text)

    if parsed_json is None:
        return None

    summary = parsed_json.get("summary")
    start_str = parsed_json.get("start_time")
    end_str = parsed_json.get("end_time")
    tz_str = parsed_json.get("timezone")

    if not all([summary, start_str, end_str]):
        if not retry:
            st.warning("⚠️ Gemini response was incomplete. Trying again...")
            return extract_appointment_details(prompt, retry=True)
        else:
            st.error("❌ I couldn’t understand your request.")
            st.info("💡 Please try again with more specific details, like:\n\n`Schedule a 30-minute meeting with John tomorrow at 4 PM in New York`")
            with st.expander("🔍 Debug Info"):
                st.subheader("Parsed JSON (incomplete)")
                st.json(parsed_json)
            return None

    return {
        "summary": summary,
        "start": isoparse(start_str),
        "end": isoparse(end_str),
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
if st.button("📆 Book Appointment"):
    if not user_input.strip():
        st.warning("⚠️ Please enter a valid appointment request.")
    elif not looks_valid_request(user_input):
        st.info("💡 Your request seems incomplete. Please mention a date and time. For example:\n\n`Schedule a 30-minute meeting with Alex tomorrow at 4 PM in New York`")
    else:
        with st.spinner("🔍 Talking to Gemini..."):
            try:
                # Replace relative dates like "tomorrow" → "2025-07-04"
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
                    start = start.astimezone(tz)
                    end = end.astimezone(tz)
                else:
                    start = apply_default_timezone_if_missing(start)
                    end = apply_default_timezone_if_missing(end)

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

            except Exception as e:
                st.error("⚠️ An unexpected error occurred while processing the request.")
                st.exception(e)
