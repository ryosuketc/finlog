# Credit Card Intermediate Data Schema Specification

## Overview
This document defines the universal **Credit Card Intermediate Data Model** for `finlog`. 

- **Purpose**: Normalizes credit-company-specific CSV differences (Amex, VISA, and future card statement formats) into a universal format.
- **Alignment**: Designed to align seamlessly with the preprocessed Zaim transaction schema (defined by the SQL query in `zaim_schema.md`) to enable transaction matching and verification.

> **Note**: Zaim log data is processed separately according to the standardized SQL transformation rules documented in [zaim_schema.md](file:///usr/local/google/home/rtachibana/repos/agents/dev/finlog/docs/schema/zaim_schema.md).

---

## Credit Card Intermediate Schema Definition

| Field Name | Data Type | Nullable | Description | Mapping from Card CSV (Amex / VISA) |
| :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | String | No | Unique transaction ID (leftmost column) | Auto-generated (e.g., `AMEX-00001`, `VISA-00001`) |
| `card_company` | String | No | Card company / product name | `Amex Proper`, `ANA VISA Platinum` |
| `date` | Date (YYYY-MM-DD) | No | Transaction date | Parsed from `ご利用日` / `use_date` |
| `account` | String | No | Mapped Zaim-compatible account name | e.g. `Amex Proper Unpaid`, `ANA VISA Platinum Paid` |
| `amount` | Numeric | No | Transaction amount in JPY (Integer) | Cleaned numeric from `金額` / `利用金額` |
| `currencycode` | String | No | Currency code (`JPY`) | Default `JPY` |
| `payee_payer` | String | No | Normalized merchant / store name | Cleaned `ご利用内容` / `利用店名・商品名` |
| `cardholder` | String | Yes | Card member name | `カード会員様名` (`RYOSUKE TACHIBANA`, `YURI TACHIBANA`) / `橘 亮丞` |
| `card_number_suffix` | String | Yes | Last digits / masked card number | `会員番号 #` (`-23007`) / `4980-11**` |
| `note` | String | Yes | Remarks / notes | VISA `note` (Col 6) / Empty for Amex |
| `raw_row_index` | Numeric | No | Original line index in source CSV | 1-based index of source line |

---

## Alignment with Zaim Preprocessed Schema

The Credit Card Intermediate Schema fields map directly to preprocessed Zaim fields for matching:

| Credit Card Intermediate Field | Corresponding Zaim Preprocessed Field | Matching Criteria |
| :--- | :--- | :--- |
| `amount` | `amount` | MUST match exactly |
| `card_company` | `account` (`accountfrom` for payment) | Mapped account alignment (e.g., Zaim `Amex Proper Unpaid` / `Amex Proper Paid` maps to card `Amex Proper`) |
| `date` | `date` | Matches within configurable date window (default: ±5 days) |
| `payee_payer` | `payee_payer` (`merchant`) | Used for merchant verification / auxiliary visual inspection |

---

## Account Mapping Rules

Zaim uses status-suffixed account names (e.g., `Unpaid` vs `Paid`), whereas Credit Card statements represent the card/company name directly.

- **`Amex Proper`**: Matches Zaim accounts `Amex Proper Unpaid`, `Yuri Amex Proper Unpaid`, `Amex Proper Paid`.
- **`ANA VISA Platinum`**: Matches Zaim accounts `ANA VISA Platinum Unpaid`, `ANA VISA Platinum Paid`.

---

## Transaction Matching Logic Overview

When comparing normalized credit card transactions against preprocessed Zaim transactions:
1. **Exact Amount Match**: `Card.amount == Zaim.amount`
2. **Account Alignment**: `Card.account == Zaim.account`
3. **Date Window Alignment**: Accounts for delay between actual purchase date (Zaim) and card posting date (Card CSV).
4. **Result Flags**:
   - **Matched**: Credit card transaction successfully paired with a Zaim entry.
   - **Unmatched**: Credit card transaction has no corresponding Zaim entry (highlighted in output sheet).
