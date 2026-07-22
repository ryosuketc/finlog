import pytest
from finlog.parsers.visa import VisaParser


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
    assert t1.card_company == "ANA VISA Platinum"
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
