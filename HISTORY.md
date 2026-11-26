# finlog history

This file records what changed in finlog, why, and where the work happened.
Newest entries come first. Times are JST.

Sources: the commit log and the Jetski conversations listed in each entry.
Older conversations are archived, and only their titles and first prompts were
available when this file was written. A conversation-to-commit link marked
"inferred" comes from matching timestamps, not from the transcript.

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

## 2026-08-22: Google Sheets export error

**Summary**: A conversation looked into a Google Sheets export error. No commit
followed it. The 2026-09-22 OAuth fix may cover the same failure, but that is
not confirmed.

**Conversation**: 2e337d81-bc4b-4764-a85b-275fd477ba5d ("Finlog Google Sheets
Export Error").

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

## Open items

See [ROADMAP.md](ROADMAP.md) for the full list. Main items:

*   Monthly end-to-end reconciliation with real Zaim exports and statements.
*   More tuning of merchant matching and N:1 bundling against real data.
*   Check `finlog gsu` figures against the e-Tax filing.
