"""🌸 Gold/CPI-indexed Mahr BENCHMARK. Derived, not observed Mahr data! 🧸

Pakistan has no public dataset of actual Mahr amounts. What we CAN do honestly:
index a fixed nominal sum and a fixed gold weight against CPI, showing how the
real value of a nominal Mahr erodes while a gold-denominated Mahr tracks gold.
Inputs are real series YOU export from SBP/PBS or a documented gold source. ✨
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import logger as log


def load_series(path: Path, date_col: str, value_col: str) -> pd.DataFrame:
    """✨ CSV -> (obs_date, value), validated: unique dates, positive values."""
    df = pd.read_csv(path, usecols=[date_col, value_col])
    df = df.rename(columns={date_col: "obs_date", value_col: "value"})
    df["obs_date"] = pd.to_datetime(df["obs_date"], errors="coerce", format="mixed").dt.to_period("M").dt.to_timestamp()
    bad = df["obs_date"].isna() | pd.to_numeric(df["value"], errors="coerce").isna()
    if bad.any():
        log.missing(f"{path.name}: dropped {int(bad.sum())} unparseable rows")
    good = df[~bad].copy()
    good["value"] = pd.to_numeric(good["value"])
    df = pd.DataFrame(good.groupby("obs_date", as_index=False)["value"].mean())
    if df.empty or (df["value"] <= 0).any():
        raise ValueError(f"{path.name}: empty or non-positive values")
    return df


def build_mahr_benchmark(gold: pd.DataFrame, cpi: pd.DataFrame, base_month: str) -> pd.DataFrame:
    """🎀 Index both series to base_month=100.

    gold_index   : value of a fixed gold weight (nominal PKR index)
    cpi_index    : price level index
    gold_to_cpi  : real purchasing power of the gold-denominated Mahr (base=100)
    real_value_fixed_pkr : real worth of a fixed nominal PKR sum (base=100), i.e. 10000/cpi_index
    """
    m = gold.merge(cpi, on="obs_date", suffixes=("_gold", "_cpi"))
    if m.empty:
        raise ValueError("gold and CPI series share no months")
    base = pd.Timestamp(base_month).to_period("M").to_timestamp()
    if base not in set(m["obs_date"]):
        raise ValueError(f"base month {base_month} not present in both series")
    b = m.loc[m["obs_date"] == base].iloc[0]
    out = pd.DataFrame({
        "obs_date": m["obs_date"].dt.date,
        "gold_index": 100.0 * m["value_gold"] / b["value_gold"],
        "cpi_index": 100.0 * m["value_cpi"] / b["value_cpi"],
    })
    out["gold_to_cpi_ratio"] = 100.0 * out["gold_index"] / out["cpi_index"]
    out["real_value_fixed_pkr"] = 10_000.0 / out["cpi_index"]
    return out.sort_values("obs_date").reset_index(drop=True)
