"""
web/server.py — Flask Web Server for Fake News Examiner
Serves the beautiful web UI and exposes a REST API endpoint.

Run with:
    python web/server.py
Then open: http://localhost:5000
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from app import layer1_news_search, layer2_factcheck, layer3_bert_classifier, aggregator

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/examine", methods=["POST"])
def api_examine():
    """
    POST /api/examine
    Body: { "query": "...", "use_bert": true }
    Returns: full verdict JSON
    """
    data = request.get_json(force=True)
    query = (data.get("query") or "").strip()
    use_bert = data.get("use_bert", True)

    if not query or len(query) < 5:
        return jsonify({"error": "Please enter a longer claim (at least 5 characters)."}), 400

    start = time.time()

    # Layer 2 first (fastest for known claims)
    l2_result = layer2_factcheck.run(query)

    # Layer 1 (real-time news)
    l1_result = layer1_news_search.run(query)

    # Layer 3 (BERT) — skip if Layer 2 was definitive
    l2_conf = l2_result.get("confidence", 0)
    l2_hint = l2_result.get("verdict_hint", "unverified")

    if l2_conf >= 0.95 and l2_hint in ("fake", "real"):
        l3_result = {
            "verdict_hint": "skipped",
            "truth_score": 0.5,
            "confidence": 0.5,
            "model_used": "Skipped (fact-check was definitive)",
            "layer": "Layer 3 — ML Classifier"
        }
    else:
        l3_result = layer3_bert_classifier.run(query, use_bert=use_bert)

    # Aggregate
    final = aggregator.aggregate(l1_result, l2_result, l3_result)
    final["elapsed"] = round(time.time() - start, 2)

    # Attach layer details for the UI
    l1_gdelt = l1_result.get("gdelt") or {}
    l1_wiki = l1_result.get("wikipedia") or {}
    l2_gfc = l2_result.get("google_factcheck") or {}
    l2_entity = l2_result.get("entity_verification") or {}

    final["layer_details"] = {
        "layer1": {
            "gdelt_articles": len(l1_gdelt.get("articles") or []),
            "gdelt_error": l1_gdelt.get("error"),
            "wiki_page": l1_wiki.get("page_title", ""),
            "wiki_extract": (l1_wiki.get("extract") or "")[:250],
            "wiki_contradiction": l1_wiki.get("contradiction_detected", False),
            "combined_score": l1_result.get("combined_score", 0),
            "verdict": l1_result.get("verdict_hint", "unverified")
        },
        "layer2": {
            "google_fc_found": l2_gfc.get("found", False),
            "google_fc_rating": l2_gfc.get("best_rating"),
            "google_fc_publisher": l2_gfc.get("publisher"),
            "entity_contradictions": l2_entity.get("contradictions") or [],
            "entity_facts": l2_entity.get("verified_facts") or [],
            "verdict": l2_result.get("verdict_hint", "unverified")
        },
        "layer3": {
            "model": l3_result.get("model_used", ""),
            "truth_score": l3_result.get("truth_score", 0.5),
            "confidence": l3_result.get("confidence", 0.5),
            "verdict": l3_result.get("verdict_hint", "uncertain")
        }
    }

    return jsonify(final)


if __name__ == "__main__":
    print("\n[Fake News Examiner] Web Server starting...")
    print("   Open your browser at: http://localhost:5000\n")
    app.run(debug=True, port=5000, use_reloader=False)

