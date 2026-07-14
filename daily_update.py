#!/usr/bin/env python3
"""Daily unattended refresh of the arXiv math dashboard.

Steps: (1) re-fetch the current month and the previous month for all 32
categories (older months are complete and never change; late cross-lists can
still land in the previous month for a few days), upserting into data.csv and
auto-adding rows for a newly-started month; (2) regenerate data.js and
report_data.js; (3) copy into public/; (4) commit & push only if data changed.

Intended to be run by Windows Task Scheduler once a day. All output is appended
to update.log.
"""
import csv, os, subprocess, sys
from datetime import date
import harvest, gen_data, analyze, stats_analysis

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "data.csv")
LOG = os.path.join(HERE, "update.log")

def log(msg):
    line = f"[{date.today().isoformat()}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def git(*args):
    r = subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()

def target_months():
    t = date.today()
    cur = f"{t.year:04d}-{t.month:02d}"
    py, pm = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)
    prev = f"{py:04d}-{pm:02d}"
    return [prev, cur]

def main():
    months = target_months()
    log(f"refreshing months {months}")

    # load existing
    with open(CSV, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], [r for r in rows[1:] if len(r) >= 3]
    data = {(r[0], r[1]): int(r[2]) for r in body}

    changed = 0
    for ym in months:
        for cat in harvest.CATEGORIES:
            n = harvest.fetch(cat, ym, retries=6)
            if n is None:
                log(f"  FAIL {cat} {ym} (kept old)")
                continue
            if data.get((cat, ym)) != n:
                changed += 1
            data[(cat, ym)] = n
    log(f"fetched; {changed} cell(s) changed")

    if changed == 0:
        log("no data changes; skipping regen/commit")
        return

    # rewrite csv sorted by (category order, month)
    order = {c: i for i, c in enumerate(harvest.CATEGORIES)}
    items = sorted(data.items(), key=lambda kv: (order.get(kv[0][0], 99), kv[0][1]))
    with open(CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for (cat, ym), n in items:
            w.writerow([cat, ym, n])

    gen_data.main()
    analyze.main()
    stats_analysis.main()
    for fn in ("data.js", "report_data.js", "stats_data.js"):
        with open(os.path.join(HERE, fn), "rb") as a, \
             open(os.path.join(HERE, "public", fn), "wb") as b:
            b.write(a.read())
    log("regenerated data.js, report_data.js, public/")

    # commit & push if the working tree changed
    code, out = git("status", "--porcelain")
    if not out:
        log("git: nothing to commit")
        return
    git("add", "-A")
    msg = f"Daily data refresh {date.today().isoformat()} ({changed} cells)"
    git("commit", "-m", msg)
    code, out = git("push", "origin", "HEAD")
    if code == 0:
        log(f"pushed: {msg}")
    else:
        log(f"PUSH FAILED (committed locally): {out}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e!r}")
        sys.exit(1)
