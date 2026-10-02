"""
layer1_news_search.py — Real-Time News Corroboration
Checks if a claim appears in real, recent news articles.

Sources used (all FREE, no API key needed by default):
  • GDELT 2.0  — indexes 100+ languages, updated every 15 minutes
  • Wikipedia  — for factual entity verification
  • NewsAPI    — optional, 100 req/day free (more reliable than GDELT)

Logic:
  - Credible sources publishing this claim → likely REAL
  - No credible sources, only tabloids      → suspicious / FAKE
  - Not found anywhere                      → UNVERIFIED (too new / obscure)
"""

import requests
import time
import re
import sys
import os
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

HEADERS = {"User-Agent": config.USER_AGENT}


# ─────────────────────────────────────────────────────────────────────────────
# Utility: Extract domain from URL
# ─────────────────────────────────────────────────────────────────────────────
def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _score_domain(domain: str) -> int:
    """Return credibility score for a given domain."""
    if domain in config.TRUSTED_DOMAINS:
        return config.TRUSTED_DOMAINS[domain]
    if domain in config.UNRELIABLE_DOMAINS:
        return config.UNRELIABLE_DOMAINS[domain]
    return 0  # unknown domain = neutral


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Layer A: GDELT 2.0 (free, no key, updated every 15 minutes)
# Covers news from last 3 months across 100+ languages
# ─────────────────────────────────────────────────────────────────────────────
def search_gdelt(query: str, days_back: int = 2) -> dict:
    """
    Search GDELT for recent news matching the query.
    Returns credibility score + list of found articles.
    """
    result = {
        "source": "GDELT",
        "articles": [],
        "credibility_score": 0,
        "verdict_hint": "unverified",
        "error": None
    }

    try:
        # Build date filter (yesterday + today = "1 day old news")
        since_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y%m%d%H%M%S")
        encoded_query = quote(query)
        url = (
            f"https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query={encoded_query}"
            f"&mode=artlist"
            f"&maxrecords=15"
            f"&startdatetime={since_date}"
            f"&sort=DateDesc"
            f"&format=json"
        )
        resp = requests.get(url, headers=HEADERS, timeout=(6, 15))

        if resp.status_code == 429:
            result["error"] = "GDELT rate limited (5 sec between calls)"
            return result

        if resp.status_code != 200 or not resp.text.strip():
            result["error"] = f"GDELT returned status {resp.status_code}"
            return result

        data = resp.json()
        articles = data.get("articles", [])
        result["articles"] = articles[:10]

        # Score all found articles by domain credibility
        total_score = 0
        for art in articles:
            domain = _get_domain(art.get("url", ""))
            score = _score_domain(domain)
            total_score += score

        result["credibility_score"] = total_score

        if total_score >= 15:
            result["verdict_hint"] = "real"
        elif total_score <= -5:
            result["verdict_hint"] = "fake"
        else:
            result["verdict_hint"] = "unverified"

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Layer B: Wikipedia Fact Cross-Check (free, no key)
# Used to verify factual claims about real entities (people, places, events)
# ─────────────────────────────────────────────────────────────────────────────
def search_wikipedia(query: str) -> dict:
    """
    Search Wikipedia for factual information related to the claim.
    Returns a summary and whether any numbers/claims match.
    """
    result = {
        "source": "Wikipedia",
        "found": False,
        "extract": "",
        "page_title": "",
        "contradiction_detected": False,
        "verdict_hint": "unverified",
        "error": None
    }

    try:
        # Step 1: Search for the most relevant Wikipedia page
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
            result["error"] = "No Wikipedia page found"
            return result

        page_title = search_results[0]["title"]
        result["page_title"] = page_title

        # Step 2: Get the first 3 sentences of that page
        extract_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "prop": "extracts",
                "exsentences": 5, "exintro": True,
                "titles": page_title, "format": "json",
                "explaintext": True
            },
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT
        )
        pages = extract_resp.json()["query"]["pages"]
        page = list(pages.values())[0]
        extract = page.get("extract", "")

        result["extract"] = extract
        result["found"] = bool(extract)

        if extract:
            result["verdict_hint"] = "has_context"
            # Check for numeric contradictions (e.g., "100 years" vs real age)
            numbers_in_query = re.findall(r"\b\d+\b", query)
            if numbers_in_query:
                for num in numbers_in_query:
                    # If the number in the claim doesn't appear in the Wikipedia extract
                    # but very different numbers do, flag a potential contradiction
                    if num not in extract and int(num) > 50:
                        # Find actual numbers in extract
                        real_nums = re.findall(r"\b(\d{4}|\d{2,3})\b", extract)
                        if real_nums:
                            result["contradiction_detected"] = True
                            result["verdict_hint"] = "contradiction"

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Layer C: NewsAPI (optional, 100 req/day free)
# More reliable than GDELT but requires a free API key
# ─────────────────────────────────────────────────────────────────────────────
def search_newsapi(query: str, days_back: int = 1) -> dict:
    """
    Search NewsAPI for recent articles. Requires NEWS_API_KEY in config.py
    """
    result = {
        "source": "NewsAPI",
        "articles": [],
        "credibility_score": 0,
        "verdict_hint": "unverified",
        "error": None
    }

    if not config.NEWS_API_KEY:
        result["error"] = "No NewsAPI key configured"
        return result

    try:
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "from": from_date,
                "sortBy": "publishedAt",
                "pageSize": 10,
                "language": "en",
                "apiKey": config.NEWS_API_KEY
            },
            headers=HEADERS,
            timeout=config.REQUEST_TIMEOUT
        )

        data = resp.json()
        if data.get("status") != "ok":
            result["error"] = data.get("message", "NewsAPI error")
            return result

        articles = data.get("articles", [])
        result["articles"] = articles

        total_score = 0
        for art in articles:
            source_url = art.get("url", "")
            domain = _get_domain(source_url)
            total_score += _score_domain(domain)

        result["credibility_score"] = total_score

        if total_score >= 15:
            result["verdict_hint"] = "real"
        elif total_score <= -5:
            result["verdict_hint"] = "fake"
        else:
            result["verdict_hint"] = "unverified"

    except Exception as e:
        result["error"] = str(e)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────
def run(query: str) -> dict:
    """
    Run all Layer 1 sub-checks and return combined result.
    """
    output = {
        "layer": "Layer 1 — Real-Time News Search",
        "query": query,
        "gdelt": None,
        "wikipedia": None,
        "newsapi": None,
        "combined_score": 0,
        "verdict_hint": "unverified",
        "supporting_articles": []
    }

    # Run GDELT
    gdelt_result = search_gdelt(query)
    output["gdelt"] = gdelt_result
    output["combined_score"] += gdelt_result.get("credibility_score", 0)
    output["supporting_articles"].extend([
        {"title": a.get("title", ""), "url": a.get("url", ""), "domain": _get_domain(a.get("url", ""))}
        for a in gdelt_result.get("articles", [])[:5]
    ])

    # Small delay to respect GDELT rate limit
    time.sleep(0.5)

    # Run Wikipedia
    wiki_result = search_wikipedia(query)
    output["wikipedia"] = wiki_result

    # A contradiction in Wikipedia strongly hints at fake
    if wiki_result.get("contradiction_detected"):
        output["combined_score"] -= 10
    elif wiki_result.get("verdict_hint") == "has_context":
        output["combined_score"] += 2  # slight boost for having context

    # Run NewsAPI (only if key is configured)
    if config.NEWS_API_KEY:
        newsapi_result = search_newsapi(query)
        output["newsapi"] = newsapi_result
        output["combined_score"] += newsapi_result.get("credibility_score", 0)
        output["supporting_articles"].extend([
            {"title": a.get("title", ""), "url": a.get("url", ""), "domain": _get_domain(a.get("url", ""))}
            for a in newsapi_result.get("articles", [])[:5]
        ])

    # Final verdict hint
    if output["combined_score"] >= 15:
        output["verdict_hint"] = "real"
    elif output["combined_score"] <= -8:
        output["verdict_hint"] = "fake"
    else:
        output["verdict_hint"] = "unverified"

    return output


if __name__ == "__main__":
    test_query = "Modi age 100 years old"
    print(f"\nTesting Layer 1 with: '{test_query}'")
    result = run(test_query)
    print(f"\nVerdict Hint : {result['verdict_hint']}")
    print(f"Combined Score: {result['combined_score']}")
    print(f"\nWikipedia page: {result['wikipedia'].get('page_title')}")
    print(f"Contradiction detected: {result['wikipedia'].get('contradiction_detected')}")
    print(f"Wikipedia extract: {result['wikipedia'].get('extract', '')[:200]}")
    print(f"\nGDELT articles found: {len(result['gdelt'].get('articles', []))}")
    print(f"GDELT error: {result['gdelt'].get('error')}")
