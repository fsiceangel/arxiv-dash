#!/usr/bin/env python3
"""Paper-level analysis from the Kaggle arXiv metadata snapshot (one-off).

Streams meta/arxiv-metadata-oai-snapshot.json and, for papers listing any of
our 32 math subfields, aggregates by first-version year:

1. Engagement analog: per-paper cross-listing among the 32 subfields
   (mean subfields/paper, share multi-subfield, entropy of pair types) —
   the counterpart of Hao et al.'s inter-paper engagement measure.
2. Mechanism test: AI/ML-related share per subfield-year via a conservative
   keyword classifier on title+abstract; correlation between a subfield's
   growth and its rise in AI share (permutation p-values).
3. Dedup robustness: effective number of subfields computed on PRIMARY
   categories (each paper counted once) vs the listing-based series.

Writes meta_data.js (window.META_DATA) and prints a summary.
"""
import json, math, os, re, sys
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "meta", "arxiv-metadata-oai-snapshot.json")

import gen_data
CATS = [c[0] for c in gen_data.CATS]
CATSET = set(CATS)
DATA_CLUSTER = {"cs.IT", "math.OC", "math.NA", "math.ST", "math.PR"}
YEARS = [str(y) for y in range(2017, 2027)]   # 2026 partial

AI_RE = re.compile(
    r"machine learning|deep learning|neural network|neural operator|"
    r"reinforcement learning|artificial intelligence|language model|"
    r"generative adversarial|autoencoder|graph neural|deep neural|"
    r"convolutional neural|physics-informed neural|attention mechanism|"
    r"transformer (?:model|network|architecture)s?", re.I)
LLM_RE = re.compile(r"\bLLMs?\b")             # case-sensitive on purpose

def ai_flag(title, abstract):
    txt = (title or "") + " " + (abstract or "")
    return bool(AI_RE.search(txt) or LLM_RE.search(txt))

def v1_year(rec):
    try:
        return rec["versions"][0]["created"].split()[3]
    except (KeyError, IndexError):
        return None

def shannon_bits(counter):
    tot = sum(counter.values())
    if not tot:
        return 0.0
    return -sum((v / tot) * math.log2(v / tot) for v in counter.values() if v)

def main():
    sub_n = defaultdict(Counter)      # year -> subfield -> papers listing it
    sub_ai = defaultdict(Counter)     # year -> subfield -> AI-flagged papers
    prim_n = defaultdict(Counter)     # year -> primary subfield -> papers
    pair_n = defaultdict(Counter)     # year -> (a,b) pair -> count
    eng = defaultdict(lambda: [0, 0, 0])  # year -> [papers, sum|cats|, multi]

    n_lines = n_kept = 0
    with open(SNAP, encoding="utf-8") as f:
        for line in f:
            n_lines += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cats = (rec.get("categories") or "").split()
            ours = [c for c in cats if c in CATSET]
            if not ours:
                continue
            yy = v1_year(rec)
            if yy not in YEARS:
                continue
            n_kept += 1
            flag = ai_flag(rec.get("title"), rec.get("abstract"))
            for c in ours:
                sub_n[yy][c] += 1
                if flag:
                    sub_ai[yy][c] += 1
            if cats and cats[0] in CATSET:
                prim_n[yy][cats[0]] += 1
            e = eng[yy]
            e[0] += 1; e[1] += len(ours); e[2] += 1 if len(ours) >= 2 else 0
            for a, b in combinations(sorted(ours), 2):
                pair_n[yy][(a, b)] += 1
            if n_lines % 500000 == 0:
                sys.stderr.write(f"  ...{n_lines} lines, kept {n_kept}\n")

    # engagement series
    engagement = {}
    for yy in YEARS:
        p, s, m = eng[yy]
        engagement[yy] = {
            "papers": p,
            "mean_subfields": round(s / p, 4) if p else None,
            "multi_share": round(m / p, 4) if p else None,
            "eff_pairs": round(2 ** shannon_bits(pair_n[yy]), 1),
        }

    # AI share series: cluster vs rest (subfield-listing weighted)
    ai_series = {"cluster": {}, "rest": {}, "all": {}}
    for yy in YEARS:
        for key, group in (("cluster", DATA_CLUSTER), ("rest", CATSET - DATA_CLUSTER),
                           ("all", CATSET)):
            n = sum(sub_n[yy][c] for c in group)
            a = sum(sub_ai[yy][c] for c in group)
            ai_series[key][yy] = round(a / n, 4) if n else None

    # per-subfield: growth (2017->2025, metadata-based) vs delta AI share
    points = []
    for c in CATS:
        n17, n25 = sub_n["2017"][c], sub_n["2025"][c]
        a17, a25 = sub_ai["2017"][c], sub_ai["2025"][c]
        if not (n17 and n25):
            continue
        points.append({
            "code": c, "cluster": c in DATA_CLUSTER,
            "growth": round(n25 / n17, 3),
            "ai17": round(a17 / n17, 4), "ai25": round(a25 / n25, 4),
            "d_ai": round(a25 / n25 - a17 / n17, 4),
        })

    x = np.array([p["d_ai"] for p in points])
    y = np.array([p["growth"] for p in points])
    def pearson(a, b):
        a = (a - a.mean()) / a.std(); b = (b - b.mean()) / b.std()
        return float((a * b).mean())
    def spearman(a, b):
        return pearson(np.argsort(np.argsort(a)).astype(float),
                       np.argsort(np.argsort(b)).astype(float))
    r_p, r_s = pearson(x, y), spearman(x, y)
    rng = np.random.default_rng(42)
    perm_p = float(np.mean([abs(pearson(rng.permutation(x), y)) >= abs(r_p)
                            for _ in range(10000)]))
    perm_s = float(np.mean([abs(spearman(rng.permutation(x), y)) >= abs(r_s)
                            for _ in range(10000)]))

    # dedup robustness: effective subfields on primary categories, annual
    dedup_E = {yy: round(2 ** shannon_bits(prim_n[yy]), 2) for yy in YEARS}

    out = {
        "years": YEARS,
        "engagement": engagement,
        "ai_series": ai_series,
        "points": points,
        "corr": {"pearson": round(r_p, 3), "p_pearson": round(perm_p, 4),
                 "spearman": round(r_s, 3), "p_spearman": round(perm_s, 4)},
        "dedup_eff_subfields": dedup_E,
        "n_papers_kept": n_kept,
    }
    with open(os.path.join(HERE, "meta_data.js"), "w", encoding="utf-8") as f:
        f.write("window.META_DATA = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")

    print(f"lines={n_lines} kept={n_kept}")
    print("engagement (papers, mean subfields, multi share, eff pairs):")
    for yy in YEARS:
        e = engagement[yy]
        print(f"  {yy}: {e['papers']:6d}  {e['mean_subfields']}  {e['multi_share']}  {e['eff_pairs']}")
    print("AI share cluster vs rest:")
    for yy in YEARS:
        print(f"  {yy}: cluster={ai_series['cluster'][yy]}  rest={ai_series['rest'][yy]}")
    print(f"corr growth~dAI: pearson={r_p:.3f} (p={perm_p:.4f})  "
          f"spearman={r_s:.3f} (p={perm_s:.4f})")
    print("dedup effective subfields:", {y: dedup_E[y] for y in ('2017','2021','2025')})
    top = sorted(points, key=lambda p: -p["d_ai"])[:5]
    print("top dAI:", [(p['code'], p['d_ai'], p['growth']) for p in top])

if __name__ == "__main__":
    main()
