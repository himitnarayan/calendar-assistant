from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import json
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = os.getenv("CALENDAR_ID")

# Load credentials from environment variable
credentials_info = json.loads(os.environ['GOOGLE_CREDENTIALS_JSON'])
credentials = service_account.Credentials.from_service_account_info(credentials_info, scopes=SCOPES)


def get_calendar_service():
    # Refresh if needed (optional, but safe)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    return build('calendar', 'v3', credentials=credentials)


def create_event(summary, start_time: datetime, end_time: datetime):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
    }
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')


def is_time_slot_available(start_time: datetime, end_time: datetime):
    service = get_calendar_service()
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return len(events) == 0


def suggest_next_available_slot(start_from=None, duration_minutes=60, days_ahead=7):
    if start_from is None:
        start_from = datetime.now()

    start_from = (start_from + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    service = get_calendar_service()

    for day in range(days_ahead):
        current_day = start_from + timedelta(days=day)
        for hour in range(9, 18):  # 9 AM to 6 PM
            start = current_day.replace(hour=hour, minute=0)
            end = start + timedelta(minutes=duration_minutes)

            if is_time_slot_available(start, end):
                return start, end

    return None, None
