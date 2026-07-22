# finlog 💳 💴

> [!CAUTION]
> **EXPERIMENTAL & PROTOTYPE TOOL NOTICE**
> 
> `finlog` is an experimental internal tool under active development:
> - **`finlog credit`**: Must be validated and corrected through regular monthly reconciliation of real credit card statements against personal finance logs.
> - **`finlog gsu`**: Must be validated and verified through actual annual Japanese tax return filings (確定申告).
> 
> **DO NOT rely solely on this tool for official tax reporting or financial auditing without manually verifying all generated figures!**

**finlog** is a modular Python CLI tool for personal finance management:
1. **Credit Card Reconciliation (`finlog credit`)**: Matches personal finance log entries (e.g. **Zaim** CSV exports) against credit card statements (**ANA VISA Platinum**, **Amex Proper**, etc.) to identify unmatched or suspicious charges.
2. **Google Stock Units (GSU) Tax Calculator (`finlog gsu`)**: Automates Japanese tax return calculations (確定申告) for Google Stock Units (GSU), computing **給与所得 (Salary Income)**, **配当所得 & 外国税控除 (Dividend Income & Foreign Tax Withheld)**, and **譲渡所得 (Capital Gains)** using the Total Average Cost method (総平均法).

---

## ✨ Key Features

### 💳 Credit Card Reconciliation (`finlog credit`)
- 🔍 **2-Phase Automated Matching Architecture**:
  - **Phase 1 (1:1 Matching)**: Matches 1-to-1 transactions using exact amount verification, date proximity ($\pm 5$ days), and merchant containment with native alias normalization (`finlog/matching/merchant_map.json`).
  - **Phase 2 (N:1 Bundled Matching)**: Reconciles multiple Zaim log entries (e.g., ¥100 + ¥200) bundled into a single credit card charge line (e.g., ¥300) sharing exact date, account, and normalized merchant name.
- 🏦 **Card Company to Zaim Account Mapping**: Automatically maps credit cards (VISA, AMEX) to Zaim `Unpaid` and `Paid` accounts.
- 📊 **Streamlined Verification Sheets**: Generates multi-tab Google Spreadsheets featuring `Zaim View`, `Credit View` (sorted by cardholder and date ASC, flagging bundled matches as `Matched (Bundled)`), and raw data logs (sorted by date ASC).



### 💴 GSU Tax Calculator (`finlog gsu`)
- 📈 **Total Average Cost Method (総平均法)**: Chronologically tracks stock acquisitions (Vests + Dividend reinvestments) and sales to calculate average acquisition cost per share in JPY.
- 💱 **Automated FX Rate Management**: Retrieves historical USD/JPY rates via Frankfurter API with preceding business day fallback, computes TTS (`TTM + 1.0`) and TTB (`TTM - 1.0`), and caches daily rates to `user_data/fx_cache.csv`.
- 🔄 **Year-over-Year JSON Carryover**: Seamlessly saves and loads stock inventory state (`--carryover`, `--output-carryover`) across tax years:
  ```json
  {
    "year": 2024,
    "shares": 327.575,
    "average_cost_per_share": 226.83
  }
  ```
- 📊 **Tax Report Spreadsheets**: Exports detailed tabs for `Vests` (給与所得), `Dividend` (配当所得・外国税控除), `Sales & Capital Gains` (譲渡所得), `Acquisition Cost Audit` (取得単価・在庫計算監査ログ), `FX Rates Audit`, and raw CSV inputs.

---

## 🛠️ Installation

`finlog` is managed via [`uv`](https://github.com/astral-sh/uv).

To install `finlog` globally as an editable CLI tool:

```bash
cd dev/finlog
uv tool install --editable .
```

After installation, the `finlog` command is available directly in your shell:

```bash
finlog --help
```

---

## 🔑 Setting up Google Sheets API Access (OAuth 2.0)

To export outputs directly to Google Spreadsheets:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create an OAuth 2.0 **Desktop Application** Client ID.
2. Download the JSON credentials file and save it to your home directory at:
   ```bash
   ~/.config/gspread/credentials.json
   ```
3. When you run `finlog` for the first time, an authentication browser server starts. The authorized session will be saved automatically to `~/.config/gspread/authorized_user.json`.

*(Note: If Google API credentials are not found, `finlog` gracefully falls back to generating local CSV files in `user_data/output/`)*

---

## 🚀 Usage Guide

### 1. Credit Card Reconciliation (`finlog credit`)

```bash
finlog credit \
  --log user_data/credit_sample/Zaim.20260720044643.csv \
  --log-type zaim \
  --card user_data/credit_sample/visa_202607.csv \
  --card-type visa
```

#### CLI Options (`finlog credit`)

| Option | Shortcut | Description | Default |
| :--- | :--- | :--- | :--- |
| `--log` | | Path to personal finance log CSV file (e.g. Zaim export). **[Required]** | |
| `--log-type` | | Type of finance log app. | `zaim` |
| `--card` | | Path to credit card statement CSV file. **[Required]** | |
| `--card-type` | | Type of credit card (`visa`, `ana_visa`, `amex`, `amex_proper`). **[Required]** | |
| `--include-all-accounts` | | Include Zaim `Paid` accounts in addition to `Unpaid` accounts. | `False` |
| `--credentials` | `-c` | Optional custom path to OAuth `credentials.json`. | `None` |
| `--service-account` | | Optional custom path to Service Account JSON. | `None` |

---

### 2. GSU Tax Calculation (`finlog gsu`)

```bash
finlog gsu \
  --vests user_data/tax_sample/tax_report_inputs\ -\ Vests.csv \
  --dividend user_data/tax_sample/tax_report_inputs\ -\ Dividend.csv \
  --sales user_data/tax_sample/tax_report_inputs\ -\ Sales.csv \
  --carryover user_data/carryover_2023.json \
  --output-carryover user_data/carryover_2024.json
```

#### CLI Options (`finlog gsu`)

| Option | Description | Default |
| :--- | :--- | :--- |
| `--vests` | Path to Vests CSV file (`Vests.csv`). **[Required]** | |
| `--dividend` | Path to Dividend CSV file (`Dividend.csv`). **[Required]** | |
| `--sales` | Path to Sales CSV file (`Sales.csv`). **[Required]** | |
| `--carryover` | Path to previous year's carryover JSON file. | `None` |
| `--output-carryover` | Path to save current year's carryover JSON file. | `user_data/carryover_<YEAR>.json` |
| `--use-cache / --no-cache` | Enable or disable local FX rate CSV caching (`user_data/fx_cache.csv`). | `True` |
| `--credentials` | Optional custom path to OAuth `credentials.json`. | `None` |
| `--service-account` | Optional custom path to Service Account JSON. | `None` |

---

## 📚 System Design & Documentation

Detailed architecture design plans and input schema specifications are located under `docs/`:

- 💳 **Credit Reconciliation Documentation**:
  - Design Plan: [docs/credit/design_plan.md](docs/credit/design_plan.md)
  - Schemas: [docs/credit/schema/](docs/credit/schema/)
- 💴 **GSU Tax Reporting Documentation**:
  - Design Plan: [docs/tax/design_plan.md](docs/tax/design_plan.md)
  - Acquisition Cost Calculation & Audit Guide: [docs/tax/acquisition_cost_calculation.md](docs/tax/acquisition_cost_calculation.md)
  - Input Schemas: [docs/tax/schema/input_schemas.md](docs/tax/schema/input_schemas.md)
- 📌 **Development Roadmap**:
  - Roadmap: [ROADMAP.md](ROADMAP.md)

---

## 🧪 Running Unit Tests

Run the test suite via `uv`:

```bash
uv run pytest
```

---

## 📄 License

Internal tool developed for personal finance log management and tax reporting.
