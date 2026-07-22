# Zaim Data Schema Specification

## Overview
This document defines the schema and preprocessing rules for Zaim CSV log files exported from [Zaim](https://zaim.net/).

- **Default Encoding**: UTF-8
- **Header Line**: Present (Line 1)

---

## Raw CSV Field Definitions (`raw_zaim`)

| Field Name (JP) | Field Name (EN) | Data Type | Nullable | Example Values | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 日付 | `date` | Date (YYYY-MM-DD) | No | `2026-05-20` | Transaction date |
| 方法 | `type` | String | No | `payment`, `income`, `transfer` | Transaction method |
| カテゴリ | `category` | String | Yes | `食費`, `交通`, `教育・教養` | Category |
| カテゴリの内訳 | `subcategory` | String | Yes | `夕食`, `電車`, `子ども関連` | Subcategory |
| 支払元 | `accountfrom` | String | Yes | `ANA VISA Platinum Paid`, `Amex Proper Unpaid`, `現金` | Withdrawal account |
| 入金先 | `accountto` | String | Yes | `SBI ネット銀行`, `Yuri 現金`, `-` | Deposit account |
| 品目 | `item` | String | Yes | `風呂カプセル`, `グリーン 武蔵境東京` | Item detail name |
| メモ | `note` | String | Yes | `#share`, `#ryosuke#input`, `#ichika` | User note and hashtags |
| お店 | `merchant` | String | Yes | `マクドナルド`, `Amazon`, `成城石井` | Store or payee name |
| 通貨 | `currency` | String | Yes | `JPY` | Currency code |
| 収入 | `amountin` | Numeric | Yes | `0`, `1106` | Income amount |
| 支出 | `amountout` | Numeric | Yes | `200`, `10642` | Expense amount |
| 振替 | `transfer` | Numeric | Yes | `0`, `886` | Transfer amount |
| 残高調整 | `adjustment` | Numeric | Yes | `0`, `140` | Balance adjustment amount |
| 通貨変換前の金額 | `beforecurrencyconvert` | Numeric | Yes | `200`, `10642` | Original currency amount |
| 集計の設定 | `aggregation` | String | Yes | `常に集計に含める` | Aggregation setting |

---

## Preprocessing & Transformation Rules

Zaim raw data is transformed into a standardized SQL-equivalent structure:

```sql
SELECT
  'Zaim' AS platform,
  CASE
    WHEN type = 'payment' THEN 'expense'
    WHEN type = 'income' THEN 'income'
    WHEN type = 'transfer' THEN 'transfer'
    ELSE 'ERROR: Invalid data'
  END AS type,
  FORMAT_DATE("%Y", date) AS year,
  FORMAT_DATE("%Y-%m", date) AS month,
  date,
  CASE
    WHEN type = 'payment' THEN accountfrom
    WHEN type = 'income' THEN accountto
    WHEN type = 'transfer' THEN 'transfer'
    ELSE 'ERROR: Invalid data'
  END AS account,
  CASE
    WHEN type = 'payment' THEN amountout
    WHEN type = 'income' THEN amountin
    ELSE NULL
  END AS amount,
  CASE
    WHEN currency IS NOT NULL THEN 'JPY'
    ELSE 'Invalid data'
  END AS currencycode,
  category,
  subcategory,
  item,
  merchant AS payee_payer,
  LOWER(REPLACE(SUBSTR(note, STRPOS(note,'#')+1),'#',',')) AS tag_raw,
  CASE
    WHEN REGEXP_CONTAINS(note, ".*#ryosuke.*") THEN 'ryosuke'
    WHEN REGEXP_CONTAINS(note, ".*#ichika.*") THEN 'ichika'
    WHEN REGEXP_CONTAINS(note, ".*#hakuyo.*") THEN 'hakuyo'
    WHEN REGEXP_CONTAINS(note, ".*#yuri.*") THEN 'yuri'
    ELSE 'Neither ichika/yuri/ryosuke'
  END AS tag_mod,
  CASE
    WHEN STRPOS(note,'#') = 0 THEN note
    ELSE SUBSTR(note, 1, STRPOS(note,'#')-1)
  END AS note
FROM raw_zaim
```

---

## Unique Transaction ID Assignment
- Each transaction is assigned a unique ID in the leftmost column (e.g. `ZAIM-00001` or UUID).
