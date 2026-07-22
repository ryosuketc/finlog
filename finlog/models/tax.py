from dataclasses import dataclass
from decimal import Decimal
import datetime
from typing import Optional, Dict, Any


@dataclass
class CarryoverState:
    """State model for stock holdings carryover state at year end/start."""
    year: int
    shares: Decimal
    average_cost_per_share: Decimal  # JPY per share

    def to_dict(self) -> Dict[str, Any]:
        """Serialize carryover state to JSON-serializable dictionary."""
        return {
            "year": self.year,
            "shares": float(self.shares),
            "average_cost_per_share": float(self.average_cost_per_share),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CarryoverState":
        """Deserialize carryover state from dictionary."""
        return cls(
            year=int(d["year"]),
            shares=Decimal(str(d["shares"])),
            average_cost_per_share=Decimal(str(d["average_cost_per_share"])),
        )


@dataclass
class VestRecord:
    """Represents a single GSU vesting transaction event."""
    award_date: datetime.date
    vesting_date: datetime.date
    shares: Decimal
    fmv_usd: Decimal


@dataclass
class DividendRecord:
    """Represents a single dividend or tax withholding event."""
    entry_date: datetime.date
    activity: str
    cash_usd: Decimal
    shares: Decimal = Decimal("0")
    share_price_usd: Decimal = Decimal("0")


@dataclass
class SaleRecord:
    """Represents a single stock sale transaction event."""
    execution_date: datetime.date
    price_usd: Decimal
    quantity: Decimal  # Positive quantity of shares sold
    fee_usd: Decimal = Decimal("0")  # Sales fee / broker expense in USD


@dataclass
class FXRateRecord:
    """Represents a daily exchange rate entry for audit log."""
    date: datetime.date
    ttm: Decimal
    tts: Decimal
    ttb: Decimal
    source: str
