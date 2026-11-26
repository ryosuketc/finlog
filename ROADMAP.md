# finlog: Development Roadmap

This document tracks upcoming features, ongoing validation milestones, and planned improvements for `finlog`.

---

## 💳 `finlog credit` (Credit Card Reconciliation)

### Monthly Routine & Real-World Validation
- [ ] **Monthly E2E Validation**: Perform monthly reconciliation using real Zaim exports and actual monthly statements (**ANA VISA Platinum**, **Amex Proper**). *(Note: Initial iteration on Amex data for 2026-07 completed; continue optimizing)*
- [ ] **Merchant Matching Optimization**: Fine-tune fuzzy merchant containment matching rules and date proximity thresholds ($\pm 5$ days) against real-world Japanese payee strings.
- [ ] **Many-to-One (N-to-1) Transaction Reconciliation**: Support matching multiple Zaim log entries (e.g., ¥100 + ¥200) bundled into a single credit card statement line (e.g., ¥300 charge). *(Note: Initial implementation complete for exact matches; require further validation in upcoming monthly audits)*


---

## 💴 `finlog tax gsu` (GSU Tax Return Calculation)

### Yearly Routine & Tax Filing Verification
- [ ] **e-Tax Verification**: Verify generated figures (給与所得, 配当所得, 外国税控除, 譲渡所得) against official National Tax Agency (国税庁 e-Tax) 確定申告 submission forms.
- [x] **Sales Fee / Broker Expenses (譲渡費用)**: Support optional brokerage sales fees and transaction costs in capital gains calculations.

### Capital Gains (譲渡所得)
The engine already computes sales, because the year-end average cost (carryover) needs them. Full verification waits for a tax year with real sales (none in 2026).
- [ ] **Golden Test with Real Sales**: Compare a year with sales against the 確定申告 sheet for that year (proceeds, acquisition cost, fee, gain).
- [ ] **Sale Rounding Rules**: Match the past sheets: round proceeds up, and round the per-share average cost up to the yen when it is used for a sale (総平均法に準ずる方法).
- [ ] **Sale Fee FX Rate**: The past sheets convert the sale fee with TTS, and finlog uses TTB. Confirm which rate to use.
- [ ] **Read Sales from the Stock Statement Export**: Parse the Activity Report (Withdrawals Report) directly instead of a hand-built Sales CSV.

## 🏥 `finlog tax iryohi` (医療費控除)

For now the BigQuery pipeline runs by hand and produces the `iryohi_raw` review sheet. Review and export start from that sheet.
- [ ] **Automate the BigQuery Pipeline**: Run the saved queries `finlog.merge` (rebuilds the `financeLog.master` table) and `finlog.iryouhi` from the CLI, and write the result to a review sheet. Zaim download, the `raw_Zaim` upload, and the transport database update stay manual.
  - Move both saved queries into the repo as SQL files with the tax year as a parameter.
  - Add the BigQuery scope to the existing user OAuth sign-in, so one sign-in covers Sheets, Drive (for the sheet-backed transport table), and BigQuery in the FinLog BigQuery project.
- [x] **Export to 医療費集計フォーム**: `finlog tax iryohi export` writes the form rows and a Checks tab from the reviewed sheet.
- [x] **LLM Review Suggestions**: `finlog tax iryohi annotate` merges suggestions from a Jetski review ([docs/tax/iryohi_review.md](docs/tax/iryohi_review.md)).
- [ ] **Read the Sheet Directly**: Read iryohi_raw from Google Sheets by URL instead of a downloaded CSV.
- [ ] **Write the Official Form File**: Fill the National Tax Agency 医療費集計フォーム xlsx directly instead of rows to paste.

---

## 🛠️ Infrastructure & Quality Assurance

- [ ] **Automated Report Verification**: Add schema validation checks for generated Google Spreadsheets to ensure formatting consistency.
