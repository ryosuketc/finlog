import csv

import pytest
from click.testing import CliRunner

from finlog import cli
from finlog.cli import main

HEADER = [
    "iryouhikoujo_type", "year", "iryouhikoujo_person", "iryouhikoujo_payee", "is_type_shinryo",
    "is_type_iyakuhin", "is_type_kaigo", "is_type_other", "iryouhikoujo_amount", "iryouhikoujo_refund",
    "iryouhikoujo_date", "include", "receipt", "need_data_fix",
]
ROWS = [
    ["医療費・医薬品", "2025", "患者 一郎", "さくら内科", "該当する", "", "", "", "2180", "0", "2025-01-06", "1", "1", ""],
    ["医療費・医薬品", "2025", "患者 花子", "Amazon", "", "", "", "", "1780", "0", "2025-01-16", "0", "", ""],
    ["交通費", "2025", "患者 花子", "小田急バス", "", "", "", "該当する", "920", "0", "2025-01-21", "1", "", ""],
    ["医療費・医薬品", "2025", "患者 花子", "みどり薬局", "", "該当する", "", "", "1950", "0", "2025-01-20", "1", "", ""],
]


class FakeSheetsWriter:
    """Records what the CLI would write instead of calling Google Sheets."""

    calls = []

    def write_output(self, title, sheets_data, **kwargs):
        FakeSheetsWriter.calls.append({"title": title, "sheets_data": sheets_data, **kwargs})
        return "Output written (fake)"


@pytest.fixture
def fake_writer(monkeypatch):
    FakeSheetsWriter.calls = []
    monkeypatch.setattr(cli, "SheetsWriter", FakeSheetsWriter)
    return FakeSheetsWriter


@pytest.fixture
def raw_csv(tmp_path):
    path = tmp_path / "iryohi_raw.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(ROWS)
    return path


def test_iryohi_export_writes_form_rows_and_checks(raw_csv, fake_writer):
    result = CliRunner().invoke(main, ["tax", "iryohi", "export", "--input", str(raw_csv)])

    assert result.exit_code == 0, result.output
    assert "Form rows: 3" in result.output
    assert "Total paid (支払った医療費の金額): ¥5,050" in result.output
    assert "Checks: 1 (see the Checks tab)" in result.output
    assert "row 5: no receipt" in result.output

    call = fake_writer.calls[0]
    assert call["title"].startswith("finlog tax iryohi form: 2025 (")
    assert call["sheets_data"]["医療費集計フォーム"][1:] == [
        ["患者 一郎", "さくら内科", "該当する", "", "", "", 2180, 0, "2025-01-06"],
        ["患者 花子", "小田急バス", "", "", "", "該当する", 920, 0, "2025-01-21"],
        ["患者 花子", "みどり薬局", "", "該当する", "", "", 1950, 0, "2025-01-20"],
    ]
    assert call["sheets_data"]["Checks"] == [["row", "message"], [5, "no receipt"]]


def test_iryohi_annotate_writes_review_sheet_with_flags(raw_csv, tmp_path, fake_writer):
    suggestions = tmp_path / "suggestions.csv"
    suggestions.write_text(
        "row,payee,amount,suggestion,reason\n"
        "2,さくら内科,2180,include,診療\n"
        "3,Amazon,1780,unsure,目的が不明\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main, ["tax", "iryohi", "annotate", "--input", str(raw_csv), "--suggestions", str(suggestions)]
    )

    assert result.exit_code == 0, result.output
    assert "Suggestions: 1 agree, 0 disagree, 1 unsure, 2 rows without a suggestion" in result.output

    call = fake_writer.calls[0]
    assert call["title"].startswith("finlog tax iryohi review: 2025 (")
    review = call["sheets_data"]["iryohi_review"]
    assert review[0] == HEADER + ["llm_suggestion", "llm_reason", "llm_flag"]
    assert [r[-3:] for r in review[1:]] == [
        ["include", "診療", ""],
        ["unsure", "目的が不明", "1"],
        ["", "", ""],
        ["", "", ""],
    ]
    assert call["frozen_header_sheets"] == {"iryohi_review"}
    assert [column for column, _ in call["row_highlight_rules"]["iryohi_review"]] == ["llm_flag"]


def test_iryohi_annotate_reports_mismatched_suggestion(raw_csv, tmp_path, fake_writer):
    suggestions = tmp_path / "suggestions.csv"
    suggestions.write_text("row,payee,amount,suggestion,reason\n2,Amazon,1780,exclude,サプリ\n", encoding="utf-8")

    result = CliRunner().invoke(
        main, ["tax", "iryohi", "annotate", "--input", str(raw_csv), "--suggestions", str(suggestions)]
    )

    assert result.exit_code == 1
    assert "Error: row 2: suggestion is for Amazon 1780, but the row is さくら内科 2180" in result.output
    assert fake_writer.calls == []
