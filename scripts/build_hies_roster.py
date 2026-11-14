"""🎀 Build data/raw/hies_roster.csv from the HIES 2024-25 section files. ✨

Run from the project root:   python scripts/build_hies_roster.py [data/raw]
Every column name below was read from YOUR columns_key.txt (nothing guessed). 🧸
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
KEYS = ["prcode", "hhno", "idc"]


def load(name: str, cols: list[str]) -> pd.DataFrame:
    df = pd.read_stata(RAW / f"{name}.dta", convert_categoricals=False, columns=cols)
    dup = int(df.duplicated(KEYS).sum())
    if dup:
        raise SystemExit(f"💗 {name}: {dup} duplicate person keys {KEYS}; send me this message before going on")
    print(f"✨ {name}: {len(df):,} rows")
    return df


roster = load("plist_roster", KEYS + ["province", "region", "s1aq02", "s1aq03", "s1aq10", "s1aq51", "s1aq06", "weight", "hhcode"])
edu = load("sec_2ab_education", KEYS + ["s2aq01", "s2bq01", "s2bq05"])
emp = load("sec_1b_emp_income", KEYS + ["s1bq01"])
mar = load("Sec_04a_pregnancyhistory", KEYS + ["s4aq04"])

n0 = len(roster)
df = roster.merge(edu, on=KEYS, how="left", validate="one_to_one")
df = df.merge(emp, on=KEYS, how="left", validate="one_to_one")
df = df.merge(mar, on=KEYS, how="left", validate="one_to_one")
assert len(df) == n0, "💗 merge changed the row count!"

for c in ("prcode", "hhno", "idc"):
    df[c] = df[c].astype("int64")
# household id: (prcode, hhno) is the true key. hhno can have 3 digits, so use *1000 (NOT *100: collisions).
assert int(df["hhno"].max()) < 1000, "hhno has 4+ digits, tell me"
df["hh_id"] = df["prcode"] * 1000 + df["hhno"]
hc = df["hhcode"].astype("float64")          # Stata 'float' columns lose precision, so compare with a tolerance
m3 = int(np.isclose(hc, df["hh_id"].astype("float64"), rtol=1e-6).sum())
m2 = int(np.isclose(hc, (df["prcode"] * 100 + df["hhno"]).astype("float64"), rtol=1e-6).sum())
print(f"🎀 hhcode ~ prcode*1000+hhno on {m3:,} of {n0:,} rows (prcode*100+hhno: {m2:,})")
n_hh = df[["prcode", "hhno"]].drop_duplicates().shape[0]
print(f"🎀 households (unique prcode+hhno): {n_hh:,}; unique hh_id: {df['hh_id'].nunique():,}  (must be equal)")
assert n_hh == df["hh_id"].nunique(), "hh_id collides!"

# education: 0 = never attended; else highest class completed (past attenders only)
df["edu_code"] = df["s2bq05"].where(df["s2bq01"] == 2)
df.loc[df["s2bq01"] == 1, "edu_code"] = 0
df["stratum"] = df["prcode"] // 10_000   # first 4 digits of the 8-digit PSU code

# household wealth index (DHS-style PCA on housing + assets; see src/decodematrimony/wealth.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from decodematrimony.wealth import build_wealth_index  # noqa: E402

ASSETS = ["s5m1q111a", "s5m1q112a", "s5m1q113a", "s5m1q114a", "s5m1q115a", "s5m1q116a", "s5m1q117a", "s5m1q118a", "s5m1q119a"]
CATS = ["s5m1q03", "s5m1q05", "s5m1q06", "s5m1q07", "s5m1q08", "s5m1q10"]
hous = pd.read_stata(RAW / "sec_05m1_housingchar.dta", convert_categoricals=False,
                     columns=["prcode", "hhno"] + ASSETS + CATS + ["s5m1q04"])
for c in ("prcode", "hhno"):
    hous[c] = hous[c].astype("int64")
assert not hous.duplicated(["prcode", "hhno"]).any(), "housing file has duplicate households"
print(f"✨ sec_05m1_housingchar: {len(hous):,} households")

# keep household members only (roster Q10: 1 = yes, 2 = no)
dropped = int((df["s1aq10"] == 2).sum())
df = df[df["s1aq10"] != 2]
print(f"🧸 dropped {dropped:,} non-members; {len(df):,} persons kept")

hh_info = df.groupby(["prcode", "hhno"]).agg(weight=("weight", "first"), size=("idc", "size")).reset_index()
hous = hous.merge(hh_info, on=["prcode", "hhno"], how="inner", validate="one_to_one")
hous["pw"] = hous["weight"].astype("float64") * hous["size"]       # person-weighted, as in DHS
widx = build_wealth_index(hous, "pw", ASSETS, CATS, ["s5m1q04"])
chk = hous.join(widx)
print("🎀 validity check: share of households owning each asset, by wealth quintile (should rise with quintile)")
for c in ASSETS:
    shares = [float(((chk.loc[chk["wealth_quintile"] == q, c] == 1) * chk.loc[chk["wealth_quintile"] == q, "pw"]).sum()
                    / chk.loc[chk["wealth_quintile"] == q, "pw"].sum()) for q in range(1, 6)]
    print(f"   {c}: " + " ".join(f"{x:.2f}" for x in shares) + ("  ok" if all(b >= a - 0.02 for a, b in zip(shares, shares[1:])) else "  CHECK"))
hous = chk[["prcode", "hhno", "wealth_score", "wealth_quintile"]]
n1 = len(df)
df = df.merge(hous, on=["prcode", "hhno"], how="left", validate="many_to_one")
assert len(df) == n1, "wealth merge changed row count"
print("📉 wealth quintile (person-weighted share should be ~20% each):",
      (df.groupby("wealth_quintile")["weight"].sum() / df["weight"].sum()).round(3).to_dict())

# sanity check: weighted literacy, ages 10+ (PBS press release: about 63% for 2024-25)
lit = df[(df["s1aq51"] >= 10) & df["s2aq01"].isin([1, 2])]
rate = (lit["weight"] * (lit["s2aq01"] == 1)).sum() / lit["weight"].sum()
print(f"📉 weighted literacy (10+): {rate:.1%}   <- compare with PBS's published ~63%")
print("🎀 province counts:", df["province"].value_counts().sort_index().to_dict())
print("🎀 relation counts:", df["s1aq02"].value_counts().sort_index().head(6).to_dict())

out = RAW / "hies_roster.csv"
df.drop(columns=["hhcode"]).to_csv(out, index=False)
print(f"✨ wrote {out}  ({len(df):,} rows)")
