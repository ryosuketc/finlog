import pytest
from finlog.parsers.zaim import ZaimParser


def test_zaim_parser_basic_sample_lines():
    """Test parsing sample Zaim CSV lines."""
    lines = [
        "日付,方法,カテゴリ,カテゴリの内訳,支払元,入金先,品目,メモ,お店,通貨,収入,支出,振替,残高調整,通貨変換前の金額,集計の設定",
        '2026-05-20,payment,車,駐車場,現金,-,,#share,多摩駅前パーキング,JPY,0,200,0,0,200,常に集計に含める',
        '2026-05-20,payment,食費,夕食,"ANA VISA Platinum Paid",-,,#share,"焼肉きんぐ 三鷹新川店",JPY,0,10642,0,0,10642,常に集計に含める',
        '2026-05-20,payment,教育・教養,子ども関連,"Amex Proper Paid",-,"Apitor Robot"," #ichika",Amazon,JPY,0,10399,0,0,10399,常に集計に含める',
        '2026-05-21,payment,その他,会費,"Amex Proper Unpaid",-,,#ryosuke#input,"American Express",JPY,0,31900,0,0,31900,常に集計に含める',
    ]

    parser = ZaimParser()
    transactions = parser.parse(lines)

    assert len(transactions) == 4

    # Row 1 (焼肉きんぐ)
    t1 = transactions[1]
    assert t1.transaction_id == "ZAIM-00002"
    assert t1.platform == "Zaim"
    assert t1.type == "expense"
    assert t1.date.strftime("%Y-%m-%d") == "2026-05-20"
    assert t1.account == "ANA VISA Platinum Paid"
    assert t1.amount == 10642
    assert t1.category == "食費"
    assert t1.subcategory == "夕食"
    assert t1.payee_payer == "焼肉きんぐ 三鷹新川店"
    assert t1.tag_mod == "Neither ichika/yuri/ryosuke"

    # Row 2 (Apitor Robot)
    t2 = transactions[2]
    assert t2.account == "Amex Proper Paid"
    assert t2.amount == 10399
    assert t2.tag_mod == "ichika"

    # Row 3 (Amex Proper Unpaid)
    t3 = transactions[3]
    assert t3.account == "Amex Proper Unpaid"
    assert t3.amount == 31900
    assert t3.tag_mod == "ryosuke"
