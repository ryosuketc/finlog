import chardet
from pathlib import Path
from typing import List, Union


def detect_encoding(file_path: Union[str, Path]) -> str:
    """Detect file encoding using chardet, normalizing Shift_JIS variants to cp932."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, "rb") as f:
        raw_bytes = f.read(10000)

    result = chardet.detect(raw_bytes)
    encoding = result.get("encoding") or "utf-8"

    if encoding.lower() in ["shift_jis", "cp932", "sjis", "shift-jis"]:
        return "cp932"

    return encoding


def read_csv_lines(file_path: Union[str, Path]) -> List[str]:
    """Read CSV file lines handling encoding automatically and returning list of strings."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    encoding = detect_encoding(path)

    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            lines = [line.rstrip("\r\n") for line in f]
        return lines
    except UnicodeDecodeError:
        # Fallback to cp932
        with open(path, "r", encoding="cp932", errors="replace") as f:
            lines = [line.rstrip("\r\n") for line in f]
        return lines
