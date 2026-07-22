from abc import ABC, abstractmethod
import datetime
import re
import unicodedata
from typing import Any, List, Optional


class BaseParser(ABC):
    """Abstract base class for all CSV parsers."""

    @abstractmethod
    def parse(self, lines: List[str]) -> List[Any]:
        """Parse raw CSV line strings into transaction objects."""
        pass

    def clean_amount(self, value: Any) -> int:
        """Sanitize numeric amount value to integer JPY."""
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)

        s = str(value).strip().replace(",", "").replace('"', "")
        if not s:
            return 0

        try:
            return int(float(s))
        except ValueError:
            return 0

    def clean_string(self, value: Optional[str]) -> str:
        """Clean and normalize string (NFKC normalization, strip whitespace)."""
        if not value:
            return ""
        s = unicodedata.normalize("NFKC", str(value))
        return s.strip()

    def parse_date(self, date_str: str) -> datetime.date:
        """Parse date string (YYYY-MM-DD or YYYY/MM/DD) into datetime.date."""
        s = self.clean_string(date_str)
        s = s.replace("/", "-")
        parts = s.split("-")
        if len(parts) == 3:
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        raise ValueError(f"Invalid date format: {date_str}")

    def generate_transaction_id(self, prefix: str, index: int) -> str:
        """Format unique deterministic transaction ID."""
        return f"{prefix}-{index:05d}"
