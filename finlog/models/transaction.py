from dataclasses import dataclass, asdict
import datetime
from typing import Optional, Dict, Any


@dataclass
class CreditCardTransaction:
    """Represents a normalized credit card statement transaction."""

    transaction_id: str
    card_company: str
    date: datetime.date
    amount: int
    payee_merchant: str
    cardholder: Optional[str] = None
    card_number_suffix: Optional[str] = None
    note: Optional[str] = ""
    raw_row_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary format for Pandas / Sheet exporter."""
        res = asdict(self)
        if isinstance(res["date"], (datetime.date, datetime.datetime)):
            res["date"] = res["date"].isoformat()
        return res


@dataclass
class FinanceLogTransaction:
    """Represents a preprocessed personal finance log transaction (e.g. Zaim)."""

    transaction_id: str
    platform: str
    type: str  # expense, income, transfer
    date: datetime.date
    year: str
    month: str
    account: str
    amount: int
    currencycode: str = "JPY"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    item: Optional[str] = None
    payee_payer: Optional[str] = None
    tag_raw: Optional[str] = None
    tag_mod: Optional[str] = None
    note: Optional[str] = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary format for Pandas / Sheet exporter."""
        res = asdict(self)
        if isinstance(res["date"], (datetime.date, datetime.datetime)):
            res["date"] = res["date"].isoformat()
        return res
