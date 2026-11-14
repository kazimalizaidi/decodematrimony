"""🎀 Build site/index.html from the pipeline outputs, so the page can never drift from the results. ✨

  python scripts/build_site.py                 (reads out/results.csv, out/mahr_benchmark.csv, out/run_summary.json)
  python scripts/build_site.py --couples 24628 --boot 1000   (if run_summary.json is missing)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

REGIONS = {"punjab": "Punjab", "sindh": "Sindh", "khyber pakhtunkhwa": "Khyber Pakhtunkhwa", "balochistan": "Balochistan"}
EDU = {"no_education": "None", "primary": "Primary", "secondary": "Secondary", "higher": "Higher"}
PAIR = {"homogamous": "Homogamous", "hypergamous": "Hypergamous", "hypogamous": "Hypogamous"}
QUINT = {"1": "Q1 (poorest)", "2": "Q2", "3": "Q3", "4": "Q4", "5": "Q5 (richest)"}


def _get(res: pd.DataFrame, metric: str, group: str) -> pd.Series:
    r = res[(res["metric"] == metric) & (res["group_label"] == group)]
    if r.empty:
        raise SystemExit(f"💗 results.csv has no row for {metric}[{group}]; rerun the pipeline")
    return r.iloc[0]


def _pct(res: pd.DataFrame, metric: str, groups: list[str]) -> tuple[list[float], list[list[float]]]:
    est, ci = [], []
    for g in groups:
        r = _get(res, metric, g)
        est.append(round(float(r["estimate"]) * 100, 2))
        ci.append([round(float(r["ci_low"]) * 100, 2), round(float(r["ci_high"]) * 100, 2)])
    return est, ci


def build_data(res: pd.DataFrame, mahr: pd.DataFrame) -> dict[str, Any]:
    res = res.assign(group_label=res["group_label"].astype(str))
    hyper, hyperCI = _pct(res, "share_hypergamous", list(REGIONS))
    hypo, hypoCI = _pct(res, "share_hypogamous", list(REGIONS))
    gap = [_get(res, "age_gap_mean_years", g) for g in EDU]
    q = list(QUINT)
    w10, w10CI = _pct(res, "share_age_gap_10plus_by_wealth_quintile", q)
    work, workCI = _pct(res, "share_wife_working", list(PAIR))
    hq, _ = _pct(res, "share_hypergamous_by_wealth_quintile", q)
    oq, _ = _pct(res, "share_homogamous_by_wealth_quintile", q)
    adj = []
    for g, name in list(EDU.items())[1:]:
        a, u = _get(res, "age_gap_superiority_vs_no_education_adjusted", g), _get(res, "age_gap_superiority_vs_no_education", g)
        p = a["p_adjusted"] if pd.notna(a["p_adjusted"]) else a["p_value"]
        adj.append({"level": name, "raw": round(float(u["estimate"]), 4), "adj": round(float(a["estimate"]), 4),
                    "lo": round(float(a["ci_low"]), 4), "hi": round(float(a["ci_high"]), 4), "p": round(float(p), 4)})

    def card(title: str, metric: str, group: str, note: str) -> dict[str, str]:
        r = _get(res, metric, group)
        return {"title": title, "est": f"{r['estimate']:.3f}", "lo": f"{r['ci_low']:.3f}", "hi": f"{r['ci_high']:.3f}", "note": note}

    m = mahr.sort_values("obs_date")
    return {
        "regions": list(REGIONS.values()), "hyper": hyper, "hyperCI": hyperCI, "hypo": hypo, "hypoCI": hypoCI,
        "eduLevels": list(EDU.values()), "ageGap": [round(float(r["estimate"]), 2) for r in gap],
        "ageGapCI": [[round(float(r["ci_low"]), 2), round(float(r["ci_high"]), 2)] for r in gap],
        "wealthLabels": list(QUINT.values()), "wealth10": w10, "wealth10CI": w10CI,
        "pairing": list(PAIR.values()), "wifeWork": work, "wifeWorkCI": workCI,
        "adj": adj,
        "wealthPair": {"hyper": hq, "homo": oq, "hypo": [round(100 - a - b, 2) for a, b in zip(hq, oq)]},
        "mahr": {"labels": [pd.Timestamp(d).strftime("%b") for d in m["obs_date"]],
                 "gold": [round(float(x), 2) for x in m["gold_index"]], "cpi": [round(float(x), 2) for x in m["cpi_index"]],
                 "ratio": [round(float(x), 2) for x in m["gold_to_cpi_ratio"]]},
        "cards": [
            card("Working vs non-working wives", "age_gap_superiority_working_vs_not", "wife_working",
                 "Chance a working wife has the larger age gap (0.5 = no difference)."),
            card("Marriage timing, wives 30+", "spearman_wife_age_vs_age_at_first_union", "wife_age_30plus",
                 "Interval includes 0: no detectable gradient."),
            card("Wealth vs age gap", "spearman_wealth_vs_age_gap", "all", "Weighted Spearman: very weak positive."),
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--template", type=Path, default=Path("site/index.template.html"))
    ap.add_argument("--dest", type=Path, default=Path("site/index.html"))
    ap.add_argument("--couples", type=int, default=None)
    ap.add_argument("--boot", type=int, default=None)
    a = ap.parse_args()
    res = pd.read_csv(a.out / "results.csv")
    mahr = pd.read_csv(a.out / "mahr_benchmark.csv")
    n: Optional[int] = a.couples
    boot: Optional[int] = a.boot
    summ = a.out / "run_summary.json"
    if summ.exists():
        j = json.loads(summ.read_text(encoding="utf-8"))
        n, boot = n or j["n_couples"], boot or j["n_boot"]
    if n is None or boot is None:
        sys.exit("💗 need out/run_summary.json (rerun the pipeline) or --couples and --boot")
    data = build_data(res, mahr)
    sp = _get(res.assign(group_label=res["group_label"].astype(str)), "spearman_wealth_vs_age_gap", "all")
    html = a.template.read_text(encoding="utf-8")
    for k, v in {"__DATA_JSON__": json.dumps(data), "__N_COUPLES__": f"{n:,}", "__N_BOOT__": f"{boot:,}",
                 "__SPEARMAN__": f"{sp['estimate']:.3f}", "__SP_LO__": f"{sp['ci_low']:.3f}", "__SP_HI__": f"{sp['ci_high']:.3f}",
                 "__SP_N__": f"{int(sp['n_unweighted']):,}"}.items():
        html = html.replace(k, v)
    if "__" in "".join(t for t in html.split("<") if t.startswith("span>__")):
        sys.exit("💗 unreplaced placeholder left in page")
    a.dest.write_text(html, encoding="utf-8")
    print(f"✨ wrote {a.dest} from {a.out}/results.csv ({len(res)} results)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
