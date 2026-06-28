#!/usr/bin/env python3
"""Refresh the latest (current, still-incomplete) month in data.csv.

Monthly listing totals for the current month keep rising as papers are posted,
so re-fetch that month for every category and overwrite its rows in data.csv.
"""
import csv, os, sys, harvest

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "data.csv")
MONTH = sys.argv[1] if len(sys.argv) > 1 else "2026-06"

# load existing rows preserving order
rows = []
with open(CSV, newline="") as f:
    rows = list(csv.reader(f))
header, body = rows[0], rows[1:]
old = {(r[0], r[1]): int(r[2]) for r in body}

print(f"Refreshing {MONTH} for {len(harvest.CATEGORIES)} categories...")
new = {}
for cat in harvest.CATEGORIES:
    n = harvest.fetch(cat, MONTH, retries=6)
    if n is None:
        print(f"  FAIL {cat} {MONTH} (keeping old value)")
        continue
    new[(cat, MONTH)] = n

# report diffs
changed = 0
for k, v in new.items():
    o = old.get(k)
    if o != v:
        changed += 1
        print(f"  {k[0]:9s} {o} -> {v}  (+{v-o})")
    old[k] = v

# rewrite csv in original order, updating the refreshed month
with open(CSV, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(header)
    for r in body:
        key = (r[0], r[1])
        w.writerow([r[0], r[1], old[key]])
print(f"Done. {changed} category counts changed for {MONTH}.")
