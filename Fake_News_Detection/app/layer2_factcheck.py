"""
layer2_factcheck.py — Fact-Check Database Lookup
Searches verified fact-checker databases for known claims.

Sources used:
  • Google Fact Check Tools API  — 200+ fact-check orgs (Reuters, AFP, Snopes)
                                   FREE but requires a Google API key
  • Wikipedia entity verification — always free, no key needed
  • Known fake news patterns      — local pattern rules as backup

Priority: If a claim is found in a fact-check database, that result
          dominates the final verdict (highest trust).
"""

import requests
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

HEADERS = {"User-Agent": config.USER_AGENT}

# ─── Rating normalization map ─────────────────────────────────────────────────
# Different fact-checkers use different rating words. Map them all to scores.
RATING_SCORES = {
    # Definitively False
    "false": 0.0, "pants on fire": 0.0, "false!": 0.0, "fabricated": 0.0,
    "fake": 0.0, "misleading": 0.1, "manipulated": 0.05, "incorrect": 0.05,
    "inaccurate": 0.1, "wrong": 0.05, "debunked": 0.0, "distorted": 0.1,
    "mostly false": 0.1, "rated false": 0.0, "hoax": 0.0, "scam": 0.0,
    # Partially True
    "mostly true": 0.8, "half true": 0.5, "half-true": 0.5, "mixture": 0.5,
    "partly false": 0.3, "partly true": 0.6, "lacks context": 0.4,
    "unverified": 0.4, "disputed": 0.35, "exaggerated": 0.3,
    # Definitively True
    "true": 1.0, "correct": 1.0, "accurate": 1.0, "verified": 1.0,
    "confirmed": 1.0, "real": 1.0, "legit": 0.9,
}


def _normalize_rating(rating_text: str) -> float:
    """Convert any rating string to a 0.0–1.0 score."""
    if not rating_text:
        return 0.5
    rating_lower = rating_text.lower().strip()
    for key, val in RATING_SCORES.items():
        if key in rating_lower:
            return val
    return 0.5  # unknown rating → neutral


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Layer A: Google Fact Check Tools API
# Searches claims from 200+ fact-checking organizations worldwide
# Including: Reuters, AFP, Snopes, PolitiFact, AltNews, BoomLive, etc.
# FREE key from: https://console.cloud.google.com → "Fact Check Tools API"
# ─────────────────────────────────────────────────────────────────────────────
def search_google_factcheck(query: str) -> dict:
    result = {
        "source": "Google Fact Check",
        "found": False,
        "claims": [],
        "best_rating": None,
        "best_score": 0.5,
        "publisher": None,
        "review_url": None,
        "verdict_hint": "unverified",
        "error": None
    }

    if not config.GOOGLE_FACT_CHECK_API_KEY:
        result["error"] = "No Google Fact Check API key in config.py"
        return result

    try:
        resp = requests.get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params={
                "query": query,
                "key": config.GOOGLE_FACT_CHECK_API_KEY,
                "pageSize": 5
            },
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT
        )

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return result

        data = resp.json()
        claims = data.get("claims", [])

        if not claims:
            result["error"] = "No fact-checks found for this query"
            return result

        result["found"] = True
        parsed_claims = []

        for claim in claims[:3]:
            for review in claim.get("claimReview", []):
                rating_text = review.get("textualRating", "")
                score = _normalize_rating(rating_text)
                parsed_claims.append({
                    "claim_text": claim.get("text", ""),
                    "rating": rating_text,
                    "score": score,
                    "publisher": review.get("publisher", {}).get("name", ""),
                    "url": review.get("url", ""),
                    "review_date": review.get("reviewDate", "")
                })

        result["claims"] = parsed_claims

        if parsed_claims:
            # Use the most definitive (most extreme) rating
            best = min(parsed_claims, key=lambda x: abs(x["score"] - 0.5)) \
                   if len(parsed_claims) == 1 else \
                   min(parsed_claims, key=lambda x: x["score"])  # most FALSE leaning
            result["best_rating"] = best["rating"]
            result["best_score"] = best["score"]
            result["publisher"] = best["publisher"]
            result["review_url"] = best["url"]

            if best["score"] <= 0.2:
                result["verdict_hint"] = "fake"
            elif best["score"] >= 0.8:
                result["verdict_hint"] = "real"
            else:
                result["verdict_hint"] = "partial"

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Layer B: Wikipedia-based Entity Fact Verification (always free)
# Extracts verifiable facts from Wikipedia to cross-check numeric claims
# e.g., "Modi is 100 years old" → Wikipedia says he was born in 1950 → CONTRADICTION
# ─────────────────────────────────────────────────────────────────────────────
def verify_entity_facts(query: str) -> dict:
    result = {
        "source": "Wikipedia Entity Check",
        "entity_found": False,
        "verified_facts": [],
        "contradictions": [],
        "verdict_hint": "unverified",
        "confidence": 0.5,
        "error": None
    }

    try:
        # Search Wikipedia for the main entity in the query
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": query, "format": "json", "srlimit": 1
            },
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT
        )
        search_data = search_resp.json()
        search_results = search_data.get("query", {}).get("search", [])

        if not search_results:
            return result

        page_title = search_results[0]["title"]

        # Get a longer extract for better fact checking
        extract_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "prop": "extracts",
                "exsentences": 10, "exintro": True,
                "titles": page_title, "format": "json", "explaintext": True
            },
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT
        )
        pages = extract_resp.json()["query"]["pages"]
        extract = list(pages.values())[0].get("extract", "")

        if not extract:
            return result

        result["entity_found"] = True

        # ── Age Check ──────────────────────────────────────────────────────
        # Extract birth year from Wikipedia
        birth_year_match = re.search(r"born\s+.*?(\d{4})", extract)
        if birth_year_match:
            real_birth_year = int(birth_year_match.group(1))
            real_age = 2024 - real_birth_year
            result["verified_facts"].append(
                f"Born in {real_birth_year} (approx. {real_age} years old)"
            )

            # Check if the claim mentions an age and if it contradicts reality
            age_in_query = re.search(r"(\d{2,3})\s*years?\s*old", query, re.IGNORECASE)
            if age_in_query:
                claimed_age = int(age_in_query.group(1))
                if abs(claimed_age - real_age) > 10:
                    result["contradictions"].append(
                        f"Claim says {claimed_age} years old, but Wikipedia says ~{real_age} years old"
                    )
                    result["verdict_hint"] = "fake"
                    result["confidence"] = 0.95

        # ── Death Check ────────────────────────────────────────────────────
        if "died" in extract.lower() or "death" in extract.lower():
            if any(w in query.lower() for w in ["alive", "living", "still", "current"]):
                result["contradictions"].append("Wikipedia indicates this person may be deceased")
                result["verdict_hint"] = "fake"
                result["confidence"] = 0.85

        # ── Position / Role Check ──────────────────────────────────────────
        positions = re.findall(
            r"(?:is|was|served as|became)\s+(?:the\s+)?([A-Z][a-z]+(?: [A-Z][a-z]+){0,3})", extract
        )
        if positions:
            result["verified_facts"].extend([f"Known role: {p}" for p in positions[:3]])

        if result["contradictions"]:
            result["verdict_hint"] = "fake"
        elif result["verified_facts"] and result["verdict_hint"] == "unverified":
            result["verdict_hint"] = "context_found"

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────
def run(query: str) -> dict:
    """
    Run all Layer 2 fact-check sub-checks and return combined result.
    This layer has the HIGHEST weight in the final verdict.
    """
    output = {
        "layer": "Layer 2 — Fact-Check Database",
        "query": query,
        "google_factcheck": None,
        "entity_verification": None,
        "verdict_hint": "unverified",
        "confidence": 0.5,
        "verdict_score": 0.5,   # 0=fake, 1=real
        "best_evidence": None
    }

    # Sub-layer A: Google Fact Check
    gfc = search_google_factcheck(query)
    output["google_factcheck"] = gfc

    if gfc["found"] and not gfc.get("error"):
        # Google Fact Check is the gold standard — trust it directly
        output["verdict_hint"] = gfc["verdict_hint"]
        output["verdict_score"] = gfc["best_score"]
        output["confidence"] = 0.97
        output["best_evidence"] = {
            "type": "fact_check_database",
            "rating": gfc["best_rating"],
            "publisher": gfc["publisher"],
            "url": gfc["review_url"]
        }
        return output  # No need to check further — fact-checker already ruled

    # Sub-layer B: Wikipedia entity verification (always runs)
    ev = verify_entity_facts(query)
    output["entity_verification"] = ev

    if ev["contradictions"]:
        output["verdict_hint"] = "fake"
        output["verdict_score"] = 0.05
        output["confidence"] = ev.get("confidence", 0.85)
        output["best_evidence"] = {
            "type": "wikipedia_contradiction",
            "contradictions": ev["contradictions"],
            "verified_facts": ev["verified_facts"]
        }
    elif ev["verified_facts"]:
        output["verdict_hint"] = "context_found"
        output["verdict_score"] = 0.5
        output["confidence"] = 0.4
        output["best_evidence"] = {
            "type": "wikipedia_context",
            "facts": ev["verified_facts"]
        }

    return output


if __name__ == "__main__":
    queries = [
        "does the age of pm modi is 100 years old",
        "Barack Obama was not born in the United States",
        "India won the cricket world cup 2023",
    ]
    for q in queries:
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        result = run(q)
        print(f"Verdict Hint : {result['verdict_hint']}")
        print(f"Verdict Score: {result['verdict_score']} (0=fake, 1=real)")
        print(f"Confidence   : {result['confidence']}")
        print(f"Best Evidence: {result['best_evidence']}")
