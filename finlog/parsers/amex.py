import csv
from typing import List
from finlog.models.transaction import CreditCardTransaction
from finlog.parsers.base import BaseParser


class AmexParser(BaseParser):
    """Parser for American Express CSV statement files."""

    def parse(self, lines: List[str]) -> List[CreditCardTransaction]:
        if not lines:
            return []

        reader = csv.reader(lines)
        rows = list(reader)

        if not rows:
            return []

        header = rows[0]
        start_idx = 1 if header and "ご利用日" in header[0] else 0

        transactions: List[CreditCardTransaction] = []
        tx_count = 0

        for line_idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
            if not row or len(row) < 6:
                continue

            date_str = self.clean_string(row[0])
            if not date_str or not date_str[0].isdigit():
                continue

            dt = self.parse_date(date_str)
            merchant_raw = self.clean_string(row[2])
            cardholder = self.clean_string(row[3])
            card_suffix = self.clean_string(row[4])
            amount = self.clean_amount(row[5])

            tx_count += 1
            tx_id = self.generate_transaction_id("AMEX", tx_count)

            tx = CreditCardTransaction(
                transaction_id=tx_id,
                card_company="Amex Proper",
                date=dt,
                amount=amount,
                payee_merchant=merchant_raw,
                cardholder=cardholder,
                card_number_suffix=card_suffix,
                note="",
                raw_row_index=line_idx,
            )
            transactions.append(tx)

        return transactions
