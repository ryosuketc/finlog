# 医療費控除: review and export

This page covers the yearly 医療費控除 flow with `finlog tax iryohi`, and the rules an LLM reviewer (a Jetski session) follows when it suggests which rows to include.

## Workflow

1. **Build iryohi_raw (manual for now)**: Download the Zaim data, paste it into the FinLog raw_Zaim sheet, run the `finlog.merge` saved query, update the iryouhi transport database, run the `finlog.iryouhi` saved query, and export the result to the `iryohi_raw` tab of the 確定申告 sheet. Automating this is on the [ROADMAP](../../ROADMAP.md).
2. **Download iryohi_raw as CSV**: File > Download > CSV, for example to `user_data/tax/2026/iryohi_raw.csv`.
3. **LLM review (optional)**: In Jetski, ask for a review of that CSV with this page. The reviewer writes `user_data/tax/2026/iryohi_suggestions.csv` in the format below.
4. **Annotate**: `finlog tax iryohi annotate --input <iryohi_raw.csv> --suggestions <suggestions.csv>` writes a review spreadsheet. It adds `llm_suggestion`, `llm_reason`, and `llm_flag`, and highlights rows where `llm_flag` is 1 (the suggestion is unsure or disagrees with `include`).
5. **Human review**: Set `include` and `receipt` in the sheet. The suggestions never change `include`.
6. **Export**: Download the reviewed sheet as CSV and run `finlog tax iryohi export --input <reviewed.csv>`. It writes the 医療費集計フォーム rows (paste them at cell B9 of the official form; column A is a formula) and a Checks tab.

## What export checks

Export keeps rows whose `include` is 1 or TRUE. It reports, per sheet row:

- A category column (`is_type_*`) with a value other than 該当する or empty. The value is left empty in the form.
- No category selected.
- 医療を受けた人 longer than 10 characters, or 病院・薬局などの名称 longer than 20 characters (the form limits).
- No receipt (`receipt` empty, 0, or FALSE) on a row that is not 交通費.
- A refund larger than the amount, `need_data_fix` set, or a `year` that differs from most rows.

It stops with an error when a required column is missing, or when an included row has an amount that is not a whole yen value or a date it cannot read.

## Suggestions file

CSV with a header row. One line per reviewed row:

| Column | Meaning |
| :-- | :-- |
| `row` | Sheet row number (the header is row 1) |
| `payee` | `iryouhikoujo_payee` of that row, copied as is |
| `amount` | `iryouhikoujo_amount` of that row |
| `suggestion` | `include`, `exclude`, or `unsure` |
| `reason` | One short sentence, in Japanese is fine |

`annotate` stops when `payee` and `amount` do not match the row, so a shifted or different sheet cannot be annotated by mistake. Rows without a suggestion are left blank.

## Review rules

Judge each row from `iryouhikoujo_type`, `iryouhikoujo_payee`, `finlog_item`, `finlog_note`, `finlog_subcategory`, and `transport_*`. Use `unsure` whenever the purpose is not clear from the row; a person decides those rows.

The basis is National Tax Agency guidance (No.1120 医療費を支払ったとき, No.1122 医療費控除の対象となる医療費). The notes in the 確定申告 sheet README come from past calls to the tax office.

### Include

- Fees for medical examination and treatment (診療・治療) at clinics, hospitals, and dentists, including dental implants.
- Medicine bought for treatment, including over-the-counter medicine and 漢方 used to treat a condition.
- Public transport to and from a clinic for treatment, including a parent who has to go with a child. Taxi only in an emergency or when public transport is not practical.
- Rehabilitation and developmental therapy done under a doctor's supervision with a plan. A reservation fee counts when the treatment cannot happen without it.
- A referral letter (紹介状) when it is needed for treatment.
- Massage, acupuncture, or moxibustion (あんま・はり・きゅう) by a licensed practitioner for treatment.

### Exclude

- Vaccinations and other prevention.
- Health checkups and routine dental checkups when nothing is found that needs treatment (定期検診). Scaling and cleaning (歯石除去) for upkeep.
- Contact lenses and glasses that are not part of treatment.
- Supplements, vitamins, and health food for general health.
- Medical certificates and other document fees (診断書).
- Maternity classes, prenatal diagnosis, and the extra charge for a private hospital room (差額ベッド代) chosen for comfort.
- Transport by own car (fuel, parking), and transport for a visit that is itself excluded.

### Unsure

- Dental checkups or cleaning that may be implant maintenance.
- Products bought online (for example on Amazon) when the item name does not show a medical use.
- Any row where the patient, purpose, or link to a treatment is unclear.
