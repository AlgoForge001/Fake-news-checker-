# -*- coding: utf-8 -*-
"""
Created on Mon Dec  4 17:45:40 2017

@author: NishitP

Updated: Added confidence threshold and uncertainty detection.
  - Model only labels True if confidence >= 75%
  - Model only labels False if confidence <= 25%
  - Anything in between is flagged as UNCERTAIN (model doesn't know)
"""

import pickle

var = input("Please enter the news text you want to verify: ")
print("You entered: " + str(var))
print("-" * 60)

# Confidence threshold - only trust the model if it is very sure
TRUE_THRESHOLD  = 0.75   # must be 75%+ confident to say True
FALSE_THRESHOLD = 0.25   # must be 25% or less to say False

def confidence_bar(prob, width=30):
    """Visual bar showing how confident the model is."""
    filled = int(prob * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {prob * 100:.1f}%"

def detecting_fake_news(var):
    load_model = pickle.load(open('final_model.sav', 'rb'))
    prob = load_model.predict_proba([var])
    truth_prob  = prob[0][1]   # probability of being True
    false_prob  = prob[0][0]   # probability of being False

    print(f"\n📊 Truth Probability : {confidence_bar(truth_prob)}")
    print(f"📊 False Probability : {confidence_bar(false_prob)}")
    print()

    if truth_prob >= TRUE_THRESHOLD:
        print("✅ Verdict: LIKELY TRUE")
        print(f"   The model is {truth_prob * 100:.1f}% confident this is true.")
    elif truth_prob <= FALSE_THRESHOLD:
        print("❌ Verdict: LIKELY FALSE")
        print(f"   The model is {false_prob * 100:.1f}% confident this is false.")
    else:
        print("⚠️  Verdict: UNCERTAIN — Model cannot confidently decide.")
        print(f"   Truth score is only {truth_prob * 100:.1f}% (need ≥75% for True, ≤25% for False).")
        print("   This usually means the topic is outside the model's training data.")
        print("   Tip: Manually verify this statement using a trusted news source.")

    print("-" * 60)

if __name__ == '__main__':
    detecting_fake_news(var)