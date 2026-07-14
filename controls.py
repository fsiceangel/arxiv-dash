#!/usr/bin/env python3
"""Non-math control group for the Feb-2026 surge question (§6).

Harvests monthly listing counts (2019-01..2026-06) for 13 non-math arXiv
categories, then computes each category's H1-2026 YoY ratio and a z-score
against its own H1-YoY history (2020/19..2025/24). Writes controls.csv
(resumable) and controls_data.js.
"""
import csv, math, os
import harvest

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "controls.csv")

GROUPS = {
    "cs.LG": "ai", "cs.CL": "ai", "cs.CV": "ai",
    "cs.CC": "cs", "cs.DS": "cs", "cs.PL": "cs", "cs.LO": "cs",
    "hep-th": "phys", "gr-qc": "phys", "quant-ph": "phys",
    "cond-mat.stat-mech": "phys",
    "econ.TH": "econ", "stat.ME": "econ",
}
NAMES = {
    "cs.LG": ("Machine Learning", "机器学习"),
    "cs.CL": ("Computation & Language", "计算与语言"),
    "cs.CV": ("Computer Vision", "计算机视觉"),
    "cs.CC": ("Computational Complexity", "计算复杂性"),
    "cs.DS": ("Data Structures & Algorithms", "数据结构与算法"),
    "cs.PL": ("Programming Languages", "编程语言"),
    "cs.LO": ("Logic in CS", "计算机科学中的逻辑"),
    "hep-th": ("High Energy Physics — Theory", "高能物理理论"),
    "gr-qc": ("General Relativity", "广义相对论"),
    "quant-ph": ("Quantum Physics", "量子物理"),
    "cond-mat.stat-mech": ("Statistical Mechanics", "统计力学"),
    "econ.TH": ("Economic Theory", "经济理论"),
    "stat.ME": ("Statistics Methodology", "统计方法"),
}

def months():
    for y in range(2019, 2027):
        for m in range(1, 13):
            if (y, m) > (2026, 6):
                return
            yield f"{y:04d}-{m:02d}"

def harvest_controls():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, newline="") as f:
            done = {(r[0], r[1]) for r in csv.reader(f) if len(r) >= 3 and r[0] != "category"}
    new_file = not os.path.exists(OUT)
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["category", "month", "count"])
        todo = [(c, ym) for c in GROUPS for ym in months() if (c, ym) not in done]
        print(f"fetching {len(todo)} cells...")
        for i, (c, ym) in enumerate(todo, 1):
            n = harvest.fetch(c, ym, retries=6)
            if n is None:
                print(f"FAIL {c} {ym}")
                continue
            w.writerow([c, ym, n]); f.flush()
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}")

def analyze():
    d = {}
    with open(OUT, newline="") as f:
        for r in csv.reader(f):
            if len(r) >= 3 and r[0] != "category":
                d.setdefault(r[0], {})[r[1]] = int(r[2])
    def h1(c, y):
        return sum(d[c].get(f"{y}-{m:02d}", 0) for m in range(1, 7))
    out = []
    for c in GROUPS:
        base = []
        for y in range(2020, 2026):
            a, b = h1(c, y - 1), h1(c, y)
            if a and b:
                base.append(math.log(b / a))
        a25, a26 = h1(c, 2025), h1(c, 2026)
        if not (a25 and a26 and len(base) >= 4):
            print(f"skip {c} (insufficient data)")
            continue
        lr = math.log(a26 / a25)
        mu = sum(base) / len(base)
        sd = (sum((x - mu) ** 2 for x in base) / (len(base) - 1)) ** 0.5
        out.append({
            "code": c, "group": GROUPS[c],
            "en": NAMES[c][0], "zh": NAMES[c][1],
            "r26": round(a26 / a25, 3),
            "base_med": round(math.exp(sorted(base)[len(base) // 2]), 3),
            "z": round((lr - mu) / sd, 2) if sd else None,
            "h1_25": a25, "h1_26": a26,
        })
    import json
    with open(os.path.join(HERE, "controls_data.js"), "w", encoding="utf-8") as f:
        f.write("window.CONTROLS_DATA = ")
        json.dump({"controls": out}, f, ensure_ascii=False)
        f.write(";\n")
    print(f"\n{'cat':20s} {'grp':5s} {'H1 26/25':>9s} {'base med':>9s} {'z':>6s}")
    for o in sorted(out, key=lambda x: -x["r26"]):
        print(f"{o['code']:20s} {o['group']:5s} {o['r26']:9.3f} {o['base_med']:9.3f} {str(o['z']):>6s}")

if __name__ == "__main__":
    harvest_controls()
    analyze()
