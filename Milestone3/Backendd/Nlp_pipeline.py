%%writefile nlp_pipeline.py
"""
nlp_pipeline.py
Multilingual NLP pipeline for employee feedback:
normalize -> detect language -> clean -> tokenize -> stopword-filter ->
translate to English -> lemmatize -> sentiment (VADER) -> emotion (BERT).
"""

import re
import ftfy
import emoji
import spacy
import torch
import stopwordsiso
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    pipeline as hf_pipeline,
)
from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

DetectorFactory.seed = 0

_nlp = None
_vader = None
_qwen_model = None
_qwen_tokenizer = None
_bert_emotion_pipeline = None

QWEN_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

BERT_EMOTION_MODEL_NAME = "bhadresh-savani/bert-base-go-emotion"

LANGUAGE_NAMES = {
    "te": "Telugu", "kn": "Kannada", "en": "English", "ta": "Tamil",
    "hi": "Hindi", "ml": "Malayalam", "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati",
    "fr": "French", "de": "German", "es": "Spanish", "pt": "Portuguese",
    "ar": "Arabic", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ru": "Russian",
}


def _get_stopwords(language_code: str) -> set:
    """
    Returns the stopword set for `language_code` using stopwordsiso, which
    covers 50+ languages by ISO 639-1 code. Returns an empty set for any
    language it doesn't cover -- filtering is skipped rather than failing,
    so unsupported languages still flow through the rest of the pipeline.
    """
    if stopwordsiso.has_lang(language_code):
        return stopwordsiso.stopwords(language_code)
    return set()

EMOTION_LABELS = ["Happy", "Sad", "Stress", "Angry", "Fear", "Neutral"]

EMOTION_EMOJI = {
    "Happy": "\U0001F60A", "Sad": "\U0001F622", "Stress": "\U0001F62B",
    "Angry": "\U0001F621", "Fear": "\U0001F628", "Neutral": "\U0001F610",
}

# Clean sentiment labels (no emoji baked in) -- these are what get returned
# to callers and stored in the DB. Emoji-for-display is looked up separately
# by the frontend/API layer so the raw label string always stays an exact
# match for NLP_TO_MOOD_LABEL in db.py.
SENTIMENT_EMOJI = {
    "Positive": "\U0001F60A", "Negative": "\U0001F614", "Neutral": "\U0001F610",
}

GOEMOTIONS_TO_APP_LABEL = {
    "joy": "Happy", "amusement": "Happy", "excitement": "Happy",
    "love": "Happy", "gratitude": "Happy", "optimism": "Happy",
    "relief": "Happy", "pride": "Happy", "admiration": "Happy",
    "approval": "Happy", "caring": "Happy",

    "sadness": "Sad", "disappointment": "Sad", "grief": "Sad",
    "remorse": "Sad",

    "nervousness": "Stress", "embarrassment": "Stress",
    "confusion": "Stress",

    "anger": "Angry", "annoyance": "Angry", "disgust": "Angry",
    "disapproval": "Angry",

    "fear": "Fear",

    "neutral": "Neutral", "realization": "Neutral", "surprise": "Neutral",
    "curiosity": "Neutral", "desire": "Neutral",
}


def _get_nlp():
    """Lazy-load the multilingual spaCy model once per process."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("xx_sent_ud_sm")
    return _nlp


def _get_vader():
    global _vader
    if _vader is None:
        _vader = SentimentIntensityAnalyzer()
    return _vader


def _get_qwen():
    """Lazy-load Qwen2.5-0.5B-Instruct once per process (GPU if available).
    Still used by the wellness chatbot (wellness_chat_reply) -- only the
    emotion-detection step now uses BERT instead."""
    global _qwen_model, _qwen_tokenizer
    if _qwen_model is None:
        _qwen_tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL_NAME)
        _qwen_model = AutoModelForCausalLM.from_pretrained(
            QWEN_MODEL_NAME,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )
    return _qwen_model, _qwen_tokenizer


def _get_bert_emotion_pipeline():
    """
    Lazy-load the fine-tuned BERT emotion classifier once per process, using
    Hugging Face's `pipeline()` helper -- this bundles the tokenizer and the
    model together so we just call it with raw text and get scores back.

    `top_k=None` tells the pipeline to return a score for every label
    instead of just the single top prediction, so we can build a full
    scores dict (matching what the UI already expects).
    """
    global _bert_emotion_pipeline
    if _bert_emotion_pipeline is None:
        _bert_emotion_pipeline = hf_pipeline(
            "text-classification",
            model=BERT_EMOTION_MODEL_NAME,
            top_k=None,
            device=0 if torch.cuda.is_available() else -1,
        )
    return _bert_emotion_pipeline


def _bert_emotion(text: str) -> dict:
    """
    Classifies `text` using the fine-tuned BERT GoEmotions model, then maps
    the 28 GoEmotions labels down to our 6 app-level EMOTION_LABELS by
    summing mapped scores. Returns the same shape the rest of the app
    already expects: {"emotion": <label>, "scores": {label: 0-1, ...}}.
    """
    classifier = _get_bert_emotion_pipeline()

    if not text.strip():
        text = "(empty feedback)"

    raw_predictions = classifier(text, truncation=True)[0]

    app_scores = {label: 0.0 for label in EMOTION_LABELS}
    for pred in raw_predictions:
        goemotion_label = pred["label"].lower()
        app_label = GOEMOTIONS_TO_APP_LABEL.get(goemotion_label, "Neutral")
        app_scores[app_label] += pred["score"]

    total = sum(app_scores.values()) or 1.0
    app_scores = {label: round(score / total, 4) for label, score in app_scores.items()}

    final_emotion = max(app_scores, key=app_scores.get)
    confidence = app_scores[final_emotion]
    return {"emotion": final_emotion, "scores": app_scores, "confidence": confidence}


# ---------------------------------------------------------------------------
# Wellness recommendation -- was missing entirely. Rule-based (fast, free,
# deterministic -- no extra model load) using the emotion label + VADER
# compound score that the pipeline already computed. Keeps the language
# supportive and non-clinical, matching the tone used elsewhere (see
# WELLNESS_SYSTEM_PROMPT below) and never diagnoses anything.
# ---------------------------------------------------------------------------
WELLNESS_RECOMMENDATIONS = {
    "Happy": [
        "Love this energy! 🎉 Take a second to notice what's working today so you can bottle it for later.",
        "You're glowing today -- share it with someone, good moods are contagious!",
    ],
    "Sad": [
        "Hey, it's okay to feel low sometimes 💙 Be gentle with yourself today -- maybe a favorite song, a short walk, or a warm drink can help lift things a little.",
        "This feeling won't last forever. You've gotten through hard days before, and you will again -- try reaching out to someone you trust, you don't have to carry it alone.",
    ],
    "Stress": [
        "Take a breath -- in for 4, hold for 4, out for 4. You've got more control over this than it feels like right now.",
        "One thing at a time. Pick the smallest task on your list and knock it out -- small wins add up fast.",
    ],
    "Angry": [
        "Totally valid to feel this way. Give yourself a few minutes before reacting -- a short walk or some music can help take the edge off.",
        "Let it out safely -- write down what's bothering you, then decide what (if anything) needs saying out loud.",
    ],
    "Fear": [
        "Uncertainty is uncomfortable, but you're handling it. Naming exactly what worries you often makes it feel smaller.",
        "You don't have to have it all figured out today. Take the next small step, and trust yourself with the rest.",
    ],
    "Neutral": [
        "A calm, steady day -- a nice moment to check in with yourself and set a small intention for later.",
        "Nothing urgent here! Good time for a quick stretch or a few minutes of fresh air.",
    ],
}

def get_wellness_recommendation(emotion_label: str, compound_score: float) -> str:
    """
    Returns one short, supportive, non-clinical recommendation string based
    on the detected emotion label (Happy/Sad/Stress/Angry/Fear/Neutral) and
    the VADER compound score. Picks the more intense of the two available
    phrasings when the compound score is strongly negative, otherwise the
    gentler one -- so the tone scales with severity without needing another
    model call.
    """
    options = WELLNESS_RECOMMENDATIONS.get(emotion_label, WELLNESS_RECOMMENDATIONS["Neutral"])
    if compound_score <= -0.5 and len(options) > 1:
        return options[1]
    return options[0]


def process_employee_feedback(text: str) -> dict:
    """Runs the full pipeline on a single blob of text and returns a results dict."""
    nlp = _get_nlp()
    vader = _get_vader()

    normalized_text = ftfy.fix_text(text)

    try:
        language = detect(normalized_text)
    except Exception:
        language = "unknown"
    detected_language = LANGUAGE_NAMES.get(language, "Other / Unknown")

    emoji_list = [ch for ch in normalized_text if ch in emoji.EMOJI_DATA]

    cleaned_text = re.sub(r"https?://\S+|www\.\S+", " ", normalized_text)
    cleaned_text = re.sub(r"\S+@\S+", " ", cleaned_text)
    cleaned_text = re.sub(r"@\w+|#\w+", " ", cleaned_text)
    cleaned_text = emoji.replace_emoji(cleaned_text, replace="")
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    doc = nlp(cleaned_text)
    sentences = [s.text.strip() for s in doc.sents if s.text.strip()]
    original_tokens = [t.text for t in doc if not t.is_space]
    clean_tokens = [t.text for t in doc if not t.is_punct and not t.is_space and not t.like_num]

    selected_stopwords = _get_stopwords(language)
    filtered_tokens = [t for t in clean_tokens if t.lower() not in selected_stopwords]
    final_preprocessed_text = " ".join(filtered_tokens)

    try:
        translated_text = GoogleTranslator(source="auto", target="en").translate(final_preprocessed_text)
    except Exception as error:
        translated_text = f"Translation failed: {error}"

    english_doc = nlp(translated_text)
    lemmas = [t.lemma_ if t.lemma_ else t.text for t in english_doc if not t.is_space]
    lemmatized_text = " ".join(lemmas)

    sentiment_scores = vader.polarity_scores(translated_text)
    compound_score = sentiment_scores["compound"]
    if compound_score >= 0.05:
        sentiment_label = "Positive"
    elif compound_score <= -0.05:
        sentiment_label = "Negative"
    else:
        sentiment_label = "Neutral"
    # Clean label (exact match for db.py's NLP_TO_MOOD_LABEL) plus a
    # separate display string with emoji for the frontend to show as-is.
    final_sentiment = sentiment_label
    final_sentiment_display = f"{sentiment_label} {SENTIMENT_EMOJI[sentiment_label]}"

    bert_result = _bert_emotion(translated_text)
    emotion_scores = bert_result["scores"]
    final_emotion_label = bert_result["emotion"]
    # Same fix here: keep the clean label separate from the emoji-decorated
    # display string, since db.py stores `emotion` as free text and the
    # frontend's style_for()/badge lookups expect a plain label.
    final_emotion = final_emotion_label
    final_emotion_display = f"{final_emotion_label} {EMOTION_EMOJI.get(final_emotion_label, '')}"
    emotion_confidence = bert_result["confidence"]

    wellness_recommendation = get_wellness_recommendation(final_emotion_label, compound_score)

    return {
        "language_code": language,
        "detected_language": detected_language,
        "normalized_text": normalized_text,
        "cleaned_text": cleaned_text,
        "sentences": sentences,
        "original_tokens": original_tokens,
        "filtered_tokens": filtered_tokens,
        "emoji_list": emoji_list,
        "final_preprocessed_text": final_preprocessed_text,
        "translated_text": translated_text,
        "lemmatized_text": lemmatized_text,
        "sentiment_scores": sentiment_scores,
        "final_sentiment": final_sentiment,
        "final_sentiment_display": final_sentiment_display,
        "emotion_scores": emotion_scores,
        "final_emotion": final_emotion,
        "final_emotion_display": final_emotion_display,
        "emotion_confidence": emotion_confidence,
        "wellness_recommendation": wellness_recommendation,
    }


CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life", "want to die", "self harm",
    "self-harm", "hurt myself", "not worth living", "no reason to live",
]

CRISIS_MESSAGE = (
    "I'm really glad you reached out, and I want to make sure you get support "
    "beyond what I can offer here. If you're in immediate danger, please contact "
    "your local emergency number right now. You can also reach a crisis line: "
    "in India, AASRA is available at +91-9820466726 (24/7). If you're outside "
    "India, please look up a local crisis helpline or talk to a trusted person "
    "or your HR/EAP contact. You don't have to go through this alone."
)

WELLNESS_SYSTEM_PROMPT = (
    "You are a supportive workplace wellness assistant for employees. "
    "Your role is to listen, validate feelings, and offer general, gentle "
    "coping suggestions (like breathing exercises, taking a short break, "
    "or talking to a trusted colleague or manager). "
    "You are NOT a therapist or doctor: never diagnose any condition, never "
    "claim expertise you don't have, and never give medical or medication "
    "advice. If the employee describes something serious (ongoing crisis, "
    "self-harm, harming others), gently encourage them to contact a mental "
    "health professional, their HR/EAP program, or a crisis helpline. "
    "Keep replies short (2-4 sentences), warm, and non-judgmental. "
    "Avoid clinical labels and avoid being preachy or repetitive."
)


def _contains_crisis_language(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in CRISIS_KEYWORDS)


def wellness_chat_reply(message: str, history: list[dict] | None = None) -> dict:
    """
    Generates a supportive wellness chatbot reply using the Qwen chat model.
    (The chatbot still uses Qwen -- it needs to generate free-form
    conversational replies, which is a generation task, not a
    classification task, so BERT isn't a fit here.)

    `history` is an optional list of {"role": "user"|"assistant", "content": str}
    dicts representing prior turns in the conversation (kept short/recent by
    the caller — this function does not trim it).

    Always checks for crisis language first; if found, returns a fixed,
    resource-pointing message instead of an LLM-generated one, since we
    never want a small model improvising in a safety-critical moment.
    """
    if _contains_crisis_language(message):
        return {"reply": CRISIS_MESSAGE, "flagged": True}

    model, tokenizer = _get_qwen()

    messages = [{"role": "system", "content": WELLNESS_SYSTEM_PROMPT}]
    for turn in (history or []):
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    reply = tokenizer.decode(generated, skip_special_tokens=True).strip()

    if not reply:
        reply = "I'm here and listening — could you tell me a bit more about how you're feeling?"

    return {"reply": reply, "flagged": False}
