import csv
import datetime

import pytest

from finlog.tax.iryohi import (
    FORM_HEADER,
    IryohiInputError,
    annotate,
    build_shukei_form,
    form_table,
    read_iryohi_raw,
    read_suggestions,
)

# Column order of the iryohi_raw tab produced by the finlog.iryouhi BigQuery query.
RAW_HEADER = [
    "iryouhikoujo_type", "iryouhikoujo_type_detail", "year", "iryouhikoujo_person", "iryouhikoujo_payee",
    "is_type_shinryo", "is_type_iyakuhin", "is_type_kaigo", "is_type_other", "iryouhikoujo_amount",
    "iryouhikoujo_refund", "iryouhikoujo_date", "finlog_payee", "finlog_amount", "transport_payee",
    "transport_amount_round", "finlog_category", "finlog_subcategory", "finlog_tag_raw", "finlog_note",
    "finlog_item", "transport_note", "transport_link", "include", "justificaton", "receipt", "need_data_fix", "note",
]

CLINIC = {
    "iryouhikoujo_type": "医療費・医薬品", "iryouhikoujo_type_detail": "診療・治療", "year": "2025",
    "iryouhikoujo_person": "患者 一郎", "iryouhikoujo_payee": "さくら内科", "is_type_shinryo": "該当する",
    "iryouhikoujo_amount": "2180", "iryouhikoujo_refund": "0", "iryouhikoujo_date": "2025-01-06",
    "finlog_item": "血液検査", "include": "1", "receipt": "1",
}
PHARMACY = {
    "iryouhikoujo_type": "医療費・医薬品", "iryouhikoujo_type_detail": "医薬品購入", "year": "2025",
    "iryouhikoujo_person": "患者 花子", "iryouhikoujo_payee": "みどり薬局", "is_type_iyakuhin": "該当する",
    "iryouhikoujo_amount": "1,950", "iryouhikoujo_refund": "0", "iryouhikoujo_date": "2025/01/20",
    "finlog_item": "漢方薬", "include": "TRUE", "receipt": "DIGITAL - Y",
}
BUS = {
    "iryouhikoujo_type": "交通費", "iryouhikoujo_type_detail": "その他の医療費", "year": "2025",
    "iryouhikoujo_person": "患者 花子", "iryouhikoujo_payee": "小田急バス", "is_type_other": "該当する",
    "iryouhikoujo_amount": "920", "iryouhikoujo_refund": "0", "iryouhikoujo_date": "2025-01-21",
    "include": "1",
}
SUPPLEMENT = {
    "iryouhikoujo_type": "医療費・医薬品", "iryouhikoujo_type_detail": "Invalid", "year": "2025",
    "iryouhikoujo_person": "患者 花子", "iryouhikoujo_payee": "Amazon", "iryouhikoujo_amount": "1780",
    "iryouhikoujo_refund": "0", "iryouhikoujo_date": "2025-01-16", "finlog_item": "亜鉛サプリ", "include": "0",
}


def write_raw_csv(tmp_path, rows, header=RAW_HEADER):
    path = tmp_path / "iryohi_raw.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_suggestions_csv(tmp_path, text):
    path = tmp_path / "suggestions.csv"
    path.write_text(text, encoding="utf-8")
    return path


# read_iryohi_raw


def test_read_iryohi_raw_numbers_rows_like_the_sheet(tmp_path):
    path = write_raw_csv(tmp_path, [CLINIC, SUPPLEMENT])

    header, rows = read_iryohi_raw(path)

    assert header == RAW_HEADER
    assert [r.sheet_row for r in rows] == [2, 3]
    assert rows[1].values["iryouhikoujo_payee"] == "Amazon"


def test_read_iryohi_raw_keeps_multiline_cells(tmp_path):
    path = write_raw_csv(tmp_path, [dict(CLINIC, finlog_item="クラシエ薬品\n八味地黄丸"), SUPPLEMENT])

    _, rows = read_iryohi_raw(path)

    assert [r.sheet_row for r in rows] == [2, 3]
    assert rows[0].values["finlog_item"] == "クラシエ薬品\n八味地黄丸"


def test_read_iryohi_raw_rejects_missing_column(tmp_path):
    header = [h for h in RAW_HEADER if h != "include"]
    path = write_raw_csv(tmp_path, [CLINIC], header=header)

    with pytest.raises(IryohiInputError, match="missing columns: include"):
        read_iryohi_raw(path)


# build_shukei_form


def test_build_shukei_form_keeps_included_rows_and_sums_amounts(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [CLINIC, SUPPLEMENT, PHARMACY, BUS]))

    form = build_shukei_form(rows)

    assert [(r.sheet_row, r.payee, r.amount) for r in form.rows] == [
        (2, "さくら内科", 2180),
        (4, "みどり薬局", 1950),
        (5, "小田急バス", 920),
    ]
    assert form.total_amount == 5050
    assert form.total_refund == 0
    assert form.findings == []


def test_build_shukei_form_maps_categories_and_dates(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [CLINIC, PHARMACY, BUS]))

    form = build_shukei_form(rows)

    assert [(r.shinryo, r.iyakuhin, r.kaigo, r.other) for r in form.rows] == [
        (True, False, False, False),
        (False, True, False, False),
        (False, False, False, True),
    ]
    assert form.rows[1].date == datetime.date(2025, 1, 20)


@pytest.mark.parametrize("include", ["0", "FALSE", "false", ""])
def test_build_shukei_form_skips_not_included_values(tmp_path, include):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [dict(CLINIC, include=include)]))

    assert build_shukei_form(rows).rows == []


def test_build_shukei_form_flags_unexpected_category_value_and_drops_it(tmp_path):
    shifted = dict(BUS, iryouhikoujo_payee="ひまわり歯科", is_type_shinryo="電車")
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [shifted]))

    form = build_shukei_form(rows)

    assert form.rows[0].shinryo is False
    assert [(f.sheet_row, f.message) for f in form.findings] == [
        (2, "is_type_shinryo is '電車', expected 該当する or empty; left empty in the form"),
    ]


def test_build_shukei_form_flags_row_without_category(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [dict(PHARMACY, is_type_iyakuhin="")]))

    form = build_shukei_form(rows)

    assert [f.message for f in form.findings] == ["no 医療費の区分 is selected"]


def test_build_shukei_form_flags_names_longer_than_the_form_allows(tmp_path):
    long_names = dict(CLINIC, iryouhikoujo_person="患者" * 6, iryouhikoujo_payee="あ" * 21)
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [long_names]))

    form = build_shukei_form(rows)

    assert [f.message for f in form.findings] == [
        "医療を受けた人 has 12 characters, the form allows 10",
        "病院・薬局などの名称 has 21 characters, the form allows 20",
    ]


@pytest.mark.parametrize("receipt", ["", "0", "FALSE"])
def test_build_shukei_form_flags_missing_receipt_except_transport(tmp_path, receipt):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [dict(CLINIC, receipt=receipt), dict(BUS, receipt=receipt)]))

    form = build_shukei_form(rows)

    assert [(f.sheet_row, f.message) for f in form.findings] == [(2, "no receipt")]


def test_build_shukei_form_flags_refund_larger_than_amount(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [dict(CLINIC, iryouhikoujo_refund="3000")]))

    form = build_shukei_form(rows)

    assert form.total_refund == 3000
    assert [f.message for f in form.findings] == ["refund 3000 is larger than the amount 2180"]


def test_build_shukei_form_flags_need_data_fix(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [dict(CLINIC, need_data_fix="1")]))

    assert [f.message for f in build_shukei_form(rows).findings] == ["need_data_fix is set"]


def test_build_shukei_form_rejects_bad_amount_on_included_row(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [SUPPLEMENT, dict(CLINIC, iryouhikoujo_amount="12.5")]))

    with pytest.raises(IryohiInputError, match="row 3: iryouhikoujo_amount '12.5' is not a whole yen amount"):
        build_shukei_form(rows)


def test_form_table_matches_the_official_form_columns(tmp_path):
    _, rows = read_iryohi_raw(write_raw_csv(tmp_path, [CLINIC, BUS]))

    table = form_table(build_shukei_form(rows))

    assert table[0] == FORM_HEADER
    assert table[1:] == [
        ["患者 一郎", "さくら内科", "該当する", "", "", "", 2180, 0, "2025-01-06"],
        ["患者 花子", "小田急バス", "", "", "", "該当する", 920, 0, "2025-01-21"],
    ]


# annotate


def test_annotate_adds_suggestions_and_flags_rows_to_check(tmp_path):
    header, rows = read_iryohi_raw(write_raw_csv(tmp_path, [CLINIC, SUPPLEMENT, PHARMACY, BUS]))
    suggestions = read_suggestions(
        write_suggestions_csv(
            tmp_path,
            "row,payee,amount,suggestion,reason\n"
            "2,さくら内科,2180,include,診療\n"
            "3,Amazon,1780,include,サプリでも治療目的なら\n"
            "4,みどり薬局,\"1,950\",unsure,漢方の目的が不明\n",
        )
    )

    out_header, out_rows, stats = annotate(header, rows, suggestions)

    assert out_header == RAW_HEADER + ["llm_suggestion", "llm_reason", "llm_flag"]
    assert [r[-3:] for r in out_rows] == [
        ["include", "診療", ""],
        ["include", "サプリでも治療目的なら", "1"],
        ["unsure", "漢方の目的が不明", "1"],
        ["", "", ""],
    ]
    assert out_rows[0][: len(RAW_HEADER)] == [CLINIC.get(h, "") for h in RAW_HEADER]
    assert (stats.agree, stats.disagree, stats.unsure, stats.missing) == (1, 1, 1, 1)


def test_annotate_rejects_suggestion_for_a_different_row(tmp_path):
    header, rows = read_iryohi_raw(write_raw_csv(tmp_path, [CLINIC, SUPPLEMENT]))
    suggestions = read_suggestions(
        write_suggestions_csv(tmp_path, "row,payee,amount,suggestion,reason\n2,Amazon,1780,exclude,サプリ\n")
    )

    with pytest.raises(IryohiInputError, match="row 2: suggestion is for Amazon 1780, but the row is さくら内科 2180"):
        annotate(header, rows, suggestions)


def test_annotate_rejects_unknown_row(tmp_path):
    header, rows = read_iryohi_raw(write_raw_csv(tmp_path, [CLINIC]))
    suggestions = read_suggestions(
        write_suggestions_csv(tmp_path, "row,payee,amount,suggestion,reason\n3,Amazon,1780,exclude,サプリ\n")
    )

    with pytest.raises(IryohiInputError, match="row 3: no such row in iryohi_raw"):
        annotate(header, rows, suggestions)


def test_read_suggestions_rejects_duplicate_rows(tmp_path):
    path = write_suggestions_csv(
        tmp_path, "row,payee,amount,suggestion,reason\n2,さくら内科,2180,include,a\n2,さくら内科,2180,exclude,b\n"
    )

    with pytest.raises(IryohiInputError, match="row 2: more than one suggestion"):
        read_suggestions(path)


def test_read_suggestions_rejects_unknown_suggestion(tmp_path):
    path = write_suggestions_csv(tmp_path, "row,payee,amount,suggestion,reason\n2,さくら内科,2180,maybe,a\n")

    with pytest.raises(IryohiInputError, match="row 2: suggestion 'maybe' must be include, exclude, or unsure"):
        read_suggestions(path)
