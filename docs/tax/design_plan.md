# finlog tax (gsu): Architecture & Implementation Plan

## 1. Overview & Objectives

The `finlog tax` module (CLI subcommand `finlog tax gsu`) automates Japanese tax return calculations (確定申告) for Google Stock Units (GSU) across three tax income categories:

1. **給与所得 (Salary Income from Vests)**: Computed from vesting FMV (USD) converted at Vesting Date TTM rate.
2. **配当所得 & 外国税控除 (Dividend Income & Foreign Tax Withheld)**: Cash dividends and US withholding tax converted at Entry Date TTM rate.
3. **譲渡所得 (Capital Gains from Sales)**: Gross sales proceeds converted at Sale Date TTB rate minus Total Average Cost (総平均法 - acquisition events converted at TTS rates, maintaining JPY average cost per share).

---

## 2. Directory Architecture

```text
dev/finlog/
├── docs/
│   ├── credit/                   # Credit card reconciliation documentation
│   │   ├── design_plan.md
│   │   └── schema/
│   │       ├── amex_schema.md
│   │       ├── visa_schema.md
│   │       ├── zaim_schema.md
│   │       └── intermediate_schema.md
│   └── tax/                      # Tax & GSU reporting documentation
│       ├── design_plan.md        # This document
│       └── schema/
│           └── input_schemas.md  # Schema definitions for Vests, Dividend, Sales, and Carryover JSON
├── finlog/
│   ├── models/
│   │   ├── transaction.py        # Credit card & Zaim transaction models
│   │   └── tax.py                # Tax dataclasses & CarryoverState model
│   ├── parsers/
│   │   ├── base.py               # Abstract base parser
│   │   ├── amex.py / visa.py / zaim.py
│   │   └── tax.py                # VestsParser, DividendParser, SalesParser
│   ├── tax/
│   │   ├── __init__.py
│   │   ├── fx_provider.py        # MURC rate page (Frankfurter fallback) & user_data/fx_cache.csv handler
│   │   └── engine.py             # GSUTaxEngine (Total Average Cost & tax summary)
│   ├── cli.py                    # Click CLI entrypoint (credit command, tax group with gsu)
│   └── io/
│       ├── csv_reader.py
│       └── sheets_writer.py      # Google Sheets & CSV exporter
└── tests/
    ├── test_tax_parsers.py
    ├── test_fx_provider.py
    └── test_tax_engine.py
```

---

## 3. Data Models & Dataclasses (`finlog/models/tax.py`)

```python
from dataclasses import dataclass
from decimal import Decimal
import datetime
from typing import Optional, Dict, Any

@dataclass
class CarryoverState:
    year: int
    shares: Decimal
    average_cost_per_share: Decimal  # JPY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "shares": float(self.shares),
            "average_cost_per_share": float(self.average_cost_per_share),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CarryoverState":
        return cls(
            year=int(d["year"]),
            shares=Decimal(str(d["shares"])),
            average_cost_per_share=Decimal(str(d["average_cost_per_share"])),
        )

@dataclass
class VestRecord:
    award_date: datetime.date
    vesting_date: datetime.date
    shares: Decimal
    fmv_usd: Decimal

@dataclass
class DividendRecord:
    entry_date: datetime.date
    activity: str
    cash_usd: Decimal
    shares: Decimal = Decimal("0")
    share_price_usd: Decimal = Decimal("0")

@dataclass
class SaleRecord:
    execution_date: datetime.date
    price_usd: Decimal
    quantity: Decimal

@dataclass
class FXRateRecord:
    date: datetime.date
    ttm: Decimal
    tts: Decimal
    ttb: Decimal
    source: str

@dataclass
class AcquisitionTimelineRow:
    date: datetime.date
    event_type: str
    description: str
    shares_change: Decimal
    price_usd: Decimal
    fx_rate: Decimal
    event_val_jpy: Decimal
    running_shares: Decimal
    running_total_cost_jpy: Decimal
    running_avg_cost_jpy: Decimal
```

---

## 4. FX Rate Management (`finlog/tax/fx_provider.py`)

### Requirements & Strategy
1. **Source**: Fetches USD/JPY daily TTS, TTB, and TTM from the [MURC historical rate page](https://www.murc-kawasesouba.jp/fx/past_3month.php) (三菱UFJリサーチ&コンサルティング), the source cited in past tax returns. Pages for any date since 1990 are available.
2. **Fallback**: If MURC has no rate, falls back to the [Frankfurter API](https://www.frankfurter.app/) (ECB reference rate as TTM, with $\text{TTS} = \text{TTM} + 1.0$ and $\text{TTB} = \text{TTM} - 1.0$). The source column marks these rows. If neither source has a rate, the command fails with `FXRateUnavailableError` instead of using a made-up rate.
3. **Weekend/Holiday Fallback**: Uses the nearest preceding business day (up to 6 days back). The source column records the publication date, for example `MURC (2025-01-24)`.
4. **Caching**: Reads and writes rates to `user_data/fx_cache.csv`. Only MURC rows are reused. Rows from other sources are fetched again, so they are replaced once MURC is reachable.
5. **Cache Control**: Controlled via CLI flag `--use-cache / --no-cache` (default: `--use-cache`).

---

## 5. Total Average Cost & Tax Engine (`finlog/tax/engine.py`)

### Pure Python Implementation Strategy (`decimal.Decimal`)
The engine uses pure Python standard libraries without Pandas dependency to guarantee exact financial decimal precision and clear sequential logic.

### Algorithm (総平均法 - Total Average Cost Method):
*(See detailed audit formulas and rules in [acquisition_cost_calculation.md](acquisition_cost_calculation.md))*
1. **Load Initial State**: Load previous year's `CarryoverState` if `--carryover` JSON is provided.
2. **Merge & Sort Events**:
   - Combine Vests (Acquisition), Dividend Reinvestments `You bought` (Acquisition), and Sales (Disposal) into a unified chronological sequence by date.
3. **Sequential Inventory Processing**:
   - **For Acquisition Event (Vest or Reinvestment)**:
     $$\text{Event Cost JPY} = \text{Shares} \times \text{Price USD} \times \text{TTS}$$
     $$\text{New Total Shares} = \text{Current Shares} + \text{Event Shares}$$
     $$\text{New Total Cost JPY} = \text{Current Total Cost JPY} + \text{Event Cost JPY}$$
     $$\text{average\_cost\_per\_share} = \frac{\text{New Total Cost JPY}}{\text{New Total Shares}}$$
   - **For Sale Event (Disposal)**:
     $$\text{Gross Sale Proceeds JPY} = \text{Shares Sold} \times \text{Sale Price USD} \times \text{TTB}$$
     $$\text{Acquisition Cost of Sold Shares JPY} = \text{Shares Sold} \times \text{average\_cost\_per\_share}$$
     $$\text{Capital Gain JPY} = \text{Gross Sale Proceeds JPY} - \text{Acquisition Cost of Sold Shares JPY}$$
     $$\text{New Total Shares} = \text{Current Shares} - \text{Shares Sold}$$
     $$\text{New Total Cost JPY} = \text{New Total Shares} \times \text{average\_cost\_per\_share}$$
4. **Generate Reports**:
   - Vests Table (給与所得)
   - Dividend Table (配当所得 & 外国税控除)
   - Sales & Capital Gains Table (譲渡所得)
   - Year-end `CarryoverState` JSON object.

### Rounding (matches the past 確定申告 sheets)
- Vest income, cash dividend, and foreign tax rows keep exact yen values. Only the yearly totals are rounded up to the yen (ROUNDUP, away from zero).
- Acquisition costs are not rounded, and the year-end average cost per share is carried over at full precision.
- Sale rounding is not verified yet (see ROADMAP).

### Verification
`tests/test_tax_golden.py` reproduces the 2025 figures from the 2025 確定申告 sheet. Its inputs are personal data under `user_data/tax_golden/2025/` (not in git), so the test is skipped when they are missing.

---

## 6. Output Sheets Architecture

The exporter (`finlog.io.sheets_writer`) creates multi-tab Google Spreadsheets (or local CSV fallback directory):

1. `Vests`: Vest events, TTM rates, JPY income, total salary income.
2. `Dividend`: Cash dividends, IRS withholding tax, TTM rates, JPY totals.
3. `Sales & Capital Gains`: Sales events, TTB rates, average acquisition costs (JPY), proceeds JPY, net capital gains JPY.
4. `Acquisition Cost Audit`: Complete chronological inventory log tracking every event (carryover, vest, reinvestment, sale) with running shares, total JPY cost, and running average cost per share (JPY).
5. `FX Rates Audit`: Log of all dates, TTM, TTS, TTB, and source.
6. `Raw Vests`, `Raw Dividend`, `Raw Sales`: Raw CSV copies for verification.

---

## 7. CLI Command Specification

```bash
finlog tax gsu \
  --vests <path_to_vests_csv> \
  --dividend <path_to_dividend_csv> \
  --sales <path_to_sales_csv> \
  [--carryover <path_to_previous_year_json>] \
  [--output-carryover <path_to_save_next_year_json>] \
  [--use-cache / --no-cache] \
  [--dev] \
  [--folder-id <google_drive_folder_id>] \
  [--credentials <path_to_google_oauth_json>] \
  [--service-account <path_to_service_account_json>]
```
