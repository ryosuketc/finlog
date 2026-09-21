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
            mock_ws.update.assert_called_once_with(
                sheets_data["Sheet1"], value_input_option="USER_ENTERED"
            )


def test_get_drive_folder_id():
    from finlog.config import (
        get_drive_folder_id,
        DRIVE_FOLDER_ID_PROD,
        DRIVE_FOLDER_ID_DEV,
    )

    # Default -> PROD
    assert get_drive_folder_id() == DRIVE_FOLDER_ID_PROD
    assert get_drive_folder_id(dev=False) == DRIVE_FOLDER_ID_PROD

    # dev=True -> DEV
    assert get_drive_folder_id(dev=True) == DRIVE_FOLDER_ID_DEV

    # override_id
    assert get_drive_folder_id(override_id="custom-folder") == "custom-folder"
    assert get_drive_folder_id(dev=True, override_id="custom-folder") == "custom-folder"


def test_sheets_writer_custom_folder_id():
    writer = SheetsWriter()
    sheets_data = {"Sheet1": [["a", "b"], [1, 2]]}

    mock_gc = MagicMock()
    mock_sh = MagicMock()
    mock_sh.url = "https://docs.google.com/spreadsheets/d/test-id"
    mock_ws = MagicMock()
    mock_sh.sheet1 = mock_ws
    mock_gc.create.return_value = mock_sh

    with patch("gspread.oauth", return_value=mock_gc):
        with patch.object(Path, "exists", return_value=True):
            writer.write_output("Test Title", sheets_data, folder_id="dev-folder-123")
            mock_gc.create.assert_called_once_with("Test Title", folder_id="dev-folder-123")


def test_sheets_writer_oauth_invalid_grant_recovery():
    from google.auth.exceptions import RefreshError

    writer = SheetsWriter()
    sheets_data = {"Sheet1": [["a", "b"], [1, 2]]}
    tests_dir = Path(__file__).parent

    with tempfile.TemporaryDirectory(dir=tests_dir) as tmp_dir:
        tmp_path = Path(tmp_dir)
        gspread_dir = tmp_path / ".config" / "gspread"
        gspread_dir.mkdir(parents=True, exist_ok=True)
        creds_file = gspread_dir / "credentials.json"
        auth_user_file = gspread_dir / "authorized_user.json"
        creds_file.write_text('{"installed": {}}', encoding="utf-8")
        auth_user_file.write_text('{"refresh_token": "expired"}', encoding="utf-8")

        # First client loaded from stale authorized_user.json raises RefreshError on create()
        stale_gc = MagicMock()
        stale_gc.create.side_effect = RefreshError(
            "invalid_grant: Bad Request",
            {"error": "invalid_grant", "error_description": "Bad Request"},
        )

        # Second client authorized after InstalledAppFlow succeeds
        fresh_gc = MagicMock()
        mock_sh = MagicMock()
        mock_sh.url = "https://docs.google.com/spreadsheets/d/recovered-id"
        mock_sh.sheet1 = MagicMock()
        fresh_gc.create.return_value = mock_sh

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"refresh_token": "fresh_token"}'
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("gspread.oauth", return_value=stale_gc), \
             patch("gspread.authorize", return_value=fresh_gc) as mock_authorize, \
             patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            res = writer.write_output("Recovered Title", sheets_data, output_dir=tmp_path)

        assert "Google Spreadsheet created successfully:" in res
        assert "https://docs.google.com/spreadsheets/d/recovered-id" in res
        mock_flow.run_local_server.assert_called_once_with(port=0, open_browser=False)
        mock_authorize.assert_called_once_with(mock_creds)
        assert auth_user_file.read_text(encoding="utf-8") == '{"refresh_token": "fresh_token"}'


