# Finlog Tax (GSU) Input Data Schemas & Models

## Overview
This document specifies the input data schemas and JSON model definitions required for `finlog gsu` (Japanese tax return calculations for Google Stock Units).

The system accepts three CSV inputs (Vests, Dividend, Sales) and one optional JSON input (Carryover from previous year).

---

## 1. Vests Input CSV Schema (`Vests.csv`)

### Structure & Header
- **Line 1**: Report Metadata Header (e.g. `"Alphabet, Inc. - GSUs (report run on ...)"`). Skiped by parser.
- **Line 2**: Table Header:
  `Purno,Jurisdiction,Award Date,Vesting Date,GSUs Vested,Shares Deposited,Fair Market Value,Amount Subject to Tax Withholding,Total Tax Withheld at Broker,FX Rate,Currency,Release Type,Award Number`
- **Lines 3 to N-4**: Data Rows.
- **Footer Lines**: Legal disclaimers and stock split notes. Skipped by parser.

### Key Fields Processing

| Field Name | Source Column | Type | Example | Description & Rules |
| :--- | :--- | :--- | :--- | :--- |
| `award_date` | `Award Date` | Date (`DD-Mon-YYYY`) | `08-Mar-2023` | Original equity grant date |
| `vesting_date` | `Vesting Date` | Date (`DD-Mon-YYYY`) | `25-Dec-2024` | Date GSUs vested (used for TTM FX lookup) |
| `shares` | `GSUs Vested` | Decimal | `10.034` | Number of vested GSU shares |
| `fmv_usd` | `Fair Market Value` | Decimal (USD) | `$197.57` | Fair Market Value per share in USD |

> **Crucial Rule**: The `FX Rate` column included in `Vests.csv` MUST be ignored. For consistency, FX rates are fetched from a unified data source (Frankfurter API / `fx_cache.csv`).

---

## 2. Dividend Input CSV Schema (`Dividend.csv`)

### Structure & Header
- **Line 1**: Table Header:
  `Entry Date,Activity,Type of Money,Cash,Number of Shares,Share Price,Book Value,Market Value`
- **Data Rows**: Activity-based transactions.

### Key Fields & Activity Categorization

| Field Name | Source Column | Type | Example | Description |
| :--- | :--- | :--- | :--- | :--- |
| `entry_date` | `Entry Date` | Date (`YYYY-MM-DD` / `DD-Mon-YYYY`) | `2024-06-17` | Transaction entry date |
| `activity` | `Activity` | String | `Dividend (Cash)` | Activity type identifier |
| `cash_usd` | `Cash` | Decimal (USD) | `19.8000` / `-5.9400` | Net cash flow in USD |
| `shares` | `Number of Shares` | Decimal | `$0.08` -> `0.08` | Reinvested shares (for `You bought`) |
| `share_price_usd` | `Share Price` | Decimal (USD) | `$178.00` -> `178.00` | Reinvestment purchase price per share |

### Activity Handling Rules
1. `Dividend (Cash)`: Recorded as **配当所得 (Dividend Income)** using TTM FX rate on `entry_date`.
2. `IRS Nonresident Alien Withholding`: Recorded as **外国税控除 (Foreign Tax Withheld)** using TTM FX rate on `entry_date`.
3. `You bought`: Represents dividend auto-reinvestment into shares. Treated as a **Stock Acquisition Event** for 総平均法 (Total Average Cost Method).

---

## 3. Sales Input CSV Schema (`Sales.csv`)

### Structure & Header
- **Line 1**: Table Header:
  `Execution Date,Order Number,Plan,Type,Order Status,Price,Quantity,Net Amount,Net Share Proceeds,Tax Payment Method`
- **Data Rows**: Completed stock sales.
- **Footer Lines**: Stock split disclaimers. Skipped by parser.

### Key Fields Processing

| Field Name | Source Column | Type | Example | Description & Rules |
| :--- | :--- | :--- | :--- | :--- |
| `execution_date` | `Execution Date` | Date (`DD-Mon-YYYY`) | `22-Feb-2024` | Order execution date (used for TTB FX lookup) |
| `price_usd` | `Price` | Decimal (USD) | `$146.00` | Sale price per share in USD |
| `quantity` | `Quantity` | Decimal | `-92` -> `92` | Shares sold (parsed as absolute positive quantity) |
| `net_amount_usd` | `Net Amount` | Decimal (USD) | `"$13,431.89"` | Gross proceeds before broker fees |

---

## 4. Carryover State JSON Schema (`carryover_<YEAR>.json`)

### Purpose
Tracks stock inventory state across tax years for Total Average Cost Method (総平均法).

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FinlogCarryoverState",
  "type": "object",
  "properties": {
    "year": {
      "type": "integer",
      "description": "Tax year of the carryover state (e.g. 2024)"
    },
    "shares": {
      "type": "number",
      "description": "Total stock shares remaining at year-end"
    },
    "average_cost_per_share": {
      "type": "number",
      "description": "Weighted average acquisition cost per share in JPY"
    }
  },
  "required": ["year", "shares", "average_cost_per_share"]
}
```

### Example Instance
```json
{
  "year": 2024,
  "shares": 327.575,
  "average_cost_per_share": 226.83
}
```
