"""
config.py — Central configuration for the Fake News Examiner
All API keys and thresholds are controlled here.
"""

# ─── API Keys ────────────────────────────────────────────────────────────────
# Get a FREE key from: https://newsapi.org/register (100 req/day free)
NEWS_API_KEY = "0084acadd72740f5acb7b1320f25553b"  # <-- paste your NewsAPI.org key here (optional)

# Get a FREE key from: https://console.cloud.google.com → "Fact Check Tools API"
GOOGLE_FACT_CHECK_API_KEY = "AIzaSyBNdYf4j_vZlv1l46u7v7rz2tVupKLAIHI"  # <-- paste your Google API key here (optional)
 
# ─── BERT Model ──────────────────────────────────────────────────────────────
# HuggingFace model for linguistic fake news detection
# This downloads automatically on first run (~500MB, one-time)
BERT_MODEL_NAME = "hamzab/roberta-fake-news-classification"

# ─── Verdict Thresholds ──────────────────────────────────────────────────────
FAKE_THRESHOLD    = 0.65   # score below this = FAKE
REAL_THRESHOLD    = 0.65   # score above this = REAL
# Anything in between = UNVERIFIED

# ─── Credibility Scores for News Sources (used in Layer 1) ───────────────────
TRUSTED_DOMAINS = {
    # International Tier 1
    "reuters.com": 10, "apnews.com": 10, "bbc.com": 9, "bbc.co.uk": 9,
    "theguardian.com": 8, "nytimes.com": 8, "washingtonpost.com": 8,
    "bloomberg.com": 8, "ft.com": 8, "economist.com": 8,
    "wsj.com": 8, "cnbc.com": 7, "cnn.com": 7, "nbcnews.com": 7,
    # Indian Tier 1
    "ndtv.com": 8, "thehindu.com": 8, "indianexpress.com": 8,
    "timesofindia.com": 7, "hindustantimes.com": 7, "livemint.com": 7,
    "business-standard.com": 7, "theprint.in": 7, "scroll.in": 7,
    "wire.in": 7, "thewire.in": 7,
    # Fact-checkers
    "snopes.com": 9, "factcheck.org": 9, "politifact.com": 9,
    "boomlive.in": 9, "altnews.in": 9, "vishvasnews.com": 8,
}

UNRELIABLE_DOMAINS = {
    "worldnewsdailyreport.com": -10,
    "yournewswire.com": -10,
    "beforeitsnews.com": -8,
    "infowars.com": -9,
    "naturalnews.com": -8,
    "theonion.com": -5,   # satire
    "clickhole.com": -5,  # satire
}

# ─── Layer Weights (for final verdict aggregation) ───────────────────────────
# These control how much each layer influences the final verdict
LAYER_WEIGHTS = {
    "factcheck":  0.50,   # Google Fact Check or Wikipedia cross-check
    "news_search": 0.30,  # Real-time news corroboration via GDELT/NewsAPI
    "bert":        0.20,  # ML linguistic analysis
}

# ─── Request Settings ─────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 8       # seconds before giving up on an API call
GDELT_DELAY     = 6       # seconds between GDELT requests (their rate limit)
USER_AGENT      = "FakeNewsExaminer/2.0 (educational project)"
