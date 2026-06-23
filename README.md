# arXiv Mathematics Submissions Dashboard · arXiv 数学论文投稿仪表盘

A bilingual (English / 中文) static dashboard of monthly arXiv submission counts across the
**32 Mathematics subject categories** (the `math.*` set plus `cs.IT`), from **January 2017 to
June 2026**.

Live preview locally:

```bash
python -m http.server 8765
# then open http://localhost:8765/index.html
```

## Dashboards

1. **Normalized Growth Index / 归一化增长指数** — each category's monthly count divided by its
   January 2017 value (Jan 2017 = `1.0`), all categories overlaid. Linear/log toggle and a
   "top growers" filter.
2. **Raw Monthly Counts / 原始每月数量** — raw paper counts per month, all categories overlaid,
   with a time-zoom slider.
3. **Per-Category Panels / 各分类原始数量** — one small-multiple chart per category.

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
