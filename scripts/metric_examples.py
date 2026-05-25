"""Compute evaluation metric examples for thesis Chapter 4 Section 4.2.

Compares our WaveDrom-specific metric against text-level similarity (Levenshtein ratio)
and BLEU to demonstrate structural advantages. All numbers in this script correspond to
Table 4.4 (tab:metric-comparison) in chap04.tex.

Usage:
    python scripts/metric_examples.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter

sys.path.insert(0, "/Users/tangbingda/wavedrom-llm")

import Levenshtein
from scoring import score_wavedrom_objects


def text_sim(gt_obj: dict, pred_obj: dict) -> float:
    return Levenshtein.ratio(json.dumps(gt_obj, ensure_ascii=False),
                            json.dumps(pred_obj, ensure_ascii=False))


def tokenize_json(obj: dict) -> list[str]:
    s = json.dumps(obj, ensure_ascii=False)
    tokens = []
    i = 0
    while i < len(s):
        if s[i] in '{}[],:':
            tokens.append(s[i])
            i += 1
        elif s[i] == '"':
            j = i + 1
            while j < len(s) and s[j] != '"':
                if s[j] == '\\':
                    j += 1
                j += 1
            tokens.append(s[i:j+1])
            i = j + 1
        elif s[i].isspace():
            i += 1
        else:
            j = i
            while j < len(s) and s[j] not in '{}[],:"\\ \t\n':
                j += 1
            tokens.append(s[i:j])
            i = j
    return tokens


def compute_bleu(ref_obj: dict, hyp_obj: dict, max_n: int = 4) -> float:
    ref_tokens = tokenize_json(ref_obj)
    hyp_tokens = tokenize_json(hyp_obj)
    if not hyp_tokens:
        return 0.0
    log_avg = 0.0
    weight = 1.0 / max_n
    for n in range(1, max_n + 1):
        ref_ngrams = Counter()
        for i in range(len(ref_tokens) - n + 1):
            ref_ngrams[tuple(ref_tokens[i:i+n])] += 1
        hyp_ngrams = Counter()
        for i in range(len(hyp_tokens) - n + 1):
            hyp_ngrams[tuple(hyp_tokens[i:i+n])] += 1
        clipped = sum(min(c, ref_ngrams[ng]) for ng, c in hyp_ngrams.items())
        total = max(len(hyp_tokens) - n + 1, 1)
        if clipped == 0:
            return 0.0
        log_avg += weight * math.log(clipped / total)
    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(len(hyp_tokens), 1)))
    return bp * math.exp(log_avg)


def show(label: str, gt: dict, pred: dict):
    p, r, f1, ok = score_wavedrom_objects(gt, pred)
    ts = text_sim(gt, pred)
    bleu = compute_bleu(gt, pred)
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"GT:   {json.dumps(gt, ensure_ascii=False)}")
    print(f"Pred: {json.dumps(pred, ensure_ascii=False)}")
    print(f"Text similarity (Levenshtein ratio): {ts:.4f}")
    print(f"BLEU: {bleu:.4f}")
    print(f"Our metric: P={p:.4f}, R={r:.4f}, F1={f1:.4f}")
    return ts, bleu, f1


# ── Scenario 1: Signal order permutation ──
gt1 = {"signal": [
    {"name": "clk", "wave": "101010"},
    {"name": "d",   "wave": "01.01."},
    {"name": "q",   "wave": "0.1.0."},
]}
pred1 = {"signal": [
    {"name": "q",   "wave": "0.1.0."},
    {"name": "d",   "wave": "01.01."},
    {"name": "clk", "wave": "101010"},
]}
show("Scenario 1: Signal order permutation", gt1, pred1)


# ── Scenario 2: Hold notation equivalence (dot vs explicit) ──
gt2 = {"signal": [
    {"name": "clk", "wave": "101010"},
    {"name": "en",  "wave": "0.1.0."},
    {"name": "d",   "wave": "0..1.."},
]}
pred2 = {"signal": [
    {"name": "clk", "wave": "101010"},
    {"name": "en",  "wave": "001100"},
    {"name": "d",   "wave": "000111"},
]}
show("Scenario 2: Hold notation equivalence (dot vs explicit)", gt2, pred2)


# ── Scenario 3a: Minor data label error (1/4 wrong) ──
gt3 = {"signal": [
    {"name": "clk", "wave": "10101010"},
    {"name": "cnt", "wave": "=.=.=.=.", "data": ["0", "1", "2", "3"]},
]}
pred3a = {"signal": [
    {"name": "clk", "wave": "10101010"},
    {"name": "cnt", "wave": "=.=.=.=.", "data": ["0", "1", "2", "4"]},
]}
show("Scenario 3a: Minor data label error (1/4)", gt3, pred3a)


# ── Scenario 3b: Major data label error (4/4 wrong) ──
pred3b = {"signal": [
    {"name": "clk", "wave": "10101010"},
    {"name": "cnt", "wave": "=.=.=.=.", "data": ["5", "6", "7", "8"]},
]}
show("Scenario 3b: Major data label error (4/4)", gt3, pred3b)


# ── Scenario 4: Missing signal (4 signals, 1 omitted) ──
gt4 = {"signal": [
    {"name": "clk", "wave": "101010"},
    {"name": "a",   "wave": "01.01."},
    {"name": "b",   "wave": "10.10."},
    {"name": "sum", "wave": "=.=.=.", "data": ["01", "11", "01"]},
]}
pred4 = {"signal": [
    {"name": "clk", "wave": "101010"},
    {"name": "a",   "wave": "01.01."},
    {"name": "sum", "wave": "=.=.=.", "data": ["01", "11", "01"]},
]}
show("Scenario 4: Missing signal (b omitted, 4->3)", gt4, pred4)
