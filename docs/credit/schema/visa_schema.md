# ANA VISA Card Data Schema Specification

## Overview
This document defines the schema and preprocessing rules for ANA VISA Platinum CSV statements (`visa_202612.csv`).

- **Default Encoding**: Shift_JIS (CP932)
- **Header Line**: None (No column header row in raw CSV)
- **Sections**: The file holds one section per card. Each section starts with a section header row (cardholder, masked card number, card product). One statement can contain several sections, such as the main member's physical card, the main member's GooglePay/iD card, and a family member's card.
- **Subtotal Rows**: Each cardholder's sections end with a subtotal row (`,,,,,580214`).
- **Total Row**: The last line contains the statement total (`,,,,,650965,`).

---

## Raw CSV Structural Layout (`raw_visa`)

```
<cardholder A>,<card number 1>,ＡＮＡＶＩＳＡプラチナプレミアム
<transaction rows>
<cardholder A>,<card number 2>,ＧｏｏｇｌｅＰａｙ／ｉＤ
<transaction rows>
,,,,,<subtotal for cardholder A>
<cardholder B>,<card number 1>,ＡＮＡＶＩＳＡプラチナプレミアム
<transaction rows>
,,,,,<subtotal for cardholder B>
,,,,,<statement total>,
```

### Section Header Rows
- Column 1: Cardholder Name (`山田　太郎　様`)
- Column 2: Masked Card Number (`1234-56**-****-****`)
- Column 3: Card Product Name (`ＡＮＡＶＩＳＡプラチナプレミアム`, `ＧｏｏｇｌｅＰａｙ／ｉＤ`)

### Transaction Rows

| Column Index | Field Name (EN) | Data Type | Nullable | Example Values | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Col 0 | `use_date` | Date (YYYY/MM/DD) | No | `2026/05/16` | Transaction date (利用日) |
| Col 1 | `merchant_raw` | String | No | `焼肉きんぐ三鷹野崎店`, `坂内吉祥寺南店／ｉＤ` | Merchant / store description (利用店名・商品名) |
| Col 2 | `amount` | Numeric | No | `134616`, `-1405` | Transaction amount in JPY (利用金額); negative for refunds |
| Col 3 | `payment_type` | String | Yes | `１` | 支払区分 (Payment type code) |
| Col 4 | `payment_count` | String | Yes | `１` | 今回回数 (Current installment count) |
| Col 5 | `billed_amount` | Numeric | No | `134616`, `10642` | Billed amount in JPY (当月支払額) |
| Col 6 | `note` | String | Yes | `返品` | Note / remarks (備考・メモ) |

### Subtotal and Total Rows
- Col 0 is empty and Col 5 holds the amount. Must be ignored during transaction parsing.

---

## Reformatted Layout (`reformat_visa_rows`)

`finlog.parsers.visa.reformat_visa_rows` flattens the raw rows into one transaction per row. The `Reformatted Credit Card Log` sheet shows this output, and `VisaParser` reads it.

| Column | Source |
| :--- | :--- |
| `source_line` | 1-based line number in the raw CSV (`raw_row_index`) |
| `cardholder`, `card_number`, `card_product` | Section header row of the transaction's section |
| `use_date` .. `note` | Transaction row columns 0-6 |

- Section header, subtotal, and total rows are dropped.
- Rows are sorted by cardholder (in order of first appearance), then by `use_date`.

---

## Parser & Preprocessing Rules

1. **Encoding Handling**: Must read with `cp932` / `shift_jis` and convert output strings to UTF-8.
2. **Line Classification**:
   - Col 0 is empty -> Subtotal or total row; drop it.
   - Col 0 does not start with a digit -> Section header; set the current cardholder, card number, and card product.
   - Otherwise -> Transaction row of the current section.
3. **Card Number**: `card_number_suffix` keeps the unmasked leading groups (`1234-56**`). A card number without hyphens is kept as is.
4. **Account Mapping**: Main member -> `ANA VISA Platinum Unpaid` / `ANA VISA Platinum Paid`. Family member (listed in `finlog.config.FAMILY_CARDHOLDERS`) -> `Yuri ANA VISA Platinum Unpaid`.
5. **Unique ID Assignment**: Prepend unique transaction ID (e.g. `VISA-00001`) in reformatted row order.
