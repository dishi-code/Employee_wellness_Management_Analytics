# Milestone 2: Multilingual NLP Pipeline & Web Application (MoodMentor)

## 📌 Overview
This directory contains **Milestone 2** of the Employee Wellness Analytics project. In this milestone, we developed an end-to-end, multilingual Natural Language Processing (NLP) pipeline integrated into a full-stack **FastAPI** backend and **Streamlit** web application (**MoodMentor**). 

The platform allows users to upload employee feedback datasets (CSV/TXT), run multi-stage NLP transformations, perform sentiment analysis and emotion classification, and interact with a supportive wellness AI chatbot.

---

## 🛠️ Key Pipeline & Technical Features

- **User Authentication & Security**:
  - JWT-based authorization (`PyJWT`, `bcrypt`) with email OTP verification via Gmail SMTP (`smtplib`).
  - PostgreSQL database connection pooling (`psycopg2`) for user credentials and security tokens.

- **Multilingual Data Preprocessing**:
  - **Language Detection & Text Normalization**: Detects 50+ languages (including Telugu, Kannada, Hindi, English) using `langdetect` and `ftfy`.
  - **Stopword Filtering**: Language-aware stopword removal via `stopwordsiso`.
  - **Translation & Lemmatization**: Automatic English translation via `deep-translator` and lemmatization using spaCy (`xx_sent_ud_sm`).

- **Sentiment & Emotion Analysis**:
  - **VADER Sentiment Analysis**: Computes compound, positive, negative, and neutral sentiment scores (`vaderSentiment`).
  - **Fine-Tuned BERT Emotion Classifier**: Multi-label emotion classification mapped to core app labels (*Happy, Sad, Stress, Angry, Fear, Neutral*) using `bhadresh-savani/bert-base-go-emotion`.

- **Interactive UI & Wellness Chatbot**:
  - **Streamlit Frontend**: Custom glassmorphism interface featuring responsive navigation, analytical report cards, and interactive Plotly visualization charts.
  - **Qwen2.5 Conversational AI**: Integrated `Qwen/Qwen2.5-0.5B-Instruct` causal language model for an interactive employee wellness assistant.
  - **Crisis Safety Net**: Built-in crisis keyword detection that immediately routes flagged inputs to crisis helpline resources.

---

## 📁 File Structure

* **`app.py`**: The main Streamlit web application providing dashboards, file uploader, profile management, feedback, and wellness chat interfaces.
* **`backend.py`**: FastAPI server hosting REST API endpoints (`/upload`, `/analyze`, `/chat`) with JWT authentication.
* **`nlp_pipeline.py`**: Core NLP processing engine handling normalization, translation, spaCy tokenization, BERT emotion scoring, and Qwen chat generation.
* **`auth.py` & `db.py`**: Database management and password hashing / JWT verification services.
* **`email_utils.py`**: Utility for dispatching verification OTPs via SMTP.

---

## 🚀 How to Run

1. **Install Dependencies**:
   ```bash
   pip install streamlit psycopg2-binary PyJWT bcrypt python-dotenv email-validator pyngrok \
               fastapi uvicorn python-multipart requests langdetect ftfy emoji \
               deep-translator vaderSentiment spacy pandas matplotlib transformers accelerate torch stopwordsiso
   python -m spacy download xx_sent_ud_sm
