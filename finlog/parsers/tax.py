import csv
import datetime
import io
import re
from decimal import Decimal
from typing import List, Optional

from finlog.parsers.base import BaseParser
from finlog.models.tax import VestRecord, DividendRecord, SaleRecord


def parse_flexible_date(date_str: str) -> datetime.date:
    """Parse date strings in YYYY-MM-DD, YYYY/MM/DD, or DD-Mon-YYYY format."""
    s = date_str.strip()
    if not s:
        raise ValueError("Empty date string")

    # Try ISO YYYY-MM-DD or YYYY/MM/DD
    s_iso = s.replace("/", "-")
    parts = s_iso.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))

    # Try DD-Mon-YYYY (e.g. 25-Dec-2024, 08-Mar-2023)
    try:
        return datetime.datetime.strptime(s, "%d-%b-%Y").date()
    except ValueError:
        pass

    raise ValueError(f"Unable to parse date: {date_str}")


def clean_decimal(value: str) -> Decimal:
    """Clean currency/numeric strings (stripping $, commas, quotes) into Decimal."""
    if not value:
        return Decimal("0")
    s = str(value).strip().replace("$", "").replace(",", "").replace('"', "")
    if not s or s == "N/A":
        return Decimal("0")
    return Decimal(s)


class VestsParser(BaseParser):
    """Parser for Google/Broker GSU Vests CSV export."""

    def parse(self, lines: List[str]) -> List[VestRecord]:
        records: List[VestRecord] = []
        raw_rows = list(csv.reader(io.StringIO("\n".join(lines))))

        for row in raw_rows:
            if not row or len(row) < 7:
                continue

            # Header / metadata line skip
            first_cell = row[0].strip()
            if "Alphabet" in first_cell or first_cell.startswith("Purno") or "This is not" in first_cell:
                continue

            award_date_str = row[2].strip()
            vesting_date_str = row[3].strip()
            shares_str = row[4].strip()
            fmv_str = row[6].strip()

            if not award_date_str or not vesting_date_str or not shares_str:
                continue

            try:
                award_date = parse_flexible_date(award_date_str)
                vesting_date = parse_flexible_date(vesting_date_str)
                shares = clean_decimal(shares_str)
                fmv_usd = clean_decimal(fmv_str)

                if shares > 0:
                    records.append(
                        VestRecord(
                            award_date=award_date,
                            vesting_date=vesting_date,
                            shares=shares,
                            fmv_usd=fmv_usd,
                        )
                    )
            except (ValueError, Exception):
                continue

        return records


class DividendParser(BaseParser):
    """Parser for Broker Dividend CSV export."""

    def parse(self, lines: List[str]) -> List[DividendRecord]:
        records: List[DividendRecord] = []
        raw_rows = list(csv.reader(io.StringIO("\n".join(lines))))

        for row in raw_rows:
            if not row or len(row) < 4:
                continue

            first_cell = row[0].strip()
            if first_cell == "Entry Date" or not first_cell:
                continue

            try:
                entry_date = parse_flexible_date(first_cell)
                activity = row[1].strip()
                cash_usd = clean_decimal(row[3]) if len(row) > 3 else Decimal("0")
                shares = clean_decimal(row[4]) if len(row) > 4 else Decimal("0")
                share_price_usd = clean_decimal(row[5]) if len(row) > 5 else Decimal("0")

                records.append(
                    DividendRecord(
                        entry_date=entry_date,
                        activity=activity,
                        cash_usd=cash_usd,
                        shares=shares,
                        share_price_usd=share_price_usd,
                    )
                )
            except (ValueError, Exception):
                continue

        return records


class SalesParser(BaseParser):
    """Parser for Broker Stock Sales CSV export."""

    def parse(self, lines: List[str]) -> List[SaleRecord]:
        records: List[SaleRecord] = []
        raw_rows = list(csv.reader(io.StringIO("\n".join(lines))))

        col_date = 0
        col_price = 5
        col_quantity = 6
        col_fee: Optional[int] = None

        for row in raw_rows:
            if not row or len(row) < 3:
                continue

            headers_lower = [c.strip().lower() for c in row]
            if "execution date" in headers_lower:
                for idx, h in enumerate(headers_lower):
                    if h in ("execution date", "date"):
                        col_date = idx
                    elif h in ("price", "sale price", "price per share"):
                        col_price = idx
                    elif h in ("quantity", "shares", "quantity sold"):
                        col_quantity = idx
                    elif h in ("fee", "fees", "commission", "sales fee", "brokerage fee", "broker fee"):
                        col_fee = idx
                continue

            first_cell = row[0].strip()
            if first_cell == "Execution Date" or "Please note" in first_cell or not first_cell:
                continue

            try:
                exec_date = parse_flexible_date(row[col_date])
                price_usd = clean_decimal(row[col_price])
                quantity = abs(clean_decimal(row[col_quantity]))
                fee_usd = clean_decimal(row[col_fee]) if col_fee is not None and col_fee < len(row) else Decimal("0")

                if quantity > 0:
                    records.append(
                        SaleRecord(
                            execution_date=exec_date,
                            price_usd=price_usd,
                            quantity=quantity,
                            fee_usd=fee_usd,
                        )
                    )
            except (ValueError, Exception):
                continue

        return records
