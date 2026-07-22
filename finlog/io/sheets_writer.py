import csv
import os
import click
from pathlib import Path
from typing import Dict, List, Any, Optional
from finlog.config import DRIVE_FOLDER_ID, get_drive_folder_id

try:
    import gspread
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False


class SheetsWriter:
    """Lightweight I/O layer for writing multi-tab output data to Google Sheets or local CSVs."""

    def write_output(
        self,
        title: str,
        sheets_data: Dict[str, List[List[Any]]],
        service_account_path: Optional[str] = None,
        credentials_path: Optional[str] = None,
        output_dir: Optional[Path] = None,
        folder_id: Optional[str] = None,
    ) -> str:
        """Write multi-tab data to Google Sheets (via OAuth or Service Account) or fallback to local CSVs."""
        if HAS_GSPREAD:
            try:
                gc = None
                if service_account_path and os.path.exists(service_account_path):
                    gc = gspread.service_account(filename=service_account_path)
                elif credentials_path and os.path.exists(credentials_path):
                    gc = gspread.oauth(credentials_filename=credentials_path)
                else:
                    default_creds = Path.home() / ".config" / "gspread" / "credentials.json"
                    authorized_user = Path.home() / ".config" / "gspread" / "authorized_user.json"
                    if default_creds.exists():
                        gc = self._get_oauth_client(default_creds, authorized_user)

                if gc:
                    return self._create_spreadsheet(gc, title, sheets_data, folder_id=folder_id)

            except Exception as e:
                print(f"[Warning] Google Sheets export failed ({e}). Falling back to local CSV output.")

        return self._write_local_csvs(title, sheets_data, output_dir=output_dir)

    def _get_oauth_client(self, creds_path: Path, auth_user_path: Path) -> Any:
        if auth_user_path.exists():
            return gspread.oauth(
                credentials_filename=str(creds_path),
                authorized_user_filename=str(auth_user_path),
            )

        from google_auth_oauthlib.flow import InstalledAppFlow
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes=scopes)
        # open_browser=False prevents CUI browsers (lynx) from launching in terminal
        creds = flow.run_local_server(port=0, open_browser=False)

        auth_user_path.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_user_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        return gspread.authorize(creds)

    def _create_spreadsheet(
        self,
        gc: Any,
        title: str,
        sheets_data: Dict[str, List[List[Any]]],
        folder_id: Optional[str] = None,
    ) -> str:
        target_folder_id = folder_id or DRIVE_FOLDER_ID
        if target_folder_id:
            sh = gc.create(title, folder_id=target_folder_id)
        else:
            sh = gc.create(title)

        first = True
        with click.progressbar(
            sheets_data.items(),
            label="Uploading to Google Sheets",
            length=len(sheets_data),
        ) as bar:
            for sheet_name, rows in bar:
                if first:
                    ws = sh.sheet1
                    ws.update_title(sheet_name)
                    first = False
                else:
                    ws = sh.add_worksheet(title=sheet_name, rows=len(rows) + 10, cols=15)

                if rows:
                    ws.update(rows)

        return f"Google Spreadsheet created successfully: {sh.url}"

    def _write_local_csvs(
        self,
        title: str,
        sheets_data: Dict[str, List[List[Any]]],
        output_dir: Optional[Path] = None,
    ) -> str:
        safe_title = "".join([c if c.isalnum() or c in ("-", "_", " ") else "_" for c in title]).strip()
        base_dir = output_dir if output_dir is not None else Path("user_data/output")
        target_dir = base_dir / safe_title
        target_dir.mkdir(parents=True, exist_ok=True)

        for sheet_name, rows in sheets_data.items():
            file_path = target_dir / f"{sheet_name}.csv"
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(rows)

        return f"Output generated locally at: {target_dir.resolve()}"
