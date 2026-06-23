#!/usr/bin/env python3
"""Comparative 'focus contraction' analysis for arXiv mathematics, inspired by
Hao, Xu, Li & Evans, Nature 2026 (s41586-025-09922-y / arXiv:2412.07727):
'AI tools expand scientists' impact but contract science's focus.'

We cannot measure citations or AI-augmentation from listing counts. Instead we
test the *structural* analog: is mathematics' collective output concentrating
across its 32 subfields over 2017-2026, and is growth skewing toward the
data-rich / ML-adjacent subfields (the math counterpart of 'areas richest in
data')? Outputs report_data.js for the website and prints a summary.
"""
import csv, json, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

# reuse the canonical category list + names
import gen_data
CATS = gen_data.CATS                       # (code, en, zh)
NAME = {c[0]: (c[1], c[2]) for c in CATS}
CODES = [c[0] for c in CATS]

# Computational / data-driven / ML-adjacent cluster (the "data-rich" areas).
DATA_CLUSTER = ["cs.IT", "math.OC", "math.NA", "math.ST", "math.PR"]

def load():
    raw = defaultdict(dict)   # code -> {YYYY-MM: count}
    with open(os.path.join(HERE, "data.csv"), newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 3 and row[1] != "month":
                raw[row[0]][row[1]] = int(row[2])
    return raw

def yearly(raw, full_only=True):
    """code -> {year:int -> total}. 2026 is partial (Jan-Jun)."""
    out = defaultdict(lambda: defaultdict(int))
    for code, d in raw.items():
        for ym, n in d.items():
            y = int(ym[:4])
            out[code][y] += n
    return out

def shannon_bits(shares):
    return -sum(p * math.log2(p) for p in shares if p > 0)

def gini(vals):
    v = sorted(vals)
    n = len(v)
    if n == 0 or sum(v) == 0:
        return 0.0
    cum = 0
    for i, x in enumerate(v, 1):
        cum += i * x
    return (2 * cum) / (n * sum(v)) - (n + 1) / n

def main():
    raw = load()
    yr = yearly(raw)
    YEARS = list(range(2017, 2027))         # 2026 partial
    FULL = list(range(2017, 2026))          # complete years for trend stats

    # ---- per-year concentration / diversity metrics ----
    metrics = {}   # year -> {...}
    for y in YEARS:
        counts = [yr[c].get(y, 0) for c in CODES]
        tot = sum(counts)
        shares = [c / tot for c in counts] if tot else [0] * len(counts)
        H = shannon_bits(shares)
        Hmax = math.log2(len(CODES))
        hhi = sum(s * s for s in shares)
        ranked = sorted(shares, reverse=True)
        metrics[y] = {
            "total": tot,
            "entropy_bits": round(H, 4),
            "evenness": round(H / Hmax, 4),                 # Pielou
            "eff_subfields": round(2 ** H, 2),              # effective # of equally-active fields
            "hhi": round(hhi, 5),
            "top5_share": round(sum(ranked[:5]), 4),
            "gini": round(gini(counts), 4),
            "data_cluster_share": round(
                sum(yr[c].get(y, 0) for c in DATA_CLUSTER) / tot, 4) if tot else 0,
            "partial": y == 2026,
        }

    # ---- per-category growth 2017 -> 2025 (full years) ----
    growth = []
    for code in CODES:
        a = yr[code].get(2017, 0)
        b = yr[code].get(2025, 0)
        ratio = (b / a) if a else None
        cagr = ((b / a) ** (1 / 8) - 1) if (a and b) else None
        growth.append({
            "code": code, "en": NAME[code][0], "zh": NAME[code][1],
            "y2017": a, "y2025": b,
            "ratio": round(ratio, 3) if ratio else None,
            "cagr": round(cagr * 100, 2) if cagr is not None else None,
            "data_cluster": code in DATA_CLUSTER,
        })
    growth.sort(key=lambda g: (g["ratio"] is None, -(g["ratio"] or 0)))

    # ---- pre/post-LLM split (ChatGPT = late 2022) ----
    def avg(metric, years):
        vals = [metrics[y][metric] for y in years]
        return sum(vals) / len(vals)
    pre, post = [2017, 2018, 2019, 2020, 2021, 2022], [2023, 2024, 2025]
    split = {
        "pre_years": pre, "post_years": post,
        "eff_subfields": {"pre": round(avg("eff_subfields", pre), 2),
                          "post": round(avg("eff_subfields", post), 2)},
        "evenness": {"pre": round(avg("evenness", pre), 4),
                     "post": round(avg("evenness", post), 4)},
        "top5_share": {"pre": round(avg("top5_share", pre), 4),
                       "post": round(avg("top5_share", post), 4)},
        "data_cluster_share": {"pre": round(avg("data_cluster_share", pre), 4),
                               "post": round(avg("data_cluster_share", post), 4)},
        "total": {"pre": round(avg("total", pre)), "post": round(avg("total", post))},
    }

    out = {
        "years": YEARS, "full_years": FULL,
        "metrics": metrics, "growth": growth, "split": split,
        "data_cluster": DATA_CLUSTER,
        "data_cluster_names": {c: NAME[c][0] for c in DATA_CLUSTER},
        "n_categories": len(CODES),
    }
    with open(os.path.join(HERE, "report_data.js"), "w", encoding="utf-8") as f:
        f.write("window.REPORT_DATA = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")

    # ---- console summary ----
    print("year  total  effFields  evenness  top5%   HHI    dataCluster%")
    for y in YEARS:
        m = metrics[y]
        tag = " (partial)" if m["partial"] else ""
        print(f"{y}  {m['total']:6d}   {m['eff_subfields']:6.2f}   {m['evenness']:.4f}  "
              f"{m['top5_share']*100:5.1f}  {m['hhi']:.4f}  {m['data_cluster_share']*100:5.1f}{tag}")
    print("\nPre-LLM (2017-22) vs Post-LLM (2023-25):")
    for k in ["eff_subfields", "evenness", "top5_share", "data_cluster_share"]:
        print(f"  {k:20s} {split[k]['pre']}  ->  {split[k]['post']}")
    print("\nTop 6 growers 2017->2025 (ratio):")
    for g in growth[:6]:
        print(f"  {g['code']:9s} {g['en']:28s} x{g['ratio']}  CAGR {g['cagr']}%  {'[DATA]' if g['data_cluster'] else ''}")
    print("Bottom 6 growers:")
    for g in growth[-6:]:
        print(f"  {g['code']:9s} {g['en']:28s} x{g['ratio']}  CAGR {g['cagr']}%  {'[DATA]' if g['data_cluster'] else ''}")

if __name__ == "__main__":
    main()
