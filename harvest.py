#!/usr/bin/env python3
"""Harvest monthly arXiv submission counts per category from listing pages.

For each (category, YYYY-MM) we GET https://arxiv.org/list/<cat>/<YYYY-MM>
and parse "Total of N entries". Results are written incrementally to data.csv
so the run is resumable (already-fetched rows are skipped on restart).
"""
import csv
import os
import re
import sys
import time
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data.csv")

# 32 Mathematics subject categories from the source PDF (math.* plus cs.IT).
CATEGORIES = [
    "math.AG", "math.AT", "math.AP", "math.CT", "math.CA", "math.CO",
    "math.AC", "math.CV", "math.DG", "math.DS", "math.FA", "math.GM",
    "math.GN", "math.GT", "math.GR", "math.HO", "cs.IT", "math.KT",
    "math.LO", "math-ph", "math.MG", "math.NT", "math.NA", "math.OA",
    "math.OC", "math.PR", "math.QA", "math.RT", "math.RA", "math.SP",
    "math.ST", "math.SG",
]

def months(start=(2017, 1), end=(2026, 6)):
    y, m = start
    while (y, m) <= end:
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1

TOTAL_RE = re.compile(r"Total of ([\d,]+) entries", re.I)
UA = "arxiv-dash-research/1.0 (mailto:fsiceangel@gmail.com)"

lock = threading.Lock()

def fetch(cat, ym, retries=4):
    url = f"https://arxiv.org/list/{cat}/{ym}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                html = r.read().decode("utf-8", "replace")
            mt = TOTAL_RE.search(html)
            if mt:
                return int(mt.group(1).replace(",", ""))
            # No match: month with zero entries renders differently; treat as 0
            # but only if page clearly loaded (avoid masking errors).
            if "entries" in html.lower() or "no entries" in html.lower():
                return 0
            raise ValueError("no total found")
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, TimeoutError) as e:
            wait = 2 * (attempt + 1)
            sys.stderr.write(f"retry {cat} {ym} ({e}); sleep {wait}\n")
            time.sleep(wait)
    return None

def load_done():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, newline="") as f:
            for row in csv.reader(f):
                if len(row) >= 3 and row[0] != "category":
                    done.add((row[0], row[1]))
    return done

def main():
    tasks = [(c, ym) for c in CATEGORIES for ym in months()]
    done = load_done()
    tasks = [t for t in tasks if t not in done]
    write_header = not os.path.exists(OUT)
    fout = open(OUT, "a", newline="")
    w = csv.writer(fout)
    if write_header:
        w.writerow(["category", "month", "count"])
        fout.flush()
    total = len(tasks)
    counter = {"n": 0, "fail": 0}

    def work(t):
        cat, ym = t
        n = fetch(cat, ym)
        with lock:
            counter["n"] += 1
            if n is None:
                counter["fail"] += 1
                sys.stderr.write(f"FAIL {cat} {ym}\n")
            else:
                w.writerow([cat, ym, n])
                fout.flush()
            if counter["n"] % 50 == 0:
                sys.stderr.write(f"progress {counter['n']}/{total} fails={counter['fail']}\n")
        time.sleep(0.15)

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(work, tasks))
    fout.close()
    sys.stderr.write(f"DONE {counter['n']}/{total} fails={counter['fail']}\n")

if __name__ == "__main__":
    main()
