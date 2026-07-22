from typing import Optional

DRIVE_FOLDER_ID_PROD = "1xUMheq3xhaY14JagZoDesQpQauClWDXe"
DRIVE_FOLDER_ID_DEV = "1HjukZ03FPEQde6R4Ky_lnAGYL8VL2Jxn"
DRIVE_FOLDER_ID = DRIVE_FOLDER_ID_PROD


def get_drive_folder_id(dev: bool = False, override_id: Optional[str] = None) -> str:
    """Return the target Google Drive folder ID based on dev flag or explicit override."""
    if override_id:
        return override_id
    if dev:
        return DRIVE_FOLDER_ID_DEV
    return DRIVE_FOLDER_ID_PROD

