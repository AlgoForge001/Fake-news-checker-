"""
examine.py — Main CLI entry point for the Fake News Examiner
Runs all 3 layers in sequence and displays a detailed verdict.

Usage:
    python examine.py
    python examine.py --no-bert    (skip BERT, faster but less accurate)
    python examine.py --query "your claim here"  (non-interactive)
"""

import sys
import os
import argparse
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import layer1_news_search, layer2_factcheck, layer3_bert_classifier, aggregator


VERDICT_DISPLAY = {
    "REAL": {
        "icon": "[OK]",
        "color_code": "\033[92m",   # Green
        "label": "LIKELY REAL NEWS"
    },
    "FAKE": {
        "icon": "[ERR]",
        "color_code": "\033[91m",   # Red
        "label": "LIKELY FAKE NEWS"
    },
    "MISLEADING": {
        "icon": "[WARN] ",
        "color_code": "\033[93m",   # Yellow
        "label": "MISLEADING / NEEDS CONTEXT"
    },
    "UNVERIFIED": {
        "icon": "[SEARCH]",
        "color_code": "\033[94m",   # Blue
        "label": "UNVERIFIED — CHECK MANUALLY"
    }
}

RESET = "\033[0m"
BOLD  = "\033[1m"


def confidence_bar(score: float, width: int = 35) -> str:
    """Draw a visual confidence bar."""
    filled = int(score * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score * 100:.1f}%"


def print_banner():
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  [SHIELD]  FAKE NEWS EXAMINER   3-Layer Verification System{RESET}")
    print(f"{BOLD}{'='*65}{RESET}")
    print("  Layers: Real-Time News Search | Fact-Check DB | BERT AI")
    print(f"{''*65}")


def print_verdict(result: dict, query: str, elapsed: float):
    verdict = result["verdict"]
    display = VERDICT_DISPLAY.get(verdict, VERDICT_DISPLAY["UNVERIFIED"])

    print(f"\n{''*65}")
    print(f"  CLAIM: \"{query[:80]}{'...' if len(query) > 80 else ''}\"")
    print(f"{''*65}")

    # Main Verdict
    color = display["color_code"]
    icon = display["icon"]
    label = display["label"]
    print(f"\n  {color}{BOLD}{icon}  {label}{RESET}")
    print(f"\n  Confidence   : {confidence_bar(result['confidence'])}")
    print(f"  Truth Score  : {result['truth_score']:.3f}  (0.0 = Fake  |  1.0 = Real)")
    print(f"  Decided By   : {result['dominant_layer']}")
    print(f"  Time Taken   : {elapsed:.2f}s")

    # Layer Summary
    lv = result["layer_verdicts"]
    print(f"\n  {''*61}")
    print(f"  [CHART] Layer Verdicts:")
    print(f"    Layer 1 (News Search)  : {lv['layer1'].upper()}")
    print(f"    Layer 2 (Fact-Check)   : {lv['layer2'].upper()}")
    print(f"    Layer 3 (BERT AI)      : {lv['layer3'].upper()}")

    # Summary
    print(f"\n  {''*61}")
    print(f"  [NOTE] Summary:")
    print(f"    {result['summary']}")

    # Evidence
    if result["evidence"]:
        print(f"\n  {''*61}")
        print(f"  [SEARCH] Evidence:")
        for ev in result["evidence"][:6]:
            print(f"    {ev}")

    # Sources
    unique_sources = list(dict.fromkeys(result["sources"]))  # deduplicate
    if unique_sources:
        print(f"\n  {''*61}")
        print(f"  [LINK] Sources to Check:")
        for src in unique_sources[:4]:
            print(f"     {src}")

    print(f"\n{'='*65}\n")


def examine(query: str, use_bert: bool = True) -> dict:
    """
    Run the full 3-layer examination pipeline on a claim.
    Returns the full aggregated result dict.
    """
    print(f"\n  [WAIT] Checking claim across all layers...")

    # ── Layer 2 first (fastest for known claims, no rate limits)
    print(f"  [SEARCH] Layer 2: Fact-check databases + Wikipedia...")
    l2_result = layer2_factcheck.run(query)

    # ── Layer 1 (GDELT + NewsAPI)
    print(f"  [SIGNAL] Layer 1: Real-time news search (GDELT + NewsAPI)...")
    l1_result = layer1_news_search.run(query)

    # ── Layer 3 (BERT) — skip if layer 2 already decided with high confidence
    l2_conf = l2_result.get("confidence", 0)
    l2_hint = l2_result.get("verdict_hint", "unverified")

    if l2_conf >= 0.95 and l2_hint in ("fake", "real"):
        # Fast path: fact-checker already decided, no need for BERT
        print(f"  [BERT] Layer 3: Skipped (fact-check was definitive)")
        l3_result = {
            "verdict_hint": "skipped",
            "truth_score": 0.5,
            "confidence": 0.5,
            "model_used": "Skipped",
            "layer": "Layer 3 — ML Classifier"
        }
    else:
        print(f"  [BERT] Layer 3: BERT AI linguistic analysis...")
        l3_result = layer3_bert_classifier.run(query, use_bert=use_bert)

    # ── Aggregate all results
    final = aggregator.aggregate(l1_result, l2_result, l3_result)
    return final


def main():
    parser = argparse.ArgumentParser(
        description="[SHIELD] Fake News Examiner — 3-Layer Verification"
    )
    parser.add_argument("--query", "-q", type=str, help="News claim to check")
    parser.add_argument("--no-bert", action="store_true",
                        help="Skip BERT model (faster, uses legacy TF-IDF instead)")
    args = parser.parse_args()

    print_banner()

    use_bert = not args.no_bert

    if not use_bert:
        print("   Fast mode: Using legacy TF-IDF model (BERT disabled)")

    while True:
        # Get query
        if args.query:
            query = args.query.strip()
            args.query = None  # Only use it once, then go interactive
        else:
            print()
            query = input("  [NEWS] Enter news claim to verify (or 'quit' to exit):\n  > ").strip()

        if query.lower() in ("quit", "exit", "q", ""):
            print("\n  Goodbye! Stay informed. [WAVE]\n")
            break

        if len(query) < 5:
            print("  [WARN]  Please enter a longer claim (at least 5 characters).")
            continue

        start = time.time()
        result = examine(query, use_bert=use_bert)
        elapsed = time.time() - start

        print_verdict(result, query, elapsed)

        if args.query:
            break  # Non-interactive mode exits after one query


if __name__ == "__main__":
    main()
