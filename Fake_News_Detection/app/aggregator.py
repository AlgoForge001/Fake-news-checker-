"""
aggregator.py — Smart Verdict Engine
Combines results from all 3 layers into a single final verdict.

Priority order:
  1. Layer 2 (Fact-Check DB) → Highest trust — real verified sources
  2. Layer 1 (News Search)   → Medium trust  — real-time corroboration
  3. Layer 3 (BERT ML)       → Tiebreaker    — linguistic analysis

Final Verdict:
  ✅ REAL       — Confirmed by credible sources or fact-checkers
  ❌ FAKE       — Debunked by fact-checkers or contradicts known facts
  🔍 MISLEADING — Partially true or needs more context
  ⚠️  UNVERIFIED — Not enough evidence to decide (verify manually)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _weighted_score(l1_score: float, l2_score: float, l3_score: float) -> float:
    """
    Compute weighted average of all 3 layer truth scores.
    Weights are defined in config.LAYER_WEIGHTS.
    All scores are 0.0 (fake) to 1.0 (real).
    """
    w = config.LAYER_WEIGHTS
    return (
        l2_score * w["factcheck"] +
        l1_score * w["news_search"] +
        l3_score * w["bert"]
    )


def aggregate(l1_result: dict, l2_result: dict, l3_result: dict) -> dict:
    """
    Combine all 3 layer results into a final verdict.
    
    Returns:
        dict with keys:
          - verdict: "REAL" | "FAKE" | "MISLEADING" | "UNVERIFIED"
          - confidence: float (0.0–1.0)
          - truth_score: float (0.0=fake, 1.0=real)
          - summary: human-readable explanation
          - evidence: list of evidence strings with sources
          - sources: list of URLs for the user to check
          - dominant_layer: which layer drove the verdict
    """
    output = {
        "verdict": "UNVERIFIED",
        "confidence": 0.0,
        "truth_score": 0.5,
        "summary": "",
        "evidence": [],
        "sources": [],
        "dominant_layer": None,
        "layer_verdicts": {
            "layer1": l1_result.get("verdict_hint", "unverified"),
            "layer2": l2_result.get("verdict_hint", "unverified"),
            "layer3": l3_result.get("verdict_hint", "unverified"),
        }
    }

    # ─── STEP 1: Check Layer 2 (Fact-Check DB) — HIGHEST PRIORITY ────────────
    l2_hint = l2_result.get("verdict_hint", "unverified")
    l2_confidence = l2_result.get("confidence", 0.5)
    l2_score = l2_result.get("verdict_score", 0.5)
    l2_evidence = l2_result.get("best_evidence", {})

    if l2_hint == "fake" and l2_confidence >= 0.75:
        output["verdict"] = "FAKE"
        output["dominant_layer"] = "Layer 2 (Fact-Check Database)"
        output["truth_score"] = l2_score
        output["confidence"] = l2_confidence

        if l2_evidence:
            ev_type = l2_evidence.get("type", "")
            if ev_type == "fact_check_database":
                rating = l2_evidence.get("rating", "False")
                publisher = l2_evidence.get("publisher", "a fact-checker")
                url = l2_evidence.get("url", "")
                output["evidence"].append(
                    f"🔴 Fact-checker {publisher} rated this claim as \"{rating}\""
                )
                if url:
                    output["sources"].append(url)
            elif ev_type == "wikipedia_contradiction":
                for c in l2_evidence.get("contradictions", []):
                    output["evidence"].append(f"🔴 Wikipedia contradiction: {c}")
                for f in l2_evidence.get("verified_facts", [])[:2]:
                    output["evidence"].append(f"📖 Wikipedia fact: {f}")

        output["summary"] = (
            "This claim has been fact-checked and found to be FALSE. "
            "It contradicts verified facts from credible sources."
        )
        _attach_layer1_sources(output, l1_result)
        return output

    if l2_hint == "real" and l2_confidence >= 0.75:
        output["verdict"] = "REAL"
        output["dominant_layer"] = "Layer 2 (Fact-Check Database)"
        output["truth_score"] = l2_score
        output["confidence"] = l2_confidence

        if l2_evidence:
            ev_type = l2_evidence.get("type", "")
            if ev_type == "fact_check_database":
                rating = l2_evidence.get("rating", "True")
                publisher = l2_evidence.get("publisher", "a fact-checker")
                url = l2_evidence.get("url", "")
                output["evidence"].append(
                    f"✅ Fact-checker {publisher} rated this claim as \"{rating}\""
                )
                if url:
                    output["sources"].append(url)

        output["summary"] = (
            "This claim has been verified by a credible fact-checking organization."
        )
        _attach_layer1_sources(output, l1_result)
        return output

    if l2_hint == "partial":
        output["verdict"] = "MISLEADING"
        output["dominant_layer"] = "Layer 2 (Fact-Check Database)"
        output["truth_score"] = l2_score
        output["confidence"] = 0.70
        output["evidence"].append("⚠️  Fact-checkers found this claim to be partially true or misleading")
        output["summary"] = "This claim is partially true but missing important context or is exaggerated."
        _attach_layer1_sources(output, l1_result)
        return output

    # ─── STEP 2: Check Layer 1 (News Search) — MEDIUM PRIORITY ──────────────
    l1_hint = l1_result.get("verdict_hint", "unverified")
    l1_combined = l1_result.get("combined_score", 0)
    l1_articles = l1_result.get("supporting_articles", [])
    l1_wiki = l1_result.get("wikipedia", {})

    # Check if Wikipedia cross-check found a contradiction
    if l1_wiki and l1_wiki.get("contradiction_detected"):
        output["verdict"] = "FAKE"
        output["dominant_layer"] = "Layer 1 (Wikipedia Cross-Check)"
        output["truth_score"] = 0.1
        output["confidence"] = 0.80
        output["evidence"].append(
            f"🔴 Wikipedia says: \"{l1_wiki.get('extract', '')[:150]}...\""
        )
        output["evidence"].append("🔴 The claim contradicts verified Wikipedia facts")
        output["summary"] = (
            "The numbers or facts in this claim contradict what Wikipedia "
            "records for this topic."
        )
        _attach_layer1_sources(output, l1_result)
        return output

    if l1_hint == "real" and l1_combined >= 15:
        output["verdict"] = "REAL"
        output["dominant_layer"] = "Layer 1 (Credible News Corroboration)"
        output["truth_score"] = min(0.5 + (l1_combined / 100), 0.92)
        output["confidence"] = min(0.5 + (l1_combined / 100), 0.88)
        output["evidence"].append(
            f"✅ Found in {len(l1_articles)} credible news sources (combined score: {l1_combined})"
        )
        _attach_layer1_sources(output, l1_result)
        output["summary"] = (
            f"This claim appears in {len(l1_articles)} credible news sources, "
            "suggesting it is a real story."
        )
        return output

    if l1_hint == "fake" and l1_combined <= -8:
        output["verdict"] = "FAKE"
        output["dominant_layer"] = "Layer 1 (Unreliable Source Detection)"
        output["truth_score"] = 0.15
        output["confidence"] = 0.72
        output["evidence"].append("🔴 Found only in unreliable or no credible news sources")
        _attach_layer1_sources(output, l1_result)
        output["summary"] = (
            "This claim only appears in unreliable sources, or is absent from "
            "credible news outlets."
        )
        return output

    # ─── STEP 3: Layer 3 (BERT ML) as TIEBREAKER ─────────────────────────────
    l3_hint = l3_result.get("verdict_hint", "uncertain")
    l3_truth = l3_result.get("truth_score", 0.5)
    l3_conf = l3_result.get("confidence", 0.5)
    l3_model = l3_result.get("model_used", "ML model")

    # Weighted combination of all 3 layers
    # When Layer 2 & 1 are inconclusive, use all three
    l1_truth = 0.5 if l1_hint == "unverified" else (0.8 if l1_hint == "real" else 0.2)
    l2_truth = l2_score  # already normalized
    weighted = _weighted_score(l1_truth, l2_truth, l3_truth)
    output["truth_score"] = weighted

    if l3_hint == "fake" and l3_conf >= 0.80:
        output["verdict"] = "FAKE"
        output["dominant_layer"] = f"Layer 3 ({l3_model})"
        output["confidence"] = l3_conf * 0.75  # discount slightly — BERT alone
        output["evidence"].append(
            f"🤖 {l3_model} classified this as fake news ({l3_conf:.0%} confidence)"
        )
        output["summary"] = (
            "The AI model detected linguistic patterns common in fake news. "
            "Recommend manual verification."
        )
    elif l3_hint == "real" and l3_conf >= 0.80:
        output["verdict"] = "REAL"
        output["dominant_layer"] = f"Layer 3 ({l3_model})"
        output["confidence"] = l3_conf * 0.70  # discount slightly
        output["evidence"].append(
            f"🤖 {l3_model} classified this as real news ({l3_conf:.0%} confidence)"
        )
        output["summary"] = (
            "The AI model found this claim linguistically consistent with real news. "
            "Recommend manual verification."
        )
    else:
        # All layers are inconclusive
        output["verdict"] = "UNVERIFIED"
        output["confidence"] = 0.30
        output["dominant_layer"] = "None (insufficient evidence)"
        output["evidence"].append("⚠️  No layer found strong evidence for or against this claim")
        output["evidence"].append("⚠️  This may be too new, too obscure, or too ambiguous to classify")
        output["summary"] = (
            "The system cannot confidently verify this claim. "
            "Please check trusted news sources manually (NDTV, Reuters, BBC)."
        )

    # Always attach wiki context if found
    if l2_result.get("entity_verification", {}).get("verified_facts"):
        facts = l2_result["entity_verification"]["verified_facts"]
        for f in facts[:2]:
            output["evidence"].append(f"📖 Wikipedia: {f}")

    _attach_layer1_sources(output, l1_result)
    return output


def _attach_layer1_sources(output: dict, l1_result: dict):
    """Attach any found news articles to the output sources."""
    for art in l1_result.get("supporting_articles", [])[:4]:
        if art.get("url"):
            output["sources"].append(art["url"])
            if art.get("title"):
                output["evidence"].append(
                    f"📰 Related article: \"{art['title'][:80]}\" ({art.get('domain', '')})"
                )
