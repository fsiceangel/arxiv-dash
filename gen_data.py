#!/usr/bin/env python3
"""Turn harvested data.csv into data.js (window.ARXIV_DATA) for the dashboard."""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# category -> (English name, Chinese name), in PDF order
CATS = [
    ("math.AG", "Algebraic Geometry", "代数几何"),
    ("math.AT", "Algebraic Topology", "代数拓扑"),
    ("math.AP", "Analysis of PDEs", "偏微分方程分析"),
    ("math.CT", "Category Theory", "范畴论"),
    ("math.CA", "Classical Analysis & ODEs", "经典分析与常微分方程"),
    ("math.CO", "Combinatorics", "组合数学"),
    ("math.AC", "Commutative Algebra", "交换代数"),
    ("math.CV", "Complex Variables", "复变函数"),
    ("math.DG", "Differential Geometry", "微分几何"),
    ("math.DS", "Dynamical Systems", "动力系统"),
    ("math.FA", "Functional Analysis", "泛函分析"),
    ("math.GM", "General Mathematics", "一般数学"),
    ("math.GN", "General Topology", "一般拓扑"),
    ("math.GT", "Geometric Topology", "几何拓扑"),
    ("math.GR", "Group Theory", "群论"),
    ("math.HO", "History & Overview", "数学史与综述"),
    ("cs.IT",   "Information Theory", "信息论"),
    ("math.KT", "K-Theory & Homology", "K理论与同调"),
    ("math.LO", "Logic", "数理逻辑"),
    ("math-ph", "Mathematical Physics", "数学物理"),
    ("math.MG", "Metric Geometry", "度量几何"),
    ("math.NT", "Number Theory", "数论"),
    ("math.NA", "Numerical Analysis", "数值分析"),
    ("math.OA", "Operator Algebras", "算子代数"),
    ("math.OC", "Optimization & Control", "最优化与控制"),
    ("math.PR", "Probability", "概率论"),
    ("math.QA", "Quantum Algebra", "量子代数"),
    ("math.RT", "Representation Theory", "表示论"),
    ("math.RA", "Rings & Algebras", "环与代数"),
    ("math.SP", "Spectral Theory", "谱理论"),
    ("math.ST", "Statistics Theory", "统计理论"),
    ("math.SG", "Symplectic Geometry", "辛几何"),
]

def months(start=(2017, 1), end=(2026, 6)):
    y, m = start
    out = []
    while (y, m) <= end:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out

def main():
    MONTHS = months()
    raw = {c[0]: {} for c in CATS}
    with open(os.path.join(HERE, "data.csv"), newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 3 and row[0] in raw and row[1] != "month":
                try:
                    raw[row[0]][row[1]] = int(row[2])
                except ValueError:
                    pass
    series = []
    missing = 0
    for code, en, zh in CATS:
        counts = [raw[code].get(m) for m in MONTHS]
        missing += sum(1 for v in counts if v is None)
        # base = Jan 2017 value (index 0); guard against missing/zero
        base = counts[0]
        if not base:
            base = next((v for v in counts if v), None)
        norm = [round(v / base, 4) if (v is not None and base) else None for v in counts]
        series.append({"code": code, "en": en, "zh": zh, "raw": counts, "norm": norm})
    data = {"months": MONTHS, "base_month": MONTHS[0], "series": series}
    with open(os.path.join(HERE, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.ARXIV_DATA = ")
        json.dump(data, f, ensure_ascii=False)
        f.write(";\n")
    print(f"wrote data.js: {len(series)} categories x {len(MONTHS)} months; missing cells={missing}")

if __name__ == "__main__":
    main()
