# finlog: plan for the 2026 tax return

Resume point for the 2026 確定申告 (filed in February to March 2027). History is in [HISTORY.md](HISTORY.md), the long-term backlog is in [ROADMAP.md](ROADMAP.md), and this file lists what to do next and in what order.

## Goal

One `finlog tax` command group covers the numbers for the return. Each command writes a spreadsheet (or local CSV files without Google credentials). The past 確定申告 sheets are not rebuilt; the tool replaces the hand-filled tabs and keeps the checks.

Done means:

- Every e-Tax input for 2026 comes from a `finlog tax` command or is listed as a manual item, each marked OK, needs review, or manual.
- The 2026 figures match the hand-computed 2026 golden data, or every difference has a known cause.
- After filing, the e-Tax result matches the tool output.

## What's been done (2026-11-27)

- `finlog tax gsu`: vest income (給与所得), dividends (配当所得), foreign tax (外国税額控除), and the year-end carryover (総平均法). FX rates come from MURC, rounding matches the past sheets, and a sale larger than the holdings stops the run.
- `finlog tax iryohi export`: 医療費集計フォーム rows (paste at cell B9 of the official form) and a Checks tab, from the reviewed iryohi_raw CSV.
- `finlog tax iryohi annotate`: merges review suggestions from a Jetski session and highlights rows to check. Rules: [docs/tax/iryohi_review.md](docs/tax/iryohi_review.md).
- Golden tests reproduce the 2025 GSU figures and the 2025 医療費 form. The inputs are private files under `user_data/tax_golden/2025/` (see Private inputs).

## Resume checklist (February 2027)

### 1. Set up

1. `cd dev/finlog`, then `uv sync` and `uv run pytest`. All tests pass; the golden tests are skipped on a machine without `user_data/tax_golden/`.
2. Read `user_data/tax/RESUME_2026.md` (private, not in git) for sheet links and the 2025 carryover.

### 2. GSU for 2026

There were no GSU sales in 2026, so the run covers vests, dividends, and the carryover.

1. Download the 2026 stock statement CSV (Vests) and the Activity Report from the broker site, as in the README tab of the 確定申告 sheet.
2. Build the Dividend CSV (broker layout: Entry Date, Activity, Type of Money, Cash, Number of Shares, Share Price). Use a header-only Sales CSV.
3. Run:

   ```bash
   finlog tax gsu \
     --vests <vests.csv> --dividend <dividend.csv> --sales <sales.csv> \
     --carryover user_data/carryover_2025.json \
     --output-carryover user_data/carryover_2026.json
   ```

4. Compare with the hand-computed 2026 figures. Save the inputs, MURC rates (`fx_rates.csv`), and `expected.json` under `user_data/tax_golden/2026/`, then add the 2026 case to the golden test (parametrize over years).

### 3. 医療費 for 2026

Follow [docs/tax/iryohi_review.md](docs/tax/iryohi_review.md):

1. Run the BigQuery pipeline by hand and export iryohi_raw (Zaim download, raw_Zaim upload, `finlog.merge`, transport database update, `finlog.iryouhi`).
2. Download iryohi_raw as CSV to `user_data/tax/2026/iryohi_raw.csv`.
3. Ask Jetski to review it with the rules page and write `iryohi_suggestions.csv`, then run `finlog tax iryohi annotate`.
4. Review `include` and `receipt` in the sheet, download it as CSV, and run `finlog tax iryohi export`.
5. Fix the Checks findings or accept them, then paste the form rows into the official 医療費集計フォーム.
6. Save the reviewed CSV, the submitted rows, and `iryohi_expected.json` under `user_data/tax_golden/2026/` for a 2026 golden case.

### 4. Build the data checks

Add `finlog tax checks` with a per-year config file (TOML; this needs `requires-python >= 3.11`). The config lists input files, sheet exports, and manual values. Checks summarize external data; they do not rebuild the past sheets.

| Check | Input | Output |
| :-- | :-- | :-- |
| ふるさと納税 | Tracking sheet log tab (CSV) | Year total, rows without a receipt, total against the cap |
| 寄付金控除 | Zaim CSV (税金 > その他, not ふるさと納税) | Donation list and total, compared with receipts in the config |
| 保険料控除 | Certificate amounts in the config | Deduction per type (一般生命, 介護医療, 個人年金, 地震), new and old rules |
| 為替差益・差損 | Sony Bank CSV, other banks in the config | Net gain or loss, and whether it is reportable 雑所得 |

Then add `finlog tax summary`: one spreadsheet with a Summary tab (every e-Tax input, source, status) plus the detail tabs of gsu, iryohi, and checks. Manual items such as 予定納税額 and 配偶者所得 appear as manual rows.

## Private inputs

These stay on the local machine under `user_data/` (ignored by git). Copy them when working on another machine.

| Path | Content |
| :-- | :-- |
| `user_data/tax_golden/2025/` | 2025 GSU and 医療費 inputs, MURC rates, expected figures |
| `user_data/carryover_2025.json` | Year-end 2025 holdings and average cost, the 2026 starting point |
| `user_data/fx_cache.csv` | Cached FX rates (MURC rows are reused) |
| `user_data/tax/RESUME_2026.md` | Sheet links and notes for this plan |

## Open questions

- 医療費 BigQuery automation: the saved query SQL and the sign-in account are still to be decided (ROADMAP).
- 保険料控除: whether the certificates are collected through マイナポータル連携 or entered by hand.
