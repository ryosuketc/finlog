# ANA VISA Card Data Schema Specification

## Overview
This document defines the schema and preprocessing rules for ANA VISA Platinum CSV statements (`visa_202607.csv`).

- **Default Encoding**: Shift_JIS (CP932)
- **Header Line**: None (No column header row in raw CSV)
- **Metadata Header**: Line 1 contains cardholder metadata (`橘　亮丞　様,4980-11**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム`)
- **Footer Row**: Last line contains summary total (`,,,,,863014,`)

---

## Raw CSV Structural Layout (`raw_visa`)

### Line 1 (Metadata Header)
- Column 1: Cardholder Name (`橘　亮丞　様`)
- Column 2: Masked Card Number (`4980-11**-****-****`)
- Column 3: Card Product Name (`ＡＮＡＶＩＳＡプラチナプレミアム`)

### Lines 2 to N-1 (Transaction Rows)

| Column Index | Field Name (EN) | Data Type | Nullable | Example Values | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Col 0 | `use_date` | Date (YYYY/MM/DD) | No | `2026/05/16` | Transaction date (利用日) |
| Col 1 | `merchant_raw` | String | No | `焼肉きんぐ三鷹野崎店`, `坂内吉祥寺南店／ｉＤ` | Merchant / store description (利用店名・商品名) |
| Col 2 | `amount` | Numeric | No | `134616`, `10642` | Transaction amount in JPY (利用金額) |
| Col 3 | `payment_type` | String | Yes | `１` | 支払区分 (Payment type code) |
| Col 4 | `payment_count` | String | Yes | `１` | 今回回数 (Current installment count) |
| Col 5 | `billed_amount` | Numeric | No | `134616`, `10642` | Billed amount in JPY (当月支払額) |
| Col 6 | `note` | String | Yes | `` | Note / remarks (備考・メモ) |

### Line N (Summary Footer)
- Total payment summary line (Col 5 = total amount e.g. `863014`). Must be ignored during transaction parsing.

---

## Parser & Preprocessing Rules

1. **Encoding Handling**: Must read with `cp932` / `shift_jis` and convert output strings to UTF-8.
2. **Metadata Extraction**: Parse Line 1 to identify card product (`ANA VISA Platinum`) and cardholder.
3. **Line Classification**:
   - Line 1 -> Store as statement metadata.
   - Line N (where Col 0 is empty/null and Col 5 is non-empty) -> Validate total amount against sum of transaction rows, then exclude from transaction dataset.
   - Intermediate lines -> Parse as transaction rows.
4. **Account Mapping**: `ANA VISA Platinum Paid` / `ANA VISA Platinum Unpaid`.
5. **Unique ID Assignment**: Prepend unique transaction ID (e.g. `VISA-00001` or UUID) as the leftmost column.
