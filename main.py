from calendar_utils import is_time_slot_available, create_event
from agent import parse_appointment_request
from dateutil.parser import isoparse
if __name__ == "__main__":
    user_input = input("💬 User: ")  # e.g., "Book a call with Alice tomorrow at 2pm"

    parsed = parse_appointment_request(user_input)

    if not parsed:
        print("❌ Sorry, I couldn't understand the appointment.")
    elif parsed["start_time"] == "null" or parsed["summary"] == "null":
        print("❌ Incomplete info. Please provide date, time, and purpose.")
    else:

        start = isoparse(parsed["start_time"])
        end = isoparse(parsed["end_time"])
        summary = parsed["summary"] or "Untitled Appointment"

        if is_time_slot_available(start, end):
            link = create_event(summary, start, end)
            print("✅ Appointment booked:", link)
        else:
            print("❌ That time slot is already booked.")
else:
    print("❌ Could not parse appointment details.")

