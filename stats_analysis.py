#!/usr/bin/env python3
"""Statistical tests for the focus-contraction study (beyond EDA).

1. Monthly concentration series: effective number of subfields E_t = 2^H(shares_t).
2. Structural-break search (Quandt-Andrews style): piecewise-linear trend with an
   unknown single break in intercept+slope; sup-F over candidate dates, p-value by
   moving-block residual bootstrap under the no-break null. Also reports F at two
   hypothesized dates: COVID (2020-03) and ChatGPT (2022-12).
3. Difference-in-differences on log monthly counts: data-rich cluster vs rest,
   two-way (category + month) fixed effects, COVID interaction control,
   cluster-robust SEs by category. Plus a yearly event study (base 2022).
4. Multinomial bootstrap CIs for annual effective subfields.
5. Pre-trend counterfactual: 2017-19 trend extrapolated vs actual post-2022 level.

Writes stats_data.js (window.STATS_DATA) for the report tab.
"""
import csv, json, math, os
from datetime import date
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_CLUSTER = {"cs.IT", "math.OC", "math.NA", "math.ST", "math.PR"}
RNG = np.random.default_rng(42)

def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def load_matrix():
    """counts[cat][ym], months sorted, complete months only (drop current month)."""
    raw = {}
    with open(os.path.join(HERE, "data.csv"), newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 3 and row[1] != "month":
                raw.setdefault(row[0], {})[row[1]] = int(row[2])
    t = date.today()
    cur = f"{t.year:04d}-{t.month:02d}"
    months = sorted({ym for d in raw.values() for ym in d if ym < cur})
    cats = sorted(raw.keys())
    M = np.array([[raw[c].get(ym, 0) for ym in months] for c in cats], dtype=float)
    return cats, months, M

def eff_subfields_series(M):
    shares = M / M.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.where(shares > 0, np.log2(shares), 0.0)
    H = -(shares * logs).sum(axis=0)
    return 2.0 ** H

# ---------- 1-2: structural break on the monthly series ----------

def ols_ssr(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r), beta

def break_F(y, tau):
    """F-stat for full break (intercept+slope) at index tau."""
    n = len(y)
    t = np.arange(n, dtype=float)
    X0 = np.column_stack([np.ones(n), t])
    post = (t >= tau).astype(float)
    X1 = np.column_stack([np.ones(n), t, post, post * t])
    ssr0, _ = ols_ssr(X0, y)
    ssr1, _ = ols_ssr(X1, y)
    q, k = 2, 4
    return ((ssr0 - ssr1) / q) / (ssr1 / (n - k))

def sup_F_test(y, trim=0.15, n_boot=500, block=12):
    n = len(y)
    lo, hi = int(n * trim), int(n * (1 - trim))
    cand = range(lo, hi)
    Fs = {tau: break_F(y, tau) for tau in cand}
    tau_star = max(Fs, key=Fs.get)
    supF = Fs[tau_star]
    # null model: single linear trend; moving-block bootstrap of residuals
    t = np.arange(n, dtype=float)
    X0 = np.column_stack([np.ones(n), t])
    _, b0 = ols_ssr(X0, y)
    fit0 = X0 @ b0
    res = y - fit0
    n_blocks = int(np.ceil(n / block))
    count = 0
    for _ in range(n_boot):
        starts = RNG.integers(0, n - block + 1, size=n_blocks)
        rb = np.concatenate([res[s:s + block] for s in starts])[:n]
        yb = fit0 + rb
        supFb = max(break_F(yb, tau) for tau in cand)
        if supFb >= supF:
            count += 1
    pval = (count + 1) / (n_boot + 1)
    return tau_star, supF, pval, Fs

# ---------- 3: DiD with two-way FE ----------

def did_analysis(cats, months, M):
    """log(count) on cat FE + month FE + treat interactions; cluster-robust by cat."""
    n_c, n_t = M.shape
    y = np.log(np.maximum(M, 1.0)).ravel()                    # row-major: cat-major
    cat_idx = np.repeat(np.arange(n_c), n_t)
    mon_idx = np.tile(np.arange(n_t), n_c)
    treat = np.array([1.0 if c in DATA_CLUSTER else 0.0 for c in cats])[cat_idx]
    post = np.array([1.0 if ym >= "2022-12" else 0.0 for ym in months])[mon_idx]
    covid = np.array([1.0 if "2020-03" <= ym <= "2021-12" else 0.0 for ym in months])[mon_idx]

    def run(inter_cols, names):
        # dummies: drop first cat and first month (absorbed by intercept)
        Xc = np.zeros((len(y), n_c - 1)); Xc[np.arange(len(y)), :] = 0
        for i in range(1, n_c):
            Xc[cat_idx == i, i - 1] = 1.0
        Xm = np.zeros((len(y), n_t - 1))
        for j in range(1, n_t):
            Xm[mon_idx == j, j - 1] = 1.0
        X = np.column_stack([np.ones(len(y))] + inter_cols + [Xc, Xm])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        u = y - X @ beta
        XtX_inv = np.linalg.pinv(X.T @ X)
        meat = np.zeros((X.shape[1], X.shape[1]))
        for c in range(n_c):
            m = cat_idx == c
            Xu = X[m].T @ u[m]
            meat += np.outer(Xu, Xu)
        G = n_c
        V = XtX_inv @ meat @ XtX_inv * (G / (G - 1))
        se = np.sqrt(np.diag(V))
        out = {}
        for k, name in enumerate(names, start=1):   # interactions start at col 1
            b, s = float(beta[k]), float(se[k])
            z = b / s if s > 0 else 0.0
            out[name] = {"coef": round(b, 4), "se": round(s, 4),
                         "z": round(z, 2), "p": round(2 * (1 - norm_cdf(abs(z))), 4)}
        return out

    main = run([treat * post, treat * covid], ["treat_post", "treat_covid"])

    # event study: treat x year, base 2022
    years = sorted({ym[:4] for ym in months})
    ev_names, ev_cols = [], []
    for yy in years:
        if yy == "2022":
            continue
        d = np.array([1.0 if ym[:4] == yy else 0.0 for ym in months])[mon_idx]
        ev_cols.append(treat * d)
        ev_names.append(yy)
    event = run(ev_cols, ev_names)
    return main, event, years

# ---------- 4: multinomial bootstrap CIs on annual E ----------

def annual_boot(cats, months, M, reps=2000):
    years = sorted({ym[:4] for ym in months})
    out = {}
    for yy in years:
        cols = [j for j, ym in enumerate(months) if ym[:4] == yy]
        tot = M[:, cols].sum(axis=1)
        n = int(tot.sum())
        p = tot / tot.sum()
        H = -(p[p > 0] * np.log2(p[p > 0])).sum()
        draws = RNG.multinomial(n, p, size=reps) / n
        with np.errstate(divide="ignore", invalid="ignore"):
            lg = np.where(draws > 0, np.log2(draws), 0.0)
        Eb = 2.0 ** (-(draws * lg).sum(axis=1))
        out[yy] = {"E": round(float(2 ** H), 3),
                   "lo": round(float(np.percentile(Eb, 2.5)), 3),
                   "hi": round(float(np.percentile(Eb, 97.5)), 3)}
    return out

def predictive_failure(y, months, fit_lo="2021-01", fit_hi="2025-12",
                       test_lo="2026-01", n_boot=2000, block=6):
    """Chow-type predictive failure test: fit linear trend on [fit_lo, fit_hi],
    test whether observations from test_lo jointly deviate. p-value by
    moving-block bootstrap of in-sample residuals (respects autocorrelation)."""
    idx_fit = [i for i, m in enumerate(months) if fit_lo <= m <= fit_hi]
    idx_tst = [i for i, m in enumerate(months) if m >= test_lo]
    t = np.arange(len(months), dtype=float)
    Xf = np.column_stack([np.ones(len(idx_fit)), t[idx_fit]])
    b, *_ = np.linalg.lstsq(Xf, y[idx_fit], rcond=None)
    res_fit = y[idx_fit] - Xf @ b
    s2 = float(res_fit @ res_fit) / (len(idx_fit) - 2)
    pred = b[0] + b[1] * t[idx_tst]
    e = y[idx_tst] - pred
    m = len(idx_tst)
    F = float(e @ e) / m / s2
    # bootstrap null: m-length moving blocks of in-sample residuals
    n_res = len(res_fit)
    count = 0
    for _ in range(n_boot):
        s = RNG.integers(0, n_res - m + 1)
        eb = res_fit[s:s + m]
        Fb = float(eb @ eb) / m / s2
        if Fb >= F:
            count += 1
    return {"F": round(F, 2), "p_boot": round((count + 1) / (n_boot + 1), 4),
            "mean_dev": round(float(e.mean()), 3), "m": m,
            "window": f"{fit_lo}..{fit_hi}"}

def main():
    cats, months, M = load_matrix()
    E = eff_subfields_series(M)

    tau, supF, p_sup, Fs = sup_F_test(E)
    def F_at(ym):
        if ym in months:
            i = months.index(ym)
            return round(break_F(E, i), 2)
        return None
    f_covid, f_llm = F_at("2020-03"), F_at("2022-12")

    did, event, years = did_analysis(cats, months, M)
    boot = annual_boot(cats, months, M)

    # pre-trend counterfactual: fit 2017-2019, project through end
    pre_idx = [i for i, ym in enumerate(months) if ym <= "2019-12"]
    t = np.arange(len(months), dtype=float)
    Xp = np.column_stack([np.ones(len(pre_idx)), t[pre_idx]])
    bp, *_ = np.linalg.lstsq(Xp, E[pre_idx], rcond=None)
    proj = bp[0] + bp[1] * t
    post_idx = [i for i, ym in enumerate(months) if ym >= "2023-01"]
    gap = float(np.mean(E[post_idx] - proj[post_idx]))

    # end-of-sample predictive failure for 2026 (concentration + log output)
    total = M.sum(axis=0)
    pred26 = {
        "E": predictive_failure(E, months),
        "log_total": predictive_failure(np.log(total), months),
        "cand_window_end": months[int(len(months) * 0.85) - 1],
    }

    out = {
        "months": months,
        "E_monthly": [round(float(x), 3) for x in E],
        "pred_2026": pred26,
        "proj_pre_trend": [round(float(x), 3) for x in proj],
        "break": {"month": months[tau], "supF": round(supF, 2), "p_boot": round(p_sup, 4),
                  "F_covid_2020_03": f_covid, "F_llm_2022_12": f_llm},
        "did": did, "event_study": event, "event_years": [y for y in years if y != "2022"],
        "annual_E_ci": boot,
        "pretrend_gap_post2023": round(gap, 3),
    }
    with open(os.path.join(HERE, "stats_data.js"), "w", encoding="utf-8") as f:
        f.write("window.STATS_DATA = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")

    print(f"months: {months[0]}..{months[-1]} ({len(months)})")
    print(f"BREAK: best={months[tau]} supF={supF:.1f} p_boot={p_sup:.4f} "
          f"| F@2020-03={f_covid} F@2022-12={f_llm}")
    print(f"BREAK candidate window ends: {pred26['cand_window_end']}")
    print(f"PRED-2026 E: {pred26['E']}")
    print(f"PRED-2026 log_total: {pred26['log_total']}")
    print(f"DiD treat×post(2022-12): {did['treat_post']}")
    print(f"DiD treat×covid       : {did['treat_covid']}")
    print("Event study (base 2022):")
    for yy in out["event_years"]:
        e = event[yy]
        print(f"  {yy}: {e['coef']:+.4f} (se {e['se']}, p {e['p']})")
    print(f"annual E CIs: 2017={boot['2017']} 2021={boot['2021']} 2025={boot['2025']}")
    print(f"pre-trend gap (post-2023 actual minus 2017-19 projection): {gap:+.3f}")

if __name__ == "__main__":
    main()
