import pytest
from finlog.parsers.visa import VISA_REFORMATTED_HEADER, VisaParser, reformat_visa_rows


MULTI_SECTION_LINES = [
    "山田　太郎　様,1234-56**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム",
    "2026/10/03,店舗Ｂ,200,１,１,200,",
    "2026/10/02,店舗Ａ,100,１,１,100,",
    "山田　太郎　様,9999-11**-****-****,ＧｏｏｇｌｅＰａｙ／ｉＤ",
    "2026/10/01,店舗Ｃ／ｉＤ,300,１,１,300,",
    ",,,,,600",
    "山田　花子　様,1234-56**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム",
    "2026/10/05,店舗Ｄ,400,１,１,400,メモ",
    ",,,,,400",
    ",,,,,1000,",
]


def test_visa_parser_sample_lines():
    """Test parsing sample ANA VISA CSV lines."""
    lines = [
        "山田　太郎　様,1234-56**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム",
        "2026/05/16,フルナビマネー,134616,１,１,134616,",
        "2026/05/20,焼肉きんぐ三鷹野崎店,10642,１,１,10642,",
        "2026/06/15,府中運転免許試験場／ｉＤ,3450,１,１,3450,",
        ",,,,,863014,",
    ]

    parser = VisaParser()
    transactions = parser.parse(lines)

    assert len(transactions) == 3

    t1 = transactions[0]
    assert t1.transaction_id == "VISA-00001"
    assert t1.card_name == "ANA VISA Platinum"
    assert t1.cardholder == "山田 太郎 様"
    assert t1.card_number_suffix == "1234-56**"
    assert t1.date.strftime("%Y-%m-%d") == "2026-05-16"
    assert t1.payee_merchant == "フルナビマネー"
    assert t1.amount == 134616
    assert t1.raw_row_index == 2

    t3 = transactions[2]
    assert t3.transaction_id == "VISA-00003"
    assert t3.payee_merchant == "府中運転免許試験場/iD"
    assert t3.amount == 3450
    assert t3.raw_row_index == 4



def test_reformat_visa_rows_flattens_sections_and_sorts_by_holder_then_date():
    rows = [line.split(",") for line in MULTI_SECTION_LINES]

    reformatted = reformat_visa_rows(rows)

    assert reformatted[0] == [
        "source_line", "cardholder", "card_number", "card_product",
        "use_date", "merchant", "amount", "payment_type", "payment_count", "billed_amount", "note",
    ]
    assert [(r[0], r[1], r[4]) for r in reformatted[1:]] == [
        ("5", "山田　太郎　様", "2026/10/01"),
        ("3", "山田　太郎　様", "2026/10/02"),
        ("2", "山田　太郎　様", "2026/10/03"),
        ("8", "山田　花子　様", "2026/10/05"),
    ]
    assert reformatted[1][2:4] == ["9999-11**-****-****", "ＧｏｏｇｌｅＰａｙ／ｉＤ"]
    assert reformatted[4][-1] == "メモ"


def test_reformat_visa_rows_empty_returns_header_only():
    assert reformat_visa_rows([]) == [VISA_REFORMATTED_HEADER]


def test_visa_parser_multi_section_sets_holder_per_section():
    transactions = VisaParser().parse(MULTI_SECTION_LINES)

    assert [(t.cardholder, t.card_number_suffix, t.amount, t.raw_row_index) for t in transactions] == [
        ("山田 太郎 様", "9999-11**", 300, 5),
        ("山田 太郎 様", "1234-56**", 100, 3),
        ("山田 太郎 様", "1234-56**", 200, 2),
        ("山田 花子 様", "1234-56**", 400, 8),
    ]
    assert transactions[3].note == "メモ"


def test_visa_parser_card_number_without_hyphen():
    lines = ["山田　太郎　様,1234,ＡＮＡＶＩＳＡ", "2026/10/01,店舗,100,１,１,100,"]

    transactions = VisaParser().parse(lines)

    assert transactions[0].card_number_suffix == "1234"
