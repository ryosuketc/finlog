import datetime
from finlog.models.transaction import CreditCardTransaction, FinanceLogTransaction


def test_credit_card_transaction_creation_and_to_dict():
    """Test creating CreditCardTransaction and converting to dictionary."""
    t = CreditCardTransaction(
        transaction_id="VISA-00001",
        card_company="ANA VISA Platinum",
        date=datetime.date(2026, 5, 16),
        amount=134616,
        payee_merchant="フルナビマネー",
        cardholder="山田 太郎",
        card_number_suffix="1234-56**",
        note="",
        raw_row_index=2,
    )

    assert t.transaction_id == "VISA-00001"
    assert t.card_company == "ANA VISA Platinum"
    assert t.amount == 134616
    assert t.date == datetime.date(2026, 5, 16)

    d = t.to_dict()
    assert d["transaction_id"] == "VISA-00001"
    assert d["card_company"] == "ANA VISA Platinum"
    assert d["amount"] == 134616
    assert d["date"] == "2026-05-16"
    assert d["payee_merchant"] == "フルナビマネー"


def test_finance_log_transaction_creation_and_to_dict():
    """Test creating FinanceLogTransaction and converting to dictionary."""
    t = FinanceLogTransaction(
        transaction_id="ZAIM-00001",
        platform="Zaim",
        type="expense",
        date=datetime.date(2026, 5, 20),
        year="2026",
        month="2026-05",
        account="Amex Proper Paid",
        amount=10399,
        currencycode="JPY",
        category="教育・教養",
        subcategory="子ども関連",
        item="Apitor Robot",
        payee_payer="Amazon",
        tag_raw=" #ichika",
        tag_mod="ichika",
        note="",
    )

    assert t.transaction_id == "ZAIM-00001"
    assert t.platform == "Zaim"
    assert t.type == "expense"
    assert t.amount == 10399

    d = t.to_dict()
    assert d["transaction_id"] == "ZAIM-00001"
    assert d["account"] == "Amex Proper Paid"
    assert d["amount"] == 10399
    assert d["tag_mod"] == "ichika"
