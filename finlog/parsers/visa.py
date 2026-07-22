import csv
from typing import List
from finlog.models.transaction import CreditCardTransaction
from finlog.parsers.base import BaseParser


class VisaParser(BaseParser):
    """Parser for ANA VISA Platinum CSV statement files."""

    def parse(self, lines: List[str]) -> List[CreditCardTransaction]:
        if not lines:
            return []

        reader = csv.reader(lines)
        rows = list(reader)

        if not rows:
            return []

        cardholder = ""
        card_suffix = ""

        start_idx = 0
        # Check Line 1 metadata
        first_row = rows[0]
        if first_row and len(first_row) >= 2 and not first_row[0].startswith("20"):
            cardholder = self.clean_string(first_row[0])
            if len(first_row) > 1:
                card_suffix = self.clean_string(first_row[1]).split("-")[0] + "-" + self.clean_string(first_row[1]).split("-")[1]
            start_idx = 1

        transactions: List[CreditCardTransaction] = []
        tx_count = 0

        for line_idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
            if not row:
                continue

            date_str = self.clean_string(row[0])
            # Skip footer total line (where col 0 is empty)
            if not date_str or not date_str[0].isdigit():
                continue

            if len(row) < 3:
                continue

            dt = self.parse_date(date_str)
            merchant_raw = self.clean_string(row[1])
            amount = self.clean_amount(row[2])
            note = self.clean_string(row[6]) if len(row) > 6 else ""

            tx_count += 1
            tx_id = self.generate_transaction_id("VISA", tx_count)

            tx = CreditCardTransaction(
                transaction_id=tx_id,
                card_company="ANA VISA Platinum",
                date=dt,
                amount=amount,
                payee_merchant=merchant_raw,
                cardholder=cardholder,
                card_number_suffix=card_suffix,
                note=note,
                raw_row_index=line_idx,
            )
            transactions.append(tx)

        return transactions
