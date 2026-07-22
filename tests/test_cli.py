from click.testing import CliRunner
from finlog.cli import main, sort_raw_card_rows


def test_cli_credit_visa_local():
    """Test finlog credit subcommand with VISA sample file."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "credit",
            "--log",
            "user_data/credit_sample/Zaim.20260720044643.csv",
            "--log-type",
            "zaim",
            "--card",
            "user_data/credit_sample/visa_202607.csv",
            "--card-type",
            "visa",
        ],
    )

    assert result.exit_code == 0
    assert "finlog credit" in result.output
    assert "VISA" in result.output


def test_cli_credit_amex_local():
    """Test finlog credit subcommand with AMEX sample file."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "credit",
            "--log",
            "user_data/credit_sample/Zaim.20260720044643.csv",
            "--log-type",
            "zaim",
            "--card",
            "user_data/credit_sample/amex_2026-06-21.csv",
            "--card-type",
            "amex",
        ],
    )

    assert result.exit_code == 0
    assert "finlog credit" in result.output
    assert "AMEX" in result.output


def test_sort_raw_card_rows_desc_input():
    """Test sorting raw card CSV rows into ASC order by date while preserving headers and footers."""
    rows = [
        ["ご利用日", "データ処理日", "ご利用内容", "金額"],
        ["2026/06/21", "2026/06/21", "Amazon", "1000"],
        ["2026/06/20", "2026/06/21", "Store B", "2000"],
        ["2026/05/15", "2026/05/16", "Store A", "500"],
        ["", "", "", "3500"],
    ]

    sorted_rows = sort_raw_card_rows(rows)

    assert sorted_rows[0] == ["ご利用日", "データ処理日", "ご利用内容", "金額"]
    assert sorted_rows[1][0] == "2026/05/15"
    assert sorted_rows[2][0] == "2026/06/20"
    assert sorted_rows[3][0] == "2026/06/21"
    assert sorted_rows[4] == ["", "", "", "3500"]

