#!/usr/bin/env python3
"""Independent audit of the study's data, methods, and results.

A. Data integrity (data.csv, controls.csv).
B. Independent recomputation of headline numbers vs published JS artifacts.
C. Synthetic-data validation of the sup-F implementation.
D. Placebo DiD (random pseudo-cluster should show ~no effect).
E. Consistency of numbers quoted in index.html prose vs artifacts.
"""
import csv, json, math, os, re, sys
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    tag = "PASS" if cond else "FAIL"
    if cond: ok += 1
    else: fail += 1
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))

def load_js(fn):
    t = open(os.path.join(HERE, fn), encoding="utf-8").read()
    return json.loads(t[t.index("{"):t.rindex("}")+1])

# ---------- A. data integrity ----------
print("=== A. Data integrity ===")
rows = list(csv.reader(open(os.path.join(HERE, "data.csv"))))[1:]
keys = [(r[0], r[1]) for r in rows]
check("data.csv no duplicate (cat,month)", len(keys) == len(set(keys)), f"{len(keys)} rows")
cats = sorted({r[0] for r in rows})
months = sorted({r[1] for r in rows})
check("32 categories", len(cats) == 32, str(len(cats)))
exp_months = [f"{y}-{m:02d}" for y in range(2017, 2027) for m in range(1, 13)
              if (y, m) <= (2026, 7)]
check("months contiguous 2017-01..2026-07", months == exp_months,
      f"{months[0]}..{months[-1]} n={len(months)}")
check("complete grid", len(rows) == 32 * len(months), f"{len(rows)} vs {32*len(months)}")
counts = {(r[0], r[1]): int(r[2]) for r in rows}
check("all counts > 0", all(v > 0 for v in counts.values()),
      f"min={min(counts.values())}")
crows = list(csv.reader(open(os.path.join(HERE, "controls.csv"))))[1:]
ckeys = {(r[0], r[1]) for r in crows}
check("controls.csv complete 13x90", len(ckeys) == 13 * 90, f"{len(ckeys)}")

# ---------- B. independent recomputation ----------
print("\n=== B. Recomputation vs published artifacts ===")
RD = load_js("report_data.js"); SD = load_js("stats_data.js"); MD = load_js("meta_data.js")

def year_counts(y):
    return np.array([sum(counts[(c, f"{y}-{m:02d}")] for m in range(1, 13)) for c in cats])

def eff(v):
    p = v / v.sum()
    return 2 ** (-(p[p > 0] * np.log2(p[p > 0])).sum())

for y, exp in [(2017, 24.23), (2021, 23.44), (2025, 23.49)]:
    e = eff(year_counts(y))
    check(f"E({y}) fresh vs report", abs(e - RD["metrics"][str(y)]["eff_subfields"]) < 0.01,
          f"fresh={e:.3f} published={RD['metrics'][str(y)]['eff_subfields']}")
v17, v25 = year_counts(2017), year_counts(2025)
top5_17 = np.sort(v17 / v17.sum())[::-1][:5].sum()
top5_25 = np.sort(v25 / v25.sum())[::-1][:5].sum()
check("top5 2017=36.6%", abs(top5_17 - 0.366) < 0.002, f"{top5_17:.4f}")
check("top5 2025=38.8%", abs(top5_25 - 0.388) < 0.002, f"{top5_25:.4f}")
CLUSTER = ["cs.IT", "math.OC", "math.NA", "math.ST", "math.PR"]
cl17 = sum(v17[cats.index(c)] for c in CLUSTER) / v17.sum()
cl25 = sum(v25[cats.index(c)] for c in CLUSTER) / v25.sum()
check("cluster share 26.8%->30.3%", abs(cl17-0.268)<0.002 and abs(cl25-0.303)<0.002,
      f"{cl17:.4f}->{cl25:.4f}")
for c, exp in [("math.OC", 2.282), ("math.NA", 1.968), ("math.ST", 1.951),
               ("math.CA", 0.988), ("math.CV", 1.259)]:
    g = year_counts(2025)[cats.index(c)] / year_counts(2017)[cats.index(c)]
    check(f"growth {c} ×{exp}", abs(g - exp) < 0.005, f"fresh={g:.3f}")

# monthly E series identical to stats_data (complete months < 2026-07)
mvalid = [m for m in months if m < "2026-07"]
Efresh = []
for m in mvalid:
    v = np.array([counts[(c, m)] for c in cats]); Efresh.append(eff(v))
check("monthly E series matches stats_data",
      SD["months"] == mvalid and max(abs(a-b) for a,b in zip(Efresh, SD["E_monthly"])) < 0.01,
      f"n={len(mvalid)} maxdiff={max(abs(a-b) for a,b in zip(Efresh, SD['E_monthly'])):.4f}")

# H1 2026 surge facts quoted in §4.4
def h1(c, y): return sum(counts[(c, f"{y}-{m:02d}")] for m in range(1, 7))
r26 = {c: h1(c, 2026) / h1(c, 2025) for c in cats}
r25 = {c: h1(c, 2025) / h1(c, 2024) for c in cats}
med26 = float(np.median(list(r26.values()))); med25 = float(np.median(list(r25.values())))
check("surge median +22.5% (text)", abs(med26 - 1.225) < 0.005, f"{med26:.4f}")
check("baseline median +1.8% (text)", abs(med25 - 1.018) < 0.005, f"{med25:.4f}")
check("30/32 subfields >+10%", sum(1 for v in r26.values() if v > 1.10) == 30)
check("math.CO +41% / math.LO +38% / math.DS +35%",
      abs(r26["math.CO"]-1.408)<0.01 and abs(r26["math.LO"]-1.380)<0.01
      and abs(r26["math.DS"]-1.354)<0.01,
      f"CO={r26['math.CO']:.3f} LO={r26['math.LO']:.3f} DS={r26['math.DS']:.3f}")
# meta surge consistency
ms = {s["code"]: s["r26"] for s in MD["surge"]}
maxd = max(abs(ms[c] - r26[c]) for c in cats if c in ms)
check("meta_data surge == fresh from data.csv", maxd < 0.002, f"maxdiff={maxd:.4f}")

# ---------- C. synthetic validation of sup-F ----------
print("\n=== C. sup-F synthetic validation ===")
sys.path.insert(0, HERE)
import stats_analysis as SA
rng = np.random.default_rng(123)
n = 114; t = np.arange(n)
# no break: p should be large most of the time
y0 = 24 - 0.005 * t + rng.normal(0, 0.15, n)
tau0, f0, p0, _ = SA.sup_F_test(y0, n_boot=200)
check("sup-F: no-break series -> insignificant", p0 > 0.05, f"supF={f0:.1f} p={p0:.3f}")
# planted level+slope break at index 45
y1 = 24 - 0.001 * t - (t >= 45) * (0.4 + 0.004 * (t - 45)) + rng.normal(0, 0.08, n)
tau1, f1, p1, _ = SA.sup_F_test(y1, n_boot=200)
check("sup-F: planted break at 45 detected", abs(tau1 - 45) <= 6 and p1 < 0.05,
      f"tau={tau1} supF={f1:.1f} p={p1:.3f}")
# published break stats reproduce
E = np.array(SD["E_monthly"])
i_best = SD["months"].index(SD["break"]["month"])
f_best = SA.break_F(E, i_best)
check("published supF reproduces", abs(f_best - SD["break"]["supF"]) < 0.1,
      f"F({SD['break']['month']})={f_best:.2f} vs {SD['break']['supF']}")
f_llm = SA.break_F(E, SD["months"].index("2022-12"))
f_cov = SA.break_F(E, SD["months"].index("2020-03"))
check("F@ChatGPT=1.68, F@COVID=5.41 reproduce",
      abs(f_llm - 1.68) < 0.05 and abs(f_cov - 5.41) < 0.05,
      f"llm={f_llm:.2f} covid={f_cov:.2f}")

# ---------- D. placebo DiD ----------
print("\n=== D. DiD checks ===")
M = np.array([[counts[(c, m)] for m in mvalid] for c in cats], dtype=float)
did, event, _ = SA.did_analysis(cats, mvalid, M)
check("DiD treat_post reproduces (+0.1104, p=.075)",
      abs(did["treat_post"]["coef"] - 0.1104) < 0.005 and abs(did["treat_post"]["p"] - 0.075) < 0.02,
      f"coef={did['treat_post']['coef']} p={did['treat_post']['p']}")
# placebo: random 5-category pseudo-clusters
import itertools
prng = np.random.default_rng(99)
placebo_ps = []
orig_cluster = SA.DATA_CLUSTER
for rep in range(8):
    fake = set(prng.choice([c for c in cats], size=5, replace=False))
    SA.DATA_CLUSTER = fake
    d2, _, _ = SA.did_analysis(cats, mvalid, M)
    placebo_ps.append(abs(d2["treat_post"]["coef"]))
SA.DATA_CLUSTER = orig_cluster
check("placebo clusters: |coef| mostly < real",
      sum(1 for v in placebo_ps if v < 0.1104) >= 5,
      f"placebo |coefs|={[round(v,3) for v in placebo_ps]}")

# ---------- E. prose consistency ----------
print("\n=== E. Prose numbers vs artifacts ===")
html = open(os.path.join(HERE, "index.html"), encoding="utf-8").read()
quoted = {
    "24.2 to 23.5": abs(RD["metrics"]["2017"]["eff_subfields"] - 24.23) < 0.01
                    and abs(RD["metrics"]["2025"]["eff_subfields"] - 23.49) < 0.01,
    "optimization +128%": abs(next(g for g in RD["growth"] if g["code"]=="math.OC")["ratio"] - 2.282) < 0.01,
    "Spearman 0.425 / p 0.016": MD["corr"]["spearman"] == 0.425 and abs(MD["corr"]["p_spearman"]-0.0163)<0.002,
    "cluster AI 2.9->13.5": MD["ai_series"]["cluster"]["2017"] == 0.0291 and MD["ai_series"]["cluster"]["2025"] == 0.1349,
    "engagement 1.31->1.36 / 24.2->28.1": abs(MD["engagement"]["2017"]["mean_subfields"]-1.3113)<0.001
                    and abs(MD["engagement"]["2025"]["multi_share"]-0.2812)<0.001,
    "dedup 23.27->22.08": MD["dedup_eff_subfields"]["2017"] == 23.27 and MD["dedup_eff_subfields"]["2025"] == 22.08,
    "surge corr 0.318/p .078": MD["surge_corr"]["spearman"] == 0.318 and abs(MD["surge_corr"]["p_spearman"]-0.0781)<0.005,
    "break Oct 2020/supF 5.5/p .43": SD["break"]["month"] == "2020-10" and SD["break"]["supF"] == 5.5,
    "pretrend gap 0.63": abs(SD["pretrend_gap_post2023"] + 0.63) < 0.01,
}
for k, v in quoted.items():
    check(f"quoted: {k}", v)
for s in ["24.2 to 23.5", "+128%", "0.425", "2.9% → 13.5%", "October 2020",
          "5.41", "1.68", "+22.5%", "30 of 32", "z = 5.8", "448,970",
          "F = 5.85", "F = 2.66"]:
    check(f"string present in html: '{s}'", s in html)

# 2026 predictive-failure test: reproduce independently
pred = SD.get("pred_2026")
check("pred_2026 present in stats_data", pred is not None)
if pred:
    fit_idx = [i for i, m in enumerate(mvalid) if "2021-01" <= m <= "2025-12"]
    tst_idx = [i for i, m in enumerate(mvalid) if m >= "2026-01"]
    tt = np.arange(len(mvalid), dtype=float)
    Ea = np.array(Efresh)
    Xf = np.column_stack([np.ones(len(fit_idx)), tt[fit_idx]])
    b, *_ = np.linalg.lstsq(Xf, Ea[fit_idx], rcond=None)
    rf = Ea[fit_idx] - Xf @ b
    s2 = float(rf @ rf) / (len(fit_idx) - 2)
    e = Ea[tst_idx] - (b[0] + b[1] * tt[tst_idx])
    F_E = float(e @ e) / len(tst_idx) / s2
    check("pred F(E) reproduces", abs(F_E - pred["E"]["F"]) < 0.05,
          f"fresh={F_E:.2f} published={pred['E']['F']}")
    tot = np.array([sum(counts[(c, m)] for c in cats) for m in mvalid], dtype=float)
    y = np.log(tot)
    b2, *_ = np.linalg.lstsq(Xf, y[fit_idx], rcond=None)
    rf2 = y[fit_idx] - Xf @ b2
    s22 = float(rf2 @ rf2) / (len(fit_idx) - 2)
    e2 = y[tst_idx] - (b2[0] + b2[1] * tt[tst_idx])
    F_T = float(e2 @ e2) / len(tst_idx) / s22
    check("pred F(log total) reproduces", abs(F_T - pred["log_total"]["F"]) < 0.05,
          f"fresh={F_T:.2f} published={pred['log_total']['F']}")
    check("2026 concentration deviates DOWN", pred["E"]["mean_dev"] < -0.2,
          f"mean_dev={pred['E']['mean_dev']}")
    check("2026 output deviates UP", pred["log_total"]["mean_dev"] > 0.08,
          f"mean_dev={pred['log_total']['mean_dev']}")

# controls quoted values
CD = load_js("controls_data.js")
cd = {c["code"]: c for c in CD["controls"]}
check("controls: cs.LO z=4.94, stat-mech z=8.63, cs.LG z=0.34",
      cd["cs.LO"]["z"] == 4.94 and cd["cond-mat.stat-mech"]["z"] == 8.63 and cd["cs.LG"]["z"] == 0.34)
rng_ctl = [round((c["r26"]-1)*100,1) for c in CD["controls"]]
check("controls range 14-43% as quoted", min(rng_ctl) >= 14.0 and max(rng_ctl) <= 43.0,
      f"min={min(rng_ctl)} max={max(rng_ctl)}")

print(f"\n===== AUDIT: {ok} passed, {fail} failed =====")
