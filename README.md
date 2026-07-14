# arXiv Mathematics Submissions Dashboard · arXiv 数学论文投稿仪表盘

A bilingual (English / 中文) static dashboard of monthly arXiv submission counts across the
**32 Mathematics subject categories** (the `math.*` set plus `cs.IT`), from **January 2017 to
June 2026**.

Live preview locally:

```bash
python -m http.server 8765
# then open http://localhost:8765/index.html
```

## Tabs

### 📊 Dashboards / 仪表盘

1. **Normalized Growth Index / 归一化增长指数** — each category's monthly count divided by its
   January 2017 value (Jan 2017 = `1.0`), all categories overlaid. Linear/log toggle, "top
   growers" filter, and a 12-month moving-average (MA-12) smoothing toggle.
2. **Raw Monthly Counts / 原始每月数量** — raw paper counts per month, all categories overlaid,
   with a time-zoom slider and MA-12 toggle.
3. **Per-Category Panels / 各分类原始数量** — one small-multiple chart per category, with MA-12 toggle.

### 📄 Study: Focus Contraction / 研究：聚焦收缩

A comparative deep-dive applying the central idea of **Hao, Xu, Li & Evans, *Nature* (2026),
"Artificial intelligence tools expand scientists' impact but contract science's focus"**
([doi:10.1038/s41586-025-09922-y](https://doi.org/10.1038/s41586-025-09922-y),
[arXiv:2412.07727](https://arxiv.org/abs/2412.07727)) to mathematics. Using the submission
distribution across the 32 subfields, it measures whether math's collective focus is
concentrating over time (Shannon entropy / effective number of subfields, Pielou evenness,
top-5 share, HHI) and whether growth skews toward data-rich / ML-adjacent subfields —
then tests the timing formally (`stats_analysis.py`): structural-break search with
block-bootstrap p-values on the monthly series, multinomial bootstrap CIs on annual
concentration, and a two-way fixed-effects DiD with a yearly event study for the data-rich
cluster. The finding: the concentration is real (CIs cleanly separated) but **pandemic-era,
not LLM-era** — the best break candidate is Oct 2020 (itself insignificant, sup-F p ≈ 0.43),
the trend plateaued by 2021, and post-ChatGPT event-study coefficients are ≈ 0. Paper-level
evidence from the Kaggle arXiv metadata snapshot (`process_metadata.py`, ~449k unique math
papers) adds the mechanism: AI-related content in the data-rich cluster grew 2.9% → 13.5% of
papers (steepest 2017–2020), and subfield growth correlates with rising AI share (Spearman
0.425, permutation p ≈ 0.016) — while co-listing engagement between subfields *rose* (the
opposite of the natural-science "lonely crowds" pattern). Mathematics reads as an early
deep-learning adopter that plateaued, not a field currently narrowed by generative AI.
**Click any bar in the growth chart (Fig 3)** to expand a year-by-year waterfall decomposing
that subfield's growth index (green = up year, red = down). Reproducible via `analyze.py` +
`stats_analysis.py` + `process_metadata.py` (numpy; the metadata script needs the Kaggle
snapshot: `kaggle datasets download Cornell-University/arxiv --unzip -p meta/`).

## Data

Counts come from arXiv's public monthly listing pages
(`https://arxiv.org/list/<category>/YYYY-MM` → the "Total of N entries" figure). They **include
cross-listed papers**, so a single paper can appear in several categories — **the per-category
counts must not be summed** into a grand total. The most recent month may be partial.

> Note: arXiv's export API (`export.arxiv.org/api/query`) is aggressively rate-limited and was
> unusable for bulk harvesting; the listing pages are the reliable source.

### Regenerating the data

```bash
python harvest.py      # fetches every (category, month) into data.csv (resumable, ~6 workers)
python retry.py        # gentle serial pass to fill any throttled gaps (HTTP 406)
python gen_data.py     # builds data.js (window.ARXIV_DATA) consumed by index.html
```

## Files

| File | Purpose |
|------|---------|
| `index.html` | the dashboard (ECharts, vendored locally) |
| `echarts.min.js` | charting library, vendored so there is no CDN dependency |
| `data.js` | harvested data embedded as `window.ARXIV_DATA` |
| `data.csv` | raw harvested counts (category, month, count) |
| `harvest.py` / `retry.py` / `gen_data.py` | the data pipeline |
| `public/` | deploy-ready copy (`index.html` + `data.js` + `echarts.min.js`) |

## Deploy (Cloudflare Pages)

No build step — Cloudflare just serves static files. Either:

```bash
npx wrangler pages deploy public --project-name arxiv-dash
```

or connect this repo in the Cloudflare Pages dashboard with **build command:** *(none)* and
**output directory:** `public`.
