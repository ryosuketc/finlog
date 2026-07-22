import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from finlog.io.sheets_writer import SheetsWriter


import tempfile


def test_sheets_writer_fallback():
    writer = SheetsWriter()
    sheets_data = {
        "TestSheet": [["col1", "col2"], ["val1", "val2"]]
    }
    tests_dir = Path(__file__).parent

    with tempfile.TemporaryDirectory(dir=tests_dir) as tmp_dir:
        tmp_output_path = Path(tmp_dir)
        with patch("finlog.io.sheets_writer.HAS_GSPREAD", False):
            res = writer.write_output("Test Title", sheets_data, output_dir=tmp_output_path)
            assert "Output generated locally at:" in res
            assert (tmp_output_path / "Test Title" / "TestSheet.csv").exists()

    assert not tmp_output_path.exists()


def test_sheets_writer_oauth_success():
    writer = SheetsWriter()
    sheets_data = {
        "Sheet1": [["a", "b"], [1, 2]]
    }

    mock_gc = MagicMock()
    mock_sh = MagicMock()
    mock_sh.url = "https://docs.google.com/spreadsheets/d/test-id"
    mock_ws = MagicMock()
    mock_sh.sheet1 = mock_ws
    mock_gc.create.return_value = mock_sh

    with patch("gspread.oauth", return_value=mock_gc):
        with patch.object(Path, "exists", return_value=True):
            res = writer.write_output("Test Title", sheets_data)
            assert "Google Spreadsheet created successfully:" in res
            assert mock_sh.url in res
