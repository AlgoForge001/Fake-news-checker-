"""
layer3_bert_classifier.py — BERT-based Linguistic Fake News Detection
Uses a pretrained RoBERTa model fine-tuned on 70,000+ real and fake articles.

Model: hamzab/roberta-fake-news-classification (HuggingFace)
Download: ~500MB, happens automatically on first run, cached after that.

Unlike the old TF-IDF model, BERT:
  ✓ Understands full sentence context (not just word counts)
  ✓ Works for ANY topic (not just 2016 US politics)
  ✓ Detects manipulative writing patterns
  ✓ Handles negation ("NOT true" ≠ "true")
  
This layer acts as the intelligent tiebreaker when Layers 1 & 2 are inconclusive.
"""

import sys
import os
import pickle
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Global model cache (loaded once, reused)
_bert_pipeline = None
_legacy_model = None


def _load_bert_model():
    """Load the BERT model (downloads once, cached forever)."""
    global _bert_pipeline
    if _bert_pipeline is not None:
        return _bert_pipeline

    try:
        from transformers import pipeline as hf_pipeline
        print("[BERT] Loading model (first run downloads ~500MB)...")
        _bert_pipeline = hf_pipeline(
            "text-classification",
            model=config.BERT_MODEL_NAME,
            truncation=True,
            max_length=512
        )
        print("[BERT] Model loaded successfully")
        return _bert_pipeline
    except Exception as e:
        print(f"[BERT] Could not load model: {e}")
        return None


def _load_legacy_model():
    """Fallback: load the original TF-IDF + Logistic Regression model."""
    global _legacy_model
    if _legacy_model is not None:
        return _legacy_model
    try:
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "final_model.sav"
        )
        with open(model_path, "rb") as f:
            _legacy_model = pickle.load(f)
        return _legacy_model
    except Exception as e:
        print(f"[WARN]  Could not load legacy model: {e}")
        return None


def _preprocess(text: str) -> str:
    """Clean input text for the model."""
    text = text.strip()
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)
    # Truncate to safe length
    if len(text) > 1000:
        text = text[:1000]
    return text


def _run_bert(text: str) -> dict:
    """Run BERT classification."""
    model = _load_bert_model()
    if model is None:
        return {"error": "BERT model unavailable", "score": 0.5, "label": "UNKNOWN"}

    try:
        result = model(text)[0]
        label = result["label"].upper()  # "FAKE" or "REAL"
        confidence = result["score"]

        # Normalize to truth_score (0=fake, 1=real)
        if "FAKE" in label or label == "LABEL_0":
            truth_score = 1.0 - confidence
        else:
            truth_score = confidence

        return {
            "model": "BERT (RoBERTa)",
            "raw_label": label,
            "raw_confidence": confidence,
            "truth_score": truth_score,
            "error": None
        }
    except Exception as e:
        return {"error": str(e), "score": 0.5, "label": "ERROR"}


def _run_legacy(text: str) -> dict:
    """Run the old TF-IDF + Logistic Regression model as fallback."""
    model = _load_legacy_model()
    if model is None:
        return {"error": "Legacy model unavailable", "truth_score": 0.5}

    try:
        probs = model.predict_proba([text])[0]
        # probs[1] = probability of True, probs[0] = probability of False
        truth_score = probs[1]
        return {
            "model": "TF-IDF + Logistic Regression (legacy)",
            "truth_score": truth_score,
            "error": None
        }
    except Exception as e:
        return {"error": str(e), "truth_score": 0.5}


def run(query: str, use_bert: bool = True) -> dict:
    """
    Run Layer 3 ML classification.
    
    Args:
        query: The news claim text to classify
        use_bert: If True, use BERT; if False, use legacy TF-IDF model
    
    Returns:
        dict with verdict_hint, truth_score, confidence, model_used
    """
    text = _preprocess(query)

    output = {
        "layer": "Layer 3 — ML Classifier",
        "query": query,
        "bert_result": None,
        "legacy_result": None,
        "truth_score": 0.5,
        "verdict_hint": "unverified",
        "confidence": 0.5,
        "model_used": None
    }

    if use_bert:
        bert_result = _run_bert(text)
        output["bert_result"] = bert_result

        if not bert_result.get("error"):
            output["truth_score"] = bert_result["truth_score"]
            output["model_used"] = bert_result["model"]

            if bert_result["truth_score"] >= 0.70:
                output["verdict_hint"] = "real"
                output["confidence"] = bert_result["raw_confidence"]
            elif bert_result["truth_score"] <= 0.30:
                output["verdict_hint"] = "fake"
                output["confidence"] = bert_result["raw_confidence"]
            else:
                output["verdict_hint"] = "uncertain"
                output["confidence"] = 0.4

            return output

    # Fallback to legacy model
    legacy_result = _run_legacy(text)
    output["legacy_result"] = legacy_result
    output["model_used"] = legacy_result.get("model", "legacy")

    truth_score = legacy_result.get("truth_score", 0.5)
    output["truth_score"] = truth_score

    # Legacy model needs higher thresholds (less reliable)
    if truth_score >= 0.78:
        output["verdict_hint"] = "real"
        output["confidence"] = truth_score
    elif truth_score <= 0.22:
        output["verdict_hint"] = "fake"
        output["confidence"] = 1.0 - truth_score
    else:
        output["verdict_hint"] = "uncertain"
        output["confidence"] = 0.3

    return output


if __name__ == "__main__":
    queries = [
        "does the age of pm modi is 100 years old",
        "The unemployment rate has dropped to its lowest in 50 years",
        "Barack Obama faked the moon landing",
        "India launches mission to the sun",
    ]
    for q in queries:
        print(f"\n{'='*60}")
        print(f"Query: {q}")
        # Try BERT first, fall back to legacy if unavailable
        result = run(q, use_bert=True)
        print(f"Model Used   : {result['model_used']}")
        print(f"Truth Score  : {result['truth_score']:.3f} (0=fake, 1=real)")
        print(f"Verdict Hint : {result['verdict_hint']}")
        print(f"Confidence   : {result['confidence']:.3f}")
