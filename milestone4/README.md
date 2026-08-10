# Employee Wellness Management Analytics — MoodMentor

MoodMentor is an AI-powered employee wellness app. Employees log their mood
and write journal entries, the app analyzes sentiment and emotion using NLP,
gives a wellness recommendation, and stores everything for tracking over
time. Managers can view team-wide mood trends.

## Workflow

Text Input → Preprocessing → Emotion & Sentiment Analysis → Recommendation → Database → Report

## Tech Stack

- **Frontend:** Streamlit
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **NLP:** spaCy, VADER,  BERT , Qwen 


## Features

- Signup/login with OTP email verification
- Manual mood picker + mood calendar
- Journal analysis (text or file upload), multilingual support
- Wellness chatbot with crisis-message safety check
- Dashboard: date/mood/source/search filters, charts, PDF export, CSV export
- Manager report view with team trends

## Setup (Google Colab)

1. Add these as Colab Secrets (never hardcode or commit them):
   `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `JWT_SECRET`,
   `SMTP_EMAIL`, `SMTP_APP_PASSWORD`, `NGROK_AUTHTOKEN`
2. Install dependencies (see `backend/requirements.txt`)
3. Run the notebook — it starts FastAPI on port 8000, Streamlit on port 8501,
   and exposes it via ngrok.

## Security

- No secrets committed to this repo — loaded from Colab Secrets into a
  `.env` file at runtime, which is `.gitignore`d.
- Passwords hashed with bcrypt. OTPs expire in 10 minutes.

## Screenshots

See `screenshots/` for integration, testing, dashboard, and recommendation
validation evidence.
