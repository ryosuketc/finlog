# Amex Card Data Schema Specification

## Overview
This document defines the schema and preprocessing rules for American Express (Amex Proper) CSV statements.

- **Default Encoding**: Shift_JIS (CP932)
- **Header Line**: Present (Line 1)

---

## Raw CSV Field Definitions (`raw_amex`)

| Field Name (JP) | Field Name (EN) | Data Type | Nullable | Example Values | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ご利用日 | `use_date` | Date (YYYY/MM/DD) | No | `2026/06/21` | Transaction date |
| データ処理日 | `process_date` | Date (YYYY/MM/DD) | Yes | `2026/06/21` | Processing date by Amex |
| ご利用内容 | `merchant_raw` | String | No | `アマゾン　ＪＰ　マーケットプレイス　　` | Merchant description (may contain full-width trailing spaces) |
| カード会員様名 | `cardholder` | String | No | `RYOSUKE TACHIBANA`, `YURI TACHIBANA` | Name of cardholder (Main / Family card) |
| 会員番号 # | `card_number_suffix` | String | No | `-23007`, `-23015` | Card number suffix (5 digits with `-`) |
| 金額 | `amount_str` | String / Numeric | No | `"16,746"`, `799` | Amount in JPY (formatted with commas if > 999) |
| 海外通貨利用金額 | `foreign_amount` | String | Yes | `` | Foreign currency amount (if applicable) |
| 換算レート | `exchange_rate` | String | Yes | `` | Exchange rate (if applicable) |

---

## Parser & Preprocessing Rules

1. **Encoding Handling**: Must read with `cp932` / `shift_jis` and convert strings to UTF-8.
2. **Merchant Name Normalization**: Strip full-width (`\u3000`) and half-width trailing spaces.
3. **Amount Normalization**: Remove quotes and commas (`,`) from `金額` and convert to integer/numeric type.
4. **Cardholder & Account Mapping**:
   - `RYOSUKE TACHIBANA` (-23007) -> Main Card (`Amex Proper Unpaid` / `Amex Proper`)
   - `YURI TACHIBANA` (-23015) -> Family Card (`Yuri Amex Proper Unpaid` / `Amex Proper Family`)
5. **Unique ID Assignment**: Prepend unique transaction ID (e.g. `AMEX-00001` or UUID) as the leftmost column.
