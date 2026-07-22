import datetime
import pytest
from finlog.models.transaction import CreditCardTransaction, FinanceLogTransaction
from finlog.matching.strategies.contains_strategy import SimpleContainsStrategy
from finlog.matching.engine import ReconciliationEngine


def test_simple_contains_strategy():
    """Test text similarity algorithm in SimpleContainsStrategy."""
    strategy = SimpleContainsStrategy()

    # Substring containment & Alias mapping
    assert strategy.similarity("マクドナルド 三鷹店", "マクドナルド") == 1.0
    assert strategy.similarity("アマゾン JP マーケットプレイス", "アマゾン") == 1.0
    assert strategy.similarity("アマゾン シーオージェーピー", "Amazon") == 1.0
    assert strategy.similarity("アマゾンサービシーズインターナショナル", "Amazon") == 1.0
    assert strategy.similarity("ヨドバシカメラ 通信販売 ?東京都 新", "yodobashi.com") == 1.0
    assert strategy.similarity("イオンネクスト ?千葉県 千葉市", "Green Beans") == 1.0
    assert strategy.similarity("フォトクリエイト スナップスナップ 東", "snap snap") == 1.0
    assert strategy.similarity("YONDEMY", "ヨンデミー") == 1.0
    assert strategy.similarity("モスのネット注文 東京都 品川区", "モスバーガー") == 1.0




    # High similarity
    assert strategy.similarity("焼肉きんぐ三鷹野崎店", "焼肉きんぐ 三鷹新川店") >= 0.5

    # Completely different
    assert strategy.similarity("セブンイレブン", "成城石井") < 0.3


def test_reconciliation_engine_matching():
    """Test matching card transactions against Zaim transactions."""
    card_txs = [
        CreditCardTransaction(
            transaction_id="VISA-00001",
            card_company="ANA VISA Platinum",
            date=datetime.date(2026, 5, 20),
            amount=10642,
            payee_merchant="焼肉きんぐ三鷹野崎店",
            raw_row_index=2,
        ),
        CreditCardTransaction(
            transaction_id="VISA-00002",
            card_company="ANA VISA Platinum",
            date=datetime.date(2026, 5, 25),
            amount=5000,
            payee_merchant="未入力カード利用",
            raw_row_index=3,
        ),
    ]

    zaim_txs = [
        FinanceLogTransaction(
            transaction_id="ZAIM-00001",
            platform="Zaim",
            type="expense",
            date=datetime.date(2026, 5, 20),
            year="2026",
            month="2026-05",
            account="ANA VISA Platinum Unpaid",
            amount=10642,
            payee_payer="焼肉きんぐ 三鷹新川店",
        ),
        FinanceLogTransaction(
            transaction_id="ZAIM-00002",
            platform="Zaim",
            type="expense",
            date=datetime.date(2026, 7, 10),
            year="2026",
            month="2026-07",
            account="ANA VISA Platinum Unpaid",
            amount=1000,
            payee_payer="期間外Zaimログ",
        ),
        FinanceLogTransaction(
            transaction_id="ZAIM-00003",
            platform="Zaim",
            type="expense",
            date=datetime.date(2026, 5, 20),
            year="2026",
            month="2026-05",
            account="ANA VISA Platinum Paid",
            amount=10642,
            payee_payer="焼肉きんぐ 三鷹新川店",
        ),
    ]

    # Test with unpaid_only=True (default)
    engine_unpaid = ReconciliationEngine(similarity_strategy=SimpleContainsStrategy(), date_tolerance_days=5, unpaid_only=True)
    result_unpaid = engine_unpaid.reconcile(card_transactions=card_txs, zaim_transactions=zaim_txs)

    assert len(result_unpaid.matched_pairs) == 1
    assert result_unpaid.matched_pairs[0].zaim_tx.transaction_id == "ZAIM-00001"

    # Test with unpaid_only=False (all accounts)
    engine_all = ReconciliationEngine(similarity_strategy=SimpleContainsStrategy(), date_tolerance_days=5, unpaid_only=False)
    result_all = engine_all.reconcile(card_transactions=card_txs, zaim_transactions=zaim_txs)

    assert len(result_all.matched_pairs) == 1
    assert result_all.matched_pairs[0].zaim_tx.transaction_id == "ZAIM-00001"


def test_get_card_accounts():
    from finlog.matching.engine import get_card_accounts

    # VISA
    assert get_card_accounts("ANA VISA Platinum", unpaid_only=True) == ["ANA VISA Platinum Unpaid"]
    assert get_card_accounts("ANA VISA Platinum", unpaid_only=False) == ["ANA VISA Platinum Unpaid", "ANA VISA Platinum Paid"]

    # AMEX
    assert get_card_accounts("Amex Proper", unpaid_only=True) == ["Amex Proper Unpaid", "Yuri Amex Proper Unpaid"]
    assert get_card_accounts("Amex Proper", unpaid_only=False) == ["Amex Proper Unpaid", "Yuri Amex Proper Unpaid", "Amex Proper Paid"]

    # Unknown
    assert get_card_accounts("Unknown Card") == []


def test_reconciliation_engine_credit_view_cardholder_and_date_sort():
    """Test that credit_view_entries are returned sorted by cardholder first, then date in ASC order."""
    card_txs = [
        CreditCardTransaction(
            transaction_id="AMEX-00001",
            card_company="Amex Proper",
            date=datetime.date(2026, 6, 21),
            amount=1000,
            payee_merchant="Store C",
            cardholder="TARO YAMADA",
        ),
        CreditCardTransaction(
            transaction_id="AMEX-00002",
            card_company="Amex Proper",
            date=datetime.date(2026, 6, 19),
            amount=2000,
            payee_merchant="Store B",
            cardholder="HANAKO YAMADA",
        ),
        CreditCardTransaction(
            transaction_id="AMEX-00003",
            card_company="Amex Proper",
            date=datetime.date(2026, 6, 15),
            amount=500,
            payee_merchant="Store A",
            cardholder="TARO YAMADA",
        ),
    ]

    engine = ReconciliationEngine()
    result = engine.reconcile(card_transactions=card_txs, zaim_transactions=[])

    sorted_pairs = [(entry["cardholder"], entry["date"]) for entry in result.credit_view_entries]
    assert sorted_pairs == [
        ("HANAKO YAMADA", "2026-06-19"),
        ("TARO YAMADA", "2026-06-15"),
        ("TARO YAMADA", "2026-06-21"),
    ]


def test_reconciliation_engine_bundled_matching():
    """Test Phase 2 bundled N:1 matching where multiple Zaim transactions match a single card transaction."""
    card_txs = [
        CreditCardTransaction(
            transaction_id="VISA-00001",
            card_company="ANA VISA Platinum",
            date=datetime.date(2026, 7, 14),
            amount=300,
            payee_merchant="モスのネット注文 東京都 品川区",
            raw_row_index=1,
        )
    ]

    zaim_txs = [
        FinanceLogTransaction(
            transaction_id="ZAIM-00001",
            platform="Zaim",
            type="expense",
            date=datetime.date(2026, 7, 14),
            year="2026",
            month="2026-07",
            account="ANA VISA Platinum Unpaid",
            amount=100,
            payee_payer="モスバーガー",
        ),
        FinanceLogTransaction(
            transaction_id="ZAIM-00002",
            platform="Zaim",
            type="expense",
            date=datetime.date(2026, 7, 14),
            year="2026",
            month="2026-07",
            account="ANA VISA Platinum Unpaid",
            amount=200,
            payee_payer="モスバーガー",
        ),
    ]

    engine = ReconciliationEngine(unpaid_only=True)
    result = engine.reconcile(card_transactions=card_txs, zaim_transactions=zaim_txs)

    # Check Credit View
    credit_entry = result.credit_view_entries[0]
    assert credit_entry["match_status"] == "Matched (Bundled)"
    assert credit_entry["matched_transaction_id"] == "ZAIM-00001, ZAIM-00002"

    # Check Zaim View
    z1 = next(z for z in result.zaim_view_entries if z["transaction_id"] == "ZAIM-00001")
    z2 = next(z for z in result.zaim_view_entries if z["transaction_id"] == "ZAIM-00002")

    assert z1["match_status"] == "Matched (Bundled)"
    assert z1["matched_transaction_id"] == "VISA-00001"
    assert z2["match_status"] == "Matched (Bundled)"
    assert z2["matched_transaction_id"] == "VISA-00001"



