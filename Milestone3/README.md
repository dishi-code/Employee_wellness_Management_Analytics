# MoodMentor — Milestone 3: Emotion Detection & Journal Analytics

## Project Objective
An AI-powered employee wellness app that detects emotion and sentiment from
journal entries and gives supportive wellness recommendations.

## Model Used
- **Emotion Detection:** `bhadresh-savani/bert-base-go-emotion` (BERT, fine-tuned on GoEmotions) — mapped to 6 labels: Happy, Sad, Stress, Angry, Fear, Neutral
- **Sentiment Analysis:** VADER (`vaderSentiment`)
- **Wellness Chatbot:** `Qwen/Qwen2.5-0.5B-Instruct`

## Emotion Detection Pipeline
Journal text → normalize → detect language → clean (remove URLs/emojis) →
tokenize + remove stopwords → translate to English → lemmatize → VADER
sentiment → BERT emotion → wellness recommendation.

## Confidence Score Calculation
BERT returns a probability for every emotion label. These are summed into
6 categories and normalized to add up to 1. The confidence score is the
normalized probability of the winning (predicted) emotion.

## Sentiment Analysis
VADER's `polarity_scores()` gives Positive, Negative, Neutral, and Compound
scores. Sentiment label is decided from the compound score:
- `>= 0.05` → Positive
- `<= -0.05` → Negative
- else → Neutral

All four scores are shown on screen; compound score is stored in the database.

## Database Schema
**users** — id, username, email, password_hash, is_verified, role

**mood_logs** — id, user_id (FK), mood_date, sentiment, emotion,
compound_score, confidence, journal_text, source, created_at

## API Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `/analyze-text` | POST | Analyze typed journal text |
| `/analyze` | POST | Analyze uploaded CSV/TXT file |
| `/chat` | POST | Wellness chatbot |
| `/health` | GET | Health check |

## Sample Input & Output
**Input:** "I've been feeling really down and unmotivated the past few days."

**Output:**
- Sentiment: Neutral | Emotion: Sad | Confidence: 72% | Language: English
- Sentiment Breakdown: Positive 0.34, Negative 0.34, Neutral 0.33
- Wellness Recommendation: "Hey, it's okay to feel low sometimes. Be gentle
  with yourself today — maybe a favorite song, a short walk, or a warm
  drink can help lift things a little."

## Observations
- Sentiment (VADER) and emotion (BERT) can disagree on short/ambiguous text
  since they measure different things — this is expected.
- Shorter entries tend to give lower confidence scores.


