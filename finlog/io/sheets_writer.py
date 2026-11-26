import csv
import os
import click
from pathlib import Path
from typing import AbstractSet, Dict, List, Any, Mapping, Optional, Sequence, Tuple
from finlog.config import DRIVE_FOLDER_ID, get_drive_folder_id

try:
    import gspread
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# (header name, Sheets API Color) pairs. Earlier rules take precedence.
RowHighlightRules = Sequence[Tuple[str, Mapping[str, float]]]


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
        frozen_header_sheets: AbstractSet[str] = frozenset(),
        row_highlight_rules: Mapping[str, RowHighlightRules] = {},
    ) -> str:
        """Write multi-tab data to Google Sheets (via OAuth or Service Account) or fallback to local CSVs.

        frozen_header_sheets: sheets whose first row is frozen.
        row_highlight_rules: sheet name -> (header name, color) pairs; rows where that
            column is not empty get that background color, and earlier pairs win.
            Both apply to Google Sheets output only.
        """

        def create(gc: Any) -> str:
            return self._create_spreadsheet(
                gc,
                title,
                sheets_data,
                folder_id=folder_id,
                frozen_header_sheets=frozen_header_sheets,
                row_highlight_rules=row_highlight_rules,
            )

        if HAS_GSPREAD:
            try:
                gc = None
                if service_account_path and os.path.exists(service_account_path):
                    gc = gspread.service_account(filename=service_account_path)
                    return create(gc)

                creds_path = (
                    Path(credentials_path)
                    if credentials_path
                    else Path.home() / ".config" / "gspread" / "credentials.json"
                )
                authorized_user = Path.home() / ".config" / "gspread" / "authorized_user.json"

                if creds_path.exists():
                    try:
                        gc = self._get_oauth_client(creds_path, authorized_user)
                        return create(gc)
                    except Exception as oauth_err:
                        if self._is_invalid_grant_error(oauth_err):
                            print(
                                "[Notice] OAuth token expired or revoked (invalid_grant). "
                                "Removing cached token and starting re-authentication..."
                            )
                            if authorized_user.exists():
                                authorized_user.unlink()
                            gc = self._run_oauth_flow(creds_path, authorized_user)
                            return create(gc)
                        raise

            except Exception as e:
                print(f"[Warning] Google Sheets export failed ({e}). Falling back to local CSV output.")

        return self._write_local_csvs(title, sheets_data, output_dir=output_dir)

    def _is_invalid_grant_error(self, exc: Exception) -> bool:
        return "invalid_grant" in str(exc)

    def _get_oauth_client(self, creds_path: Path, auth_user_path: Path) -> Any:
        if auth_user_path.exists():
            return gspread.oauth(
                credentials_filename=str(creds_path),
                authorized_user_filename=str(auth_user_path),
            )
        return self._run_oauth_flow(creds_path, auth_user_path)

    def _run_oauth_flow(self, creds_path: Path, auth_user_path: Path) -> Any:
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
        frozen_header_sheets: AbstractSet[str] = frozenset(),
        row_highlight_rules: Mapping[str, RowHighlightRules] = {},
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
                    ws.update(rows, value_input_option="USER_ENTERED")
                if sheet_name in frozen_header_sheets:
                    ws.freeze(rows=1)
                if sheet_name in row_highlight_rules and rows:
                    sh.batch_update(self._row_highlight_request(ws.id, rows[0], row_highlight_rules[sheet_name]))

        return f"Google Spreadsheet created successfully: {sh.url}"

    def _row_highlight_request(
        self, sheet_id: int, header: List[Any], rules: RowHighlightRules
    ) -> Dict[str, Any]:
        """Build conditional format rules that color data rows whose column is not empty.

        Sheets applies the first matching rule (lowest index), so rule order is precedence.
        """
        requests = []
        for index, (column_name, color) in enumerate(rules):
            col_letter = gspread.utils.rowcol_to_a1(1, header.index(column_name) + 1).rstrip("1")
            requests.append({
                "addConditionalFormatRule": {
                    "index": index,
                    "rule": {
                        "ranges": [{"sheetId": sheet_id, "startRowIndex": 1}],
                        "booleanRule": {
                            "condition": {
                                "type": "CUSTOM_FORMULA",
                                "values": [{"userEnteredValue": f'=${col_letter}2<>""'}],
                            },
                            "format": {"backgroundColor": color},
                        },
                    },
                },
            })
        return {"requests": requests}

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
