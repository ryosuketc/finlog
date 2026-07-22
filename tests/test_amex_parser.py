import pytest
from finlog.parsers.amex import AmexParser


def test_amex_parser_basic_sample_lines():
    """Test parsing sample Amex CSV lines."""
    lines = [
        "ご利用日,データ処理日,ご利用内容,カード会員様名,会員番号 #,金額,海外通貨利用金額,換算レート",
        '2026/06/21,2026/06/21,アマゾン　ＪＰ　マーケットプレイス　　,TARO YAMADA,-12345,"16,746",,',
        "2026/06/20,2026/06/21,アマゾン　ＪＰ　マーケットプレイス　　,TARO YAMADA,-12345,799,,",
        '2026/06/19,2026/06/21,イトーヨーカドー　専門店　　　　　　　　,HANAKO YAMADA,-67890,"2,332",,',
    ]

    parser = AmexParser()
    transactions = parser.parse(lines)

    assert len(transactions) == 3

    t1 = transactions[0]
    assert t1.transaction_id == "AMEX-00001"
    assert t1.card_company == "Amex Proper"
    assert t1.date.strftime("%Y-%m-%d") == "2026-06-21"
    assert t1.payee_merchant == "アマゾン JP マーケットプレイス"
    assert t1.cardholder == "TARO YAMADA"
    assert t1.card_number_suffix == "-12345"
    assert t1.amount == 16746
    assert t1.raw_row_index == 2

    t3 = transactions[2]
    assert t3.transaction_id == "AMEX-00003"
    assert t3.cardholder == "HANAKO YAMADA"
    assert t3.card_number_suffix == "-67890"
    assert t3.amount == 2332
