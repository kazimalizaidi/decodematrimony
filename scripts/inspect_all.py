import pandas as pd

FILES = ["plist_roster", "sec_2ab_education", "sec_1b_emp_income",
         "weight", "section_info", "Sec_04a_pregnancyhistory"]

with open("columns_key.txt", "w", encoding="utf-8") as out:
    for name in FILES:
        f = f"data/raw/{name}.dta"
        with pd.read_stata(f, iterator=True, convert_categoricals=False) as r:
            labs = r.variable_labels()
        df = pd.read_stata(f, convert_categoricals=False)
        out.write(f"\n=== {name}  rows={len(df)}\n")
        for k, v in labs.items():
            out.write(f"  {k:15s} {v}\n")
        out.write("--- first 3 rows ---\n")
        out.write(df.head(3).to_string() + "\n")
print("done, wrote columns_key.txt")
