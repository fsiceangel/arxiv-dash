#!/usr/bin/env python3
"""Second pass: fill missing (category,month) cells serially with polite delays."""
import csv, os, sys, time, harvest

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data.csv")

done = harvest.load_done()
want = [(c, ym) for c in harvest.CATEGORIES for ym in harvest.months()]
missing = [t for t in want if t not in done]
print(f"missing cells: {len(missing)}")

with open(OUT, "a", newline="") as f:
    w = csv.writer(f)
    ok = fail = 0
    for i, (cat, ym) in enumerate(missing, 1):
        n = harvest.fetch(cat, ym, retries=6)
        if n is None:
            fail += 1
            print(f"STILL-FAIL {cat} {ym}")
        else:
            w.writerow([cat, ym, n]); f.flush(); ok += 1
        time.sleep(1.0)
        if i % 25 == 0:
            print(f"  {i}/{len(missing)} ok={ok} fail={fail}")
print(f"retry done ok={ok} fail={fail}")
