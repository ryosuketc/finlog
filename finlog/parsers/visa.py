import csv
from typing import Dict, List
from finlog.models.transaction import CreditCardTransaction
from finlog.parsers.base import BaseParser


VISA_REFORMATTED_HEADER = [
    "source_line",
    "cardholder",
    "card_number",
    "card_product",
    "use_date",
    "merchant",
    "amount",
    "payment_type",
    "payment_count",
    "billed_amount",
    "note",
]

_SECTION_FIELDS = 3  # cardholder, card_number, card_product
_TRANSACTION_FIELDS = 7  # use_date .. note


def reformat_visa_rows(rows: List[List[str]]) -> List[List[str]]:
    """Flatten a multi-section ANA VISA statement into one transaction per row.

    Each section starts with a header row (cardholder, card number, card product).
    Every transaction row gets its section values and its 1-based source line.
    Section header, subtotal, and total rows are dropped. Rows are sorted by
    cardholder (in order of first appearance), then by use date.
    """
    section = [""] * _SECTION_FIELDS
    holder_order: Dict[str, int] = {}
    transactions: List[List[str]] = []

    for line_no, row in enumerate(rows, start=1):
        first = row[0].strip() if row else ""
        if not first:
            continue  # blank, subtotal, or total row
        if not first[0].isdigit():
            section = (row + [""] * _SECTION_FIELDS)[:_SECTION_FIELDS]
            holder_order.setdefault(section[0], len(holder_order))
            continue
        if len(row) < 3:
            continue
        transactions.append([str(line_no)] + section + (row + [""] * _TRANSACTION_FIELDS)[:_TRANSACTION_FIELDS])

    transactions.sort(key=lambda r: (holder_order.get(r[1], -1), r[4]))
    return [list(VISA_REFORMATTED_HEADER)] + transactions


class VisaParser(BaseParser):
    """Parser for ANA VISA Platinum CSV statement files."""

    def parse(self, lines: List[str]) -> List[CreditCardTransaction]:
        if not lines:
            return []

        reformatted = reformat_visa_rows(list(csv.reader(lines)))

        transactions: List[CreditCardTransaction] = []
        for tx_count, row in enumerate(reformatted[1:], start=1):
            source_line, cardholder, card_number, _, date_str, merchant, amount, _, _, _, note = row
            transactions.append(
                CreditCardTransaction(
                    transaction_id=self.generate_transaction_id("VISA", tx_count),
                    card_company="ANA VISA Platinum",
                    date=self.parse_date(date_str),
                    amount=self.clean_amount(amount),
                    payee_merchant=self.clean_string(merchant),
                    cardholder=self.clean_string(cardholder),
                    card_number_suffix=self._card_number_prefix(card_number),
                    note=self.clean_string(note),
                    raw_row_index=int(source_line),
                )
            )

        return transactions

    def _card_number_prefix(self, card_number: str) -> str:
        """Return the unmasked leading groups (e.g. 1234-56** from 1234-56**-****-****)."""
        return "-".join(self.clean_string(card_number).split("-")[:2])
