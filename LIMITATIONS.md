# 🎀 Limitations and caveats ✨

Read this before quoting any number from DecodeMatrimony. 🧸

## 1. Who is in the sample
- Couples are **head and spouse pairs** in PBS HIES 2024-25. Couples living inside a parent's household are not captured, so the sample skews older and describes head-spouse households only.
- 24,628 couples were built from 30,123 households; 5,492 households (18.2%) had no usable single head-spouse pair (no spouse listed, polygyny, or more than one head or spouse) and are dropped, not guessed.
- HIES 2024-25 reports do not cover AJK and GB; only provinces 1-4 appear in the data.

## 2. What the data cannot show
- **No sect, caste, religion or ethnicity variable.** Sect/caste inelasticity cannot be measured from HIES; that lens is skipped.
- **Cross-sectional associations only.** Every result is an association, never a causal effect. Cohort and age effects cannot be separated.
- Age at first marriage exists only for women in the marriage-history section; the marriage-timing lens uses wives aged 30+ to avoid right-truncation and finds no detectable gradient (0.009, 95% CI -0.010 to 0.027).

## 3. Measurement choices
- **Education** is recoded to four levels (none/pre-primary, classes 1-5, classes 6-12, diploma and above); other cut points could change the pairing shares.
- **"Working"** follows the broad employment question (paid job, unpaid family work or business in the last month), so it includes unpaid family work.
- **Wealth** is a DHS-style index (weighted PCA on housing and asset indicators, first component 14.1% of variance, person-weighted quintiles), not consumption. Ties can make quintiles slightly uneven.
- The **age-gap adjustment** stratifies on wife age band and province only; it does not adjust for urban/rural or other factors.

## 4. Inference
- Intervals are 95% percentile intervals from a Rao-Wu PSU/strata bootstrap (1,000 draws); they quantify sampling variance under the design, not measurement or coding error.
- Bootstrap p-values cannot go below about 1/(draws+1), so very small p-values are reported as "p < 0.001".
- Group comparisons are weighted Mann-Whitney **effect sizes** (probability of a larger value, 0.5 = no difference) with bootstrap p-values and Holm correction, not classical U-test p-values. Effects of education on the age gap are small (0.52 to 0.54 adjusted), and the "higher" contrast is not significant after adjustment.

## 5. Derived Mahr benchmark
- The Mahr benchmark is **derived from gold and CPI**, not observed Mahr values. Treat it as a scale indicator.
- Gold is the month-end APGJSA 24K quote as reported by news outlets (September has one source only); CPI covers Jan-Oct 2026. Ten months cannot show an inflation trend for Mahr.

## 6. Engineering
- The SQL Server load was verified on SQL Server for Linux in a throwaway Colab database; it has not been tested on Windows SQL Server Express.
- Re-running the pipeline does not duplicate couples (MERGE upsert) but appends a new set of results under a new run ID.
