# Data sources and verification status 

No simulated or synthetic data is used in any analysis; unit tests use in-memory fixtures only.

## 1. Datasets and checks

| Dataset | Source | What was checked | Status |
|---|---|---|---|
| `hies_roster.csv` (2024-25) | Pakistan Bureau of Statistics, HIES page: https://www.pbs.gov.pk/hies/ | Weighted literacy (10+) = 64.0% vs PBS published ~63%; household count reconciles with `section_info` (30,123); `hhcode` matches `prcode*1000+hhno` on all 184,564 roster rows; province codes 1-4 only | Official source, sanity checks passed |
| `pakistan_cpi_2026.csv` (Jan-Oct 2026) | PBS national CPI, base 2015-16 = 100. Page: https://www.pbs.gov.pk/price-statistics (URL not checked by the assistant) | Month-on-month change implied by the file: Sep +1.275%, Oct +1.081%. Published reports (Dawn, Bloom Pakistan, Daily Pakistan, Xinhua; 2 Nov 2026) give about +1.3% (Sep) and +1.08% to +1.1% (Oct) | Last two months consistent; other months not independently checked |
| `data/reference/gold_month_end_apgjsa_2026.csv` (Jan-Oct 2026) | Month-end APGJSA 24K gold per tola, as reported by named news outlets (links per month in the file and in section 3) | Each value read from a dated report; 8 of 10 months have a second outlet or an arithmetic check against the previous day's reported quote; Sep has a single outlet (see section 3) | Method defined and documented (month-end quote). Sep single-source |


## 2. HIES 2024-25 files actually used (names and columns read from the real `.dta` files)

Household key: `(prcode, hhno)`; the script builds `hh_id = prcode*1000 + hhno`. `hhcode` is stored as an approximate float, so it is only used as a tolerance check. Person key: `(prcode, hhno, idc)`. PSU = `prcode`; stratum = first four digits of `prcode`. Weight = `weight` column in the roster (household weight).

| File | Rows | Columns used |
|---|---|---|
| `plist_roster.dta` | 184,564 | `s1aq02` relation to head, `s1aq03` sex, `s1aq10` household member, `s1aq51` age, `s1aq06` marital status, `weight`, `province`, `hhcode` |
| `sec_2ab_education.dta` | 170,901 | `s2aq01` can read, `s2bq01` attendance status, `s2bq05` highest grade completed |
| `sec_1b_emp_income.dta` | 134,468 | `s1bq01` paid job, unpaid family work or business (Yes=1) |
| `Sec_04a_pregnancyhistory.dta` | 44,103 | `s4aq04` age at first marriage (women) |
| `sec_05m1_housingchar.dta` | 30,123 | dwelling type, floor/roof/wall material, cooking and lighting fuel, rooms, nine asset questions (wealth index inputs) |

Not used: `sec_6a_consum_exp.dta` (2,396,159 item-level rows with group-total codes mixed in; summing it risks double counting) and its aggregates; the pipeline uses a housing/asset wealth index instead.

## 3. Month-end gold series (the series now used)

**Definition:** the last APGJSA 24-karat per-tola quote published in each calendar month, as reported by the cited outlets (not APGJSA's own site). One value per month; no averaging. Source: `data/reference/gold_month_end_apgjsa_2026.csv`.

| Month | Quote date | Rs per tola | Confirmation | Links |
|---|---|---|---|---|
| Jan 2026 | Sat 31 Jan | 511,862 | 2 outlets | [Business Recorder](https://www.brecorder.com/news/amp/40405009), [Express Tribune](https://tribune.com.pk/story/2590050/further-decline-in-gold-and-silver-prices-across-markets) |
| Feb 2026 | Sat 28 Feb | 550,562 | 1 outlet + arithmetic (Fri 540,562 + 10,000) | [Business Recorder](https://www.brecorder.com/news/amp/40409424); the Rs10,000 move is also in [Express Tribune](https://tribune.com.pk/story/2595030/gold-hits-5278-an-ounce-after-sharp-increase) |
| Mar 2026 | Tue 31 Mar | 478,762 | 3 outlets | [Business Recorder](https://www.brecorder.com/news/amp/40414054), [ARY](https://arynews.tv/gold-prices-surge-in-pakistan-march-31-2026), [Express Tribune](https://tribune.com.pk/story/2600297/gold-prices-rise-further-in-local-international-markets) |
| Apr 2026 | Thu 30 Apr | 483,962 | 2 outlets | [ARY](https://arynews.tv/gold-prices-rise-in-pakistan-april-30-2026), [Aaj](https://english.aaj.tv/news/amp/330457726) |
| May 2026 | Sat 30 May | 476,162 | 2 outlets | [Express Tribune](https://tribune.com.pk/story/2610533/gold-prices-rise-in-local-global-markets), [Aaj](https://english.aaj.tv/news/330459672) |
| Jun 2026 | Tue 30 Jun | 424,836 | 1 outlet + arithmetic (Mon 428,936 - 4,100) | [Daily Pakistan](https://en.dailypakistan.com.pk/30-Jun-2026/gold-price-in-pakistan-falls-to-rs424836-per-tola-after-fresh-losses), prior day [Dunya News](https://dunyanews.tv/en/Business/959791-gold-prices-fall-by-rs2300-per-tola-in-pakistan) |
| Jul 2026 | Fri 31 Jul | 430,436 | 1 outlet + arithmetic (Thu 427,436 + 3,000) | [Aaj](https://english.aaj.tv/news/330465878); the Rs3,000 move is also in [Samaa](https://www.samaa.tv/2087354481-gold-price-in-pakistan-jumps-rs3-000-per-tola-july-31-2026) |
| Aug 2026 | Mon 31 Aug | 466,136 | 2 outlets | [Dunya News](https://dunyanews.tv/en/Business/970616-gold-price-falls-by-rs1800-per-tola-in-pakistan), [Pakistan Observer](https://pakobserver.net/per-tola-gold-price-drops-to-rs4-65-lac-in-pakistan-check-new-rates/) |
| Sep 2026 | Wed 30 Sep | 441,636 | **1 outlet only** | [ARY](https://arynews.tv/gold-prices-rise-by-rs-4300-tola-in-pakistan) |
| Oct 2026 | Sat 31 Oct | 409,736 | 3 outlets + arithmetic (Fri 420,536 - 10,800) | [Dunya News](https://dunyanews.tv/en/Business/980575-gold-price-falls-by-rs10800-per-tola-in-pakistan), [Daily Pakistan](https://en.dailypakistan.com.pk/02-Nov-2026/today-gold-rates-in-pakistan-per-tola-gold-prices-2-november-2026), [Pakistan Times](https://www.pakistantimes.com/gold-price-drops-by-rs10800-per-tola-in-pakistan-today-silver-also-declines-15970/) |

Limits: values were read from published reports, so spot-check the links before publishing; September has one source; some outlets (for example Daily Pakistan) also publish other benchmarks such as the Rawalpindi-Islamabad Sarafa rate, so only quotes attributed to APGJSA were used.

## 4. Mahr benchmark inputs
- 24K gold per tola: the month-end series in section 3.
- National CPI General Index, base 2015-16 = 100: `pakistan_cpi_2026.csv` (see the CPI row above).
- The benchmark is DERIVED from gold and CPI; it is not observed Mahr data. Ten months cannot show an inflation trend for Mahr.
