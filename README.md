# 🤖 AI Calendar Assistant

This is a conversational appointment booking assistant built with **Streamlit**, **Google Calendar API**, and **Gemini (Google Generative AI)**.

## 📋 Features

- Book appointments using natural language
- Gemini parses user input to extract structured date/time
- Integrates with Google Calendar using a service account
- Suggests next available slots if conflicts exist
- Supports timezones, user-defined durations, multi-day events

## 🧠 Powered by
- [Streamlit](https://streamlit.io/) – for frontend UI
- [Google Calendar API](https://developers.google.com/calendar)
- [Google Gemini Pro API](https://ai.google.dev/) – for NLP

## 🛠 Setup Instructions

1. **Clone this repo**

   ```bash
   git clone https://github.com/himitnarayan/calendar-assistant.git
   cd calendar-assistant
   
2.Create a virtual environment & install dependencies

 ```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```
3.Configure Environment Variables
Create a .env file:

 ```.env
GEMINI_API_KEY=your_gemini_api_key
CALENDAR_ID=your_google_calendar_id
```
4.Add your Google service account JSON key

Name it something like credentials.json (but DO NOT COMMIT it).

Share your calendar with the service account email.

5.Run the app
```bash
streamlit run app.py
```
📅 Example Prompt


Schedule a 90-minute call with Meera on July 5 from 4:30am. I am in Tokyo, Japan.
