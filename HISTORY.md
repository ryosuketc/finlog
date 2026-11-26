# finlog history

This file records what changed in finlog, why, and where the work happened.
New entries go at the bottom. Times are JST.

Sources: the commit log and the Jetski conversations listed in each entry.
Older conversations are archived, and only their titles and first prompts were
available when this file was written. A conversation-to-commit link marked
"inferred" comes from matching timestamps, not from the transcript.

## 2026-07-20 to 2026-07-22: Initial build

**Summary**: Built finlog as a uv-managed Python CLI with two commands:
`finlog credit` matches Zaim logs against ANA VISA and Amex statements, and
`finlog gsu` calculates Japanese tax figures for GSUs. Output goes to a
multi-tab Google Sheet, or to local CSV files when no credentials exist.

**Changes**:

*   Initial commit with parsers, matching engine, tax engine, sheet writer,
    design docs, schemas, and tests.
*   Separate production and development Drive folders, selected with `--dev`
    or `--folder-id`.

**Commits**: 71ea899a, 3f8caaab, 4c1032fd (2026-07-22).

**Conversations** (all inferred from titles and timing):

*   042d16b4-f1d0-42a7-a96a-09f8e56ab724: "Initialize Finlog Sensitive
    Directory" (2026-07-20).
*   862ee8e8-3fc8-4c79-952a-50f2761c43fb: "Finlog Project Status Update"
    (2026-07-21).
*   fc0bb388-a45b-423e-92aa-0e0ee3d3bf78: "Developing Finlog Financial Tool"
    (2026-07-22).
*   5298dc07-e07c-43f0-aad6-ae6a60b395f9: "Analyzing Finlog Test CSV"
    (2026-07-22).
*   79e4fd29-905b-4e66-8381-4c0cc602bc73: "Reordering Finlog Date Sort"
    (2026-07-22).

## 2026-07-27: Phase 2 bundled matching

**Summary**: Improved N:1 matching, where several Zaim entries add up to one
card charge.

**Changes**:

*   Broad merchant matching (similarity of 0.4 or more) for bundled matches,
    so they work without a `merchant_map.json` entry.
*   Signed sums, so cashback or discount entries (for example 13,000 and -500
    for a 12,500 charge) can bundle.
*   Renamed `date_tolerance_days` to `match_window_days` and exposed it as
    `--match-window-days` (default 5).
*   Bundled matches are reported in the run summary.

**Commit**: d8a639e8.

**Conversation** (inferred): 0a09cb1b-5d9a-4f70-b64d-9755e7e913f1 ("Reviewing
Finlog Custom Mappings").

## 2026-08-22: Google Sheets export error

**Summary**: A conversation looked into a Google Sheets export error. No commit
followed it. The 2026-09-22 OAuth fix may cover the same failure, but that is
not confirmed.

**Conversation**: 2e337d81-bc4b-4764-a85b-275fd477ba5d ("Finlog Google Sheets
Export Error").

## 2026-09-22: OAuth expiry, Amex encoding, and raw cell quoting

**Summary**: Fixed three problems found during a run on Mac input files.

**Changes**:

*   An expired or revoked OAuth token (`invalid_grant`) now deletes the cached
    token and runs the sign-in flow again, instead of failing.
*   CSV encoding detection is now ordered: UTF-8 with BOM, then UTF-8, then
    cp932, then chardet. chardet alone misread the Amex CSV (mojibake).
    Ignored tmp/ in git.
*   Sheet writes use `USER_ENTERED` instead of `RAW`, so raw cells no longer
    show a leading quote.

**Commits**: af1d07d8, 8369457e, 94939e1e.

**Conversation**: c59fe656-304e-4052-b152-6695ae051475 ("Reset Finlog OAuth
Authentication").

## 2026-11-21 to 2026-11-26: VISA family card support

**Summary**: A family ANA VISA card was added, with its own Zaim account
("Yuri ANA VISA Platinum Unpaid"). The statement now has one section per card.
The parser read only the first section header, so family charges got the main
cardholder and never matched the family Zaim account.

**Changes**: Flattened the VISA statement to one row per transaction, scoped
matching per cardholder for VISA and Amex, and added a Reformatted Credit Card
Log sheet next to the unchanged raw sheet.

**Commit**: 24726b1e (2026-11-26).

**Conversation**: df1fe921-ce91-4335-84a0-d8cb96818a74 ("Finlog CLI Hardcoded
ANA VISA Platinum"). It started as a check for hardcoded "ANA VISA Platinum
Unpaid" logic.

## 2026-11-27: Credit View layout for manual reconciliation

**Summary**: Reshaped the Credit View tab for monthly manual review. Card
identity columns now come first, and three empty manual columns sit on the
right. Rows get a color once you fill a manual column, and the header rows of
both views are frozen.

**Changes**:

*   Renamed the model field `card_company` to `card_name` across the model,
    parsers, matching engine, tests, and schema docs.
*   Credit View columns: `transaction_id`, `card_name`, `cardholder`,
    `card_number_suffix`, `date`, `amount`, `payee_merchant`, `note`,
    `match_status`, `matched_transaction_id`, `manual_review`, `manual_fix`,
    `manual_note`.
*   Froze row 1 on Zaim View and Credit View (gspread `Worksheet.freeze`).
*   Added conditional formats on Credit View: a filled `manual_fix` colors the
    row #D0E0E3 (light cyan 3), and a filled `manual_review` colors it #D9EAD3
    (light green 3). `manual_fix` wins when both are filled.

**Key decisions**:

*   `card_name` over `card`: `card` already means the statement CSV path
    (the `--card` option), and the value is a product name, not a company.
*   Renamed the model field, not only the sheet header, so the header still
    equals the field name and no mapping layer is needed.
*   The sheet writer stays generic. The CLI chooses which tabs to freeze and
    which column and color pairs to highlight (`frozen_header_sheets`,
    `row_highlight_rules`).
*   Rule order sets precedence because Sheets applies the first matching
    conditional format rule.
*   Colors use the Sheets palette values. Screenshots were off by one in a
    single channel.

**Verification**: 52 tests passed with `pytest`. The output sheet was checked
by hand.

**Commits**: c04d160d, f7bfe60e, f1c95cc9, cb789850, 90f51188.

**Conversation**: fcf1d6d7-b255-4046-8113-cefbe5dbd9e6 ("Finlog Credit View
Output Modification Plan").

## 2026-11-27: Tax command group, MURC rates, and 2025 golden test

**Summary**: Started the 2026 tax return work. GSU moved to `finlog tax gsu`,
FX rates now come from MURC like the past returns, and a golden test
reproduces the filed 2025 figures.

**Changes**:

*   `finlog gsu` is now `finlog tax gsu`, with no alias.
*   FX rates come from the MURC historical rate page, with Frankfurter as a
    marked fallback. The made-up 150 JPY offline rate is gone; the command now
    fails with `FXRateUnavailableError`.
*   GSU totals follow the past sheets: rows keep exact yen, yearly totals round
    up, acquisition costs are not rounded, and the carryover keeps full
    precision.
*   A sale larger than the holdings now stops with `InsufficientSharesError`.
*   ROADMAP: capital gain verification (no 2026 sales) and the 医療費 BigQuery
    automation are deferred.

**Key decisions**:

*   The golden inputs are personal data, so they live in
    `user_data/tax_golden/2025/` (not in git). The golden and CLI tests skip
    when they are missing.
*   The golden test found one error in the 2025 sheet: one dividend
    reinvestment was priced at the TTS of the dividend date instead of the
    purchase date, which moved the year-end average cost slightly. The sheet
    was corrected, and the golden test expects the corrected value.
*   The expected figures live next to the inputs (`expected.json`), so no
    personal amounts are in the repository.

**Verification**: 67 tests passed with `pytest`. A live run against MURC
produced the same 2025 year-end carryover as the golden test.

**Commits**: bc44834b, e7f43caf, 20a94f42, f84978ad, 50c74e6b.

**Conversation**: dd59cb8c-9c65-4302-9229-fe932913fbf2.

## 2026-11-27: 医療費 export and review annotations

**Summary**: Added `finlog tax iryohi export` and `finlog tax iryohi annotate`.
Both start from the iryohi_raw sheet downloaded as CSV; the BigQuery pipeline
still runs by hand.

**Changes**:

*   `export` keeps rows with `include` set and writes 医療費集計フォーム rows
    (columns B to J of the official form) plus a Checks tab.
*   Checks: unexpected category values, no category, form length limits, no
    receipt (except 交通費), refund larger than the amount, `need_data_fix`,
    and mixed years.
*   `annotate` merges a suggestions CSV from a Jetski review into the sheet and
    highlights rows where the suggestion is unsure or disagrees with `include`.
*   Review rules and the suggestions format:
    [docs/tax/iryohi_review.md](docs/tax/iryohi_review.md).
*   The 2025 GSU sheet was corrected, and the golden expectations were
    updated to match.

**Key decisions**:

*   CSV input instead of reading Google Sheets directly, so the commands work
    without extra sign-in. Direct reading is on the ROADMAP.
*   Suggestions must repeat the payee and amount of their row. `annotate`
    stops on a mismatch, so suggestions cannot land on shifted rows.
*   Unexpected category values are dropped from the form and reported, not
    passed through.

**Verification**: 97 tests passed. The golden test rebuilds the rows and the
total submitted for 2025. All rows match except one hand-added transport row
whose category column held a station name; export now reports it. The 2025
data also shows rows without a category, rows without a receipt, payee names
over the 20-character limit, and rows with `need_data_fix`.

**Commits**: aa8f6c8f, 9f408802.

**Conversation**: dd59cb8c-9c65-4302-9229-fe932913fbf2.

## 2026-11-27: Handoff for the 2026 tax return

**Summary**: Paused the tax work until February 2027. GSU and 医療費 commands
are in place and verified against 2025; the data checks and the summary report
are next. [PLAN.md](PLAN.md) has the resume checklist.

**Next actions**:

*   Run `finlog tax gsu` on the 2026 inputs from the 2025 carryover, and add a
    2026 golden case from the hand-computed figures.
*   Run the 医療費 flow on 2026 data (manual BigQuery run, Jetski review,
    annotate, export).
*   Build `finlog tax checks` with a per-year config, then `finlog tax
    summary`.

**Modified files**: finlog/cli.py, finlog/tax/engine.py,
finlog/tax/fx_provider.py, finlog/tax/iryohi.py, tests (fx provider, tax
golden, tax CLI, tax engine, iryohi, iryohi golden, iryohi CLI, MURC page
fixture), README.md, ROADMAP.md, PLAN.md, docs/tax/design_plan.md,
docs/tax/acquisition_cost_calculation.md, docs/tax/iryohi_review.md,
docs/tax/schema/input_schemas.md, docs/credit/design_plan.md.

**Key decisions**:

*   Personal figures and inputs stay under `user_data/` (ignored by git),
    because this repository is public. Golden tests read their expected values
    from there and skip when the files are missing.
*   The 医療費 BigQuery pipeline stays manual for the 2026 return.

**Output links**: commits bc44834b to e7e41a9d on `main`, and this entry.

**Conversation**: dd59cb8c-9c65-4302-9229-fe932913fbf2.

## Open items

See [PLAN.md](PLAN.md) for the next steps and [ROADMAP.md](ROADMAP.md) for the
full list. Main items:

*   Monthly end-to-end reconciliation with real Zaim exports and statements.
*   More tuning of merchant matching and N:1 bundling against real data.
*   Check `finlog tax gsu` figures against the e-Tax filing, including capital
    gains in a year with sales.
