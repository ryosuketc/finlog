from unittest.mock import patch
from click.testing import CliRunner
from finlog.cli import main


def test_cli_credit_visa_local():
    """Test finlog credit subcommand with VISA sample file."""
    runner = CliRunner()
    with patch("finlog.io.sheets_writer.HAS_GSPREAD", False):
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
    with patch("finlog.io.sheets_writer.HAS_GSPREAD", False):
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


def _run_credit_and_capture_sheets(card_path, zaim_path, card_type):
    runner = CliRunner()
    with patch("finlog.cli.SheetsWriter") as writer_cls:
        writer_cls.return_value.write_output.return_value = "ok"
        result = runner.invoke(
            main,
            ["credit", "--log", str(zaim_path), "--log-type", "zaim", "--card", str(card_path), "--card-type", card_type],
        )
    assert result.exit_code == 0, result.output
    return writer_cls.return_value.write_output.call_args.args[1]


ZAIM_LINES = [
    "日付,方法,カテゴリ,カテゴリの内訳,支払元,入金先,品目,メモ,お店,通貨,収入,支出,振替,残高調整,通貨変換前の金額,集計の設定",
]


def test_cli_credit_visa_keeps_raw_rows_and_adds_reformatted_sheet(tmp_path):
    raw_lines = [
        "山田　太郎　様,1234-56**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム",
        "2026/10/03,店舗Ｂ,200,１,１,200,",
        "2026/10/02,店舗Ａ,100,１,１,100,",
        ",,,,,300",
        "山田　花子　様,1234-56**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム",
        "2026/10/01,店舗Ｃ,400,１,１,400,",
        ",,,,,400",
    ]
    card_path = tmp_path / "visa.csv"
    card_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    zaim_path = tmp_path / "zaim.csv"
    zaim_path.write_text("\n".join(ZAIM_LINES) + "\n", encoding="utf-8")

    sheets = _run_credit_and_capture_sheets(card_path, zaim_path, "visa")

    assert list(sheets) == [
        "Raw Credit Card Log",
        "Reformatted Credit Card Log",
        "Raw Zaim Log",
        "Zaim View",
        "Credit View",
    ]
    assert [",".join(r) for r in sheets["Raw Credit Card Log"]] == raw_lines
    reformatted = sheets["Reformatted Credit Card Log"]
    assert reformatted[0][:2] == ["source_line", "cardholder"]
    assert [(r[1], r[4]) for r in reformatted[1:]] == [
        ("山田　太郎　様", "2026/10/02"),
        ("山田　太郎　様", "2026/10/03"),
        ("山田　花子　様", "2026/10/01"),
    ]


def test_cli_credit_amex_reformatted_sheet_matches_raw(tmp_path):
    raw_lines = [
        "ご利用日,データ処理日,ご利用内容,カード会員様名,会員番号 #,金額",
        "2026/06/21,2026/06/21,Amazon,TARO YAMADA,-11111,1000",
        "2026/05/15,2026/05/16,Store A,HANAKO YAMADA,-22222,500",
    ]
    card_path = tmp_path / "amex.csv"
    card_path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    zaim_path = tmp_path / "zaim.csv"
    zaim_path.write_text("\n".join(ZAIM_LINES) + "\n", encoding="utf-8")

    sheets = _run_credit_and_capture_sheets(card_path, zaim_path, "amex")

    assert [",".join(r) for r in sheets["Raw Credit Card Log"]] == raw_lines
    assert sheets["Reformatted Credit Card Log"] == sheets["Raw Credit Card Log"]



CREDIT_VIEW_HEADER = [
    "transaction_id",
    "card_name",
    "cardholder",
    "card_number_suffix",
    "date",
    "amount",
    "payee_merchant",
    "note",
    "match_status",
    "matched_transaction_id",
    "manual_review",
    "manual_fix",
    "manual_note",
]


def test_cli_credit_visa_credit_view_column_order(tmp_path):
    card_path = tmp_path / "visa.csv"
    card_path.write_text(
        "\n".join([
            "山田　太郎　様,1234-56**-****-****,ＡＮＡＶＩＳＡプラチナプレミアム",
            "2026/10/02,店舗Ａ,100,１,１,100,",
            ",,,,,100",
        ]) + "\n",
        encoding="utf-8",
    )
    zaim_path = tmp_path / "zaim.csv"
    zaim_path.write_text("\n".join(ZAIM_LINES) + "\n", encoding="utf-8")

    credit_view = _run_credit_and_capture_sheets(card_path, zaim_path, "visa")["Credit View"]

    assert credit_view == [
        CREDIT_VIEW_HEADER,
        ["VISA-00001", "ANA VISA Platinum", "山田 太郎 様", "1234-56**", "2026-10-02", 100, "店舗A", "", "Unmatched", "", "", "", ""],
    ]


def test_cli_credit_amex_credit_view_column_order(tmp_path):
    card_path = tmp_path / "amex.csv"
    card_path.write_text(
        "\n".join([
            "ご利用日,データ処理日,ご利用内容,カード会員様名,会員番号 #,金額",
            "2026/06/21,2026/06/21,Amazon,TARO YAMADA,-11111,1000",
        ]) + "\n",
        encoding="utf-8",
    )
    zaim_path = tmp_path / "zaim.csv"
    zaim_path.write_text("\n".join(ZAIM_LINES) + "\n", encoding="utf-8")

    credit_view = _run_credit_and_capture_sheets(card_path, zaim_path, "amex")["Credit View"]

    assert credit_view == [
        CREDIT_VIEW_HEADER,
        ["AMEX-00001", "Amex Proper", "TARO YAMADA", "-11111", "2026-06-21", 1000, "Amazon", "", "Unmatched", "", "", "", ""],
    ]


def test_cli_credit_freezes_zaim_and_credit_view_headers(tmp_path):
    card_path = tmp_path / "amex.csv"
    card_path.write_text(
        "ご利用日,データ処理日,ご利用内容,カード会員様名,会員番号 #,金額\n"
        "2026/06/21,2026/06/21,Amazon,TARO YAMADA,-11111,1000\n",
        encoding="utf-8",
    )
    zaim_path = tmp_path / "zaim.csv"
    zaim_path.write_text("\n".join(ZAIM_LINES) + "\n", encoding="utf-8")

    runner = CliRunner()
    with patch("finlog.cli.SheetsWriter") as writer_cls:
        writer_cls.return_value.write_output.return_value = "ok"
        result = runner.invoke(
            main,
            ["credit", "--log", str(zaim_path), "--log-type", "zaim", "--card", str(card_path), "--card-type", "amex"],
        )

    assert result.exit_code == 0, result.output
    kwargs = writer_cls.return_value.write_output.call_args.kwargs
    assert kwargs["frozen_header_sheets"] == {"Zaim View", "Credit View"}
