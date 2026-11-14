"""🎀 Recompute monthly gold values from a DAILY series and compare with your monthly file. ✨

  python scripts/gold_monthly.py data/raw/gold_daily.csv --compare data/raw/gold_prices_2026.csv

Daily CSV columns (header exactly): date,price_pkr_per_tola_24k,source_url
  * one row per published APGJSA 24K per-tola quote, ONE quote per day (use the same rule every day,
    e.g. the last quote reported that day), real values only, with the page you copied it from.
Outputs data/raw/gold_monthly_recomputed.csv with the same Month / Gold_Price_Per_Tola_24K columns the
pipeline reads, plus method, n_days and month-end quote columns. 🧸
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("daily", type=Path)
ap.add_argument("--compare", type=Path, default=None, help="your existing monthly CSV (Month, Gold_Price_Per_Tola_24K)")
ap.add_argument("--min-days", type=int, default=15, help="flag months with fewer daily quotes than this")
ap.add_argument("--out", type=Path, default=Path("data/raw/gold_monthly_recomputed.csv"))
a = ap.parse_args()

d = pd.read_csv(a.daily)
need = {"date", "price_pkr_per_tola_24k", "source_url"}
if not need <= set(d.columns):
    sys.exit(f"💗 header must contain {sorted(need)}; found {list(d.columns)}")
d["date"] = pd.to_datetime(d["date"], errors="coerce", format="%Y-%m-%d")
d["price"] = pd.to_numeric(d["price_pkr_per_tola_24k"], errors="coerce")
bad = d[d["date"].isna() | d["price"].isna()]
if len(bad):
    sys.exit(f"💗 {len(bad)} rows have an unparseable date or price (first row numbers: {list(bad.index[:5] + 2)})")
if d["date"].duplicated().any():
    sys.exit(f"💗 duplicate dates: {d.loc[d['date'].duplicated(), 'date'].dt.date.tolist()[:5]}; keep one quote per day")
if (d["source_url"].isna() | (d["source_url"].astype(str).str.strip() == "")).any():
    sys.exit("💗 every row needs a source_url so each quote can be traced")
odd = d[(d["price"] < 100_000) | (d["price"] > 1_000_000)]
if len(odd):
    sys.exit(f"💗 implausible prices (outside 100k-1M PKR) on {odd['date'].dt.date.tolist()[:5]}; check typos")

d = d.sort_values("date")
d["ym"] = d["date"].dt.to_period("M")
g = d.groupby("ym")
m = pd.DataFrame({
    "Month": [p.strftime("%B %Y") for p in g.size().index],
    "Gold_Price_Per_Tola_24K": g["price"].mean().round().astype("int64").to_numpy(),
    "Method": "simple mean of daily APGJSA 24K per-tola quotes (one per day)",
    "n_days": g.size().to_numpy(),
    "first_date": g["date"].min().dt.date.astype(str).to_numpy(),
    "last_date": g["date"].max().dt.date.astype(str).to_numpy(),
    "month_end_quote": g["price"].last().astype("int64").to_numpy(),
})
for _, r in m.iterrows():
    flag = "  <- few days, mean not reliable" if r["n_days"] < a.min_days else ""
    print(f"{'🧸' if flag else '✨'} {r['Month']}: mean={r['Gold_Price_Per_Tola_24K']:,}  n_days={r['n_days']}{flag}")
a.out.parent.mkdir(parents=True, exist_ok=True)
m.to_csv(a.out, index=False)
print(f"🎀 wrote {a.out}")

if a.compare:
    old = pd.read_csv(a.compare, usecols=["Month", "Gold_Price_Per_Tola_24K"]).rename(columns={"Gold_Price_Per_Tola_24K": "your_file"})
    c = old.merge(m[["Month", "Gold_Price_Per_Tola_24K", "n_days", "month_end_quote"]], on="Month", how="outer")
    c["diff_pkr"] = c["Gold_Price_Per_Tola_24K"] - c["your_file"]
    c["diff_pct"] = (100 * c["diff_pkr"] / c["your_file"]).round(2)
    c["matches_month_end"] = c["your_file"] == c["month_end_quote"]
    print("\n🎀 comparison (recomputed mean vs your file; diff_pct beyond +-1% means the file was NOT a mean of these quotes):")
    print(c.to_string(index=False))
