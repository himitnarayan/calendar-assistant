# # from calendar_utils import get_calendar_service, CALENDAR_ID
# #
# # service = get_calendar_service()
# # events = service.events().list(calendarId=CALENDAR_ID).execute()
# # print(events)
# import google.generativeai as genai
# import os
# from dotenv import load_dotenv
#
# load_dotenv()
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
#
# model = genai.GenerativeModel("models/gemini-2.5-pro")
#
# response = model.generate_content("Say hello like a robot.")
# print(response.text)
import streamlit as st
from datetime import datetime, timedelta
from dateutil.parser import isoparse
import google.generativeai as genai
from calendar_utils import is_time_slot_available, create_event, suggest_next_available_slot
import os
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "models/gemini-1.5-pro-latest"
model = genai.GenerativeModel(MODEL_NAME)

# Streamlit page config
st.set_page_config(page_title="📅 Appointment Scheduler", layout="centered")
st.title("🤖 AI Appointment Scheduler")
st.markdown("Describe your appointment in natural language, and we'll book it!")

user_input = st.text_area("📝 Your Request", placeholder="e.g., Schedule a call with Himit tomorrow at 11 AM")

REQUIRED_KEYS = {"summary", "start_time", "end_time"}

def sanitize_and_parse_json(raw: str) -> dict:
    try:
        # Remove code block wrappers like ```json
        cleaned = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()

        # Optional: truncate if extra data comes after JSON
        match = re.search(r"\{[\s\S]*?\}", cleaned)
        if match:
            cleaned = match.group(0)

        parsed = json.loads(cleaned)

        # Validate required fields
        missing = REQUIRED_KEYS - parsed.keys()
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        return parsed
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response: Invalid JSON – {e}")
    except Exception as e:
        raise ValueError(f"Failed to parse Gemini response: {e}")

def correct_past_datetime(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    now = datetime.now(start.tzinfo)
    if start < now:
        start = start.replace(year=now.year, month=now.month, day=now.day)
        end = end.replace(year=now.year, month=now.month, day=now.day)
        if start < now:  # still in past, bump to tomorrow
            start += timedelta(days=1)
            end += timedelta(days=1)
    return start, end

if st.button("📆 Book Appointment"):
    if not user_input.strip():
        st.warning("Please enter a valid request.")
    else:
        with st.spinner("🔍 Talking to Gemini..."):
            prompt = f"""
Extract the following appointment request into valid JSON format:

Format:
{{
  "summary": "Call with Alice",
  "start_time": "YYYY-MM-DDTHH:MM:SS+05:30",
  "end_time": "YYYY-MM-DDTHH:MM:SS+05:30"
}}

Request:
{user_input}
"""
            try:
                response = model.generate_content(prompt)
                parsed_json = sanitize_and_parse_json(response.text)

                summary = parsed_json["summary"]
                start = isoparse(parsed_json["start_time"])
                end = isoparse(parsed_json["end_time"])

                start, end = correct_past_datetime(start, end)

                if is_time_slot_available(start, end):
                    link = create_event(summary, start, end)
                    st.success("✅ Appointment booked successfully!")
                    st.markdown(f"[📅 View in Calendar]({link})")
                else:
                    st.warning("⚠️ That time is already booked. Searching for next available slot...")
                    next_start, next_end = suggest_next_available_slot(start_from=start)
                    if next_start and next_end:
                        link = create_event(summary, next_start, next_end)
                        st.success("✅ Booked next available slot:")
                        st.markdown(f"🕒 {next_start.strftime('%Y-%m-%d %H:%M')} to {next_end.strftime('%H:%M')}")
                        st.markdown(f"[📅 View in Calendar]({link})")
                    else:
                        st.error("❌ No available slots found in the next 7 days.")

            except Exception as e:
                st.error("⚠️ Gemini response couldn't be processed.")
                st.exception(e)
