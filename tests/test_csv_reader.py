import pytest
from pathlib import Path
from finlog.io.csv_reader import read_csv_lines, detect_encoding


def test_detect_encoding_utf8(tmp_path):
    """Test detecting UTF-8 encoding."""
    file_path = tmp_path / "test_utf8.csv"
    file_path.write_text("日付,内容,金額\n2026-05-20,マクドナルド,1000\n", encoding="utf-8")

    enc = detect_encoding(file_path)
    assert enc.lower() in ["utf-8", "ascii"]


def test_detect_encoding_cp932(tmp_path):
    """Test detecting CP932 / Shift_JIS encoding."""
    file_path = tmp_path / "test_sjis.csv"
    file_path.write_text("ご利用日,ご利用内容,金額\n2026/06/21,アマゾン,1000\n", encoding="cp932")

    enc = detect_encoding(file_path)
    assert enc.lower() in ["shift_jis", "cp932", "sjis"]


def test_read_csv_lines(tmp_path):
    """Test reading CSV lines as list of strings."""
    file_path = tmp_path / "test_read.csv"
    file_path.write_text("line1\nline2\n", encoding="utf-8")

    lines = read_csv_lines(file_path)
    assert len(lines) == 2
    assert lines[0] == "line1"
    assert lines[1] == "line2"


def test_read_csv_lines_file_not_found():
    """Test file not found error."""
    with pytest.raises(FileNotFoundError):
        read_csv_lines(Path("non_existent_file.csv"))


def test_detect_encoding_cp932_when_chardet_misclassifies(tmp_path):
    """Test that valid CP932 CSV is detected as cp932 even if chardet returns cp500."""
    from unittest.mock import patch

    file_path = tmp_path / "amex_cp932.csv"
    content = (
        "ご利用日,データ処理日,ご利用内容,カード会員様名,会員番号 #,金額,海外通貨利用金額,換算レート\r\n"
        "2026/09/18,2026/09/18,アマゾン　シーオージェーピー　　　　　,YURI TACHIBANA,-23015,713,,\r\n"
    )
    file_path.write_bytes(content.encode("cp932"))

    with patch("chardet.detect", return_value={"encoding": "cp500", "confidence": 0.17}):
        assert detect_encoding(file_path) == "cp932"
        lines = read_csv_lines(file_path)
        assert len(lines) == 2
        assert "ご利用日" in lines[0]
        assert "2026/09/18" in lines[1]

