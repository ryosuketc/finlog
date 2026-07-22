# finlog: Development Roadmap

This document tracks upcoming features, ongoing validation milestones, and planned improvements for `finlog`.

---

## 💳 `finlog credit` (Credit Card Reconciliation)

### Monthly Routine & Real-World Validation
- [ ] **Monthly E2E Validation**: Perform monthly reconciliation using real Zaim exports and actual monthly statements (**ANA VISA Platinum**, **Amex Proper**). *(Note: Initial iteration on Amex data for 2026-07 completed; continue optimizing)*
- [ ] **Merchant Matching Optimization**: Fine-tune fuzzy merchant containment matching rules and date proximity thresholds ($\pm 5$ days) against real-world Japanese payee strings.
- [ ] **Many-to-One (N-to-1) Transaction Reconciliation**: Support matching multiple Zaim log entries (e.g., ¥100 + ¥200) bundled into a single credit card statement line (e.g., ¥300 charge). *(Note: Initial implementation complete for exact matches; require further validation in upcoming monthly audits)*


---

## 💴 `finlog gsu` (GSU Tax Return Calculation)

### Yearly Routine & Tax Filing Verification
- [ ] **e-Tax Verification**: Verify generated figures (給与所得, 配当所得, 外国税控除, 譲渡所得) against official National Tax Agency (国税庁 e-Tax) 確定申告 submission forms.
- [x] **Sales Fee / Broker Expenses (譲渡費用)**: Support optional brokerage sales fees and transaction costs in capital gains calculations.

---

## 🛠️ Infrastructure & Quality Assurance

- [ ] **Automated Report Verification**: Add schema validation checks for generated Google Spreadsheets to ensure formatting consistency.
