import csv
import re
from typing import List
from finlog.models.transaction import FinanceLogTransaction
from finlog.parsers.base import BaseParser


class ZaimParser(BaseParser):
    """Parser for Zaim exported CSV files."""

    def parse(self, lines: List[str]) -> List[FinanceLogTransaction]:
        if not lines:
            return []

        reader = csv.reader(lines)
        rows = list(reader)

        if not rows:
            return []

        # Check header
        header = rows[0]
        start_idx = 1 if header and "日付" in header[0] else 0

        transactions: List[FinanceLogTransaction] = []
        tx_count = 0

        for row in rows[start_idx:]:
            if not row or len(row) < 12:
                continue

            date_str = self.clean_string(row[0])
            if not date_str:
                continue

            dt = self.parse_date(date_str)
            raw_type = self.clean_string(row[1])

            # Map type
            if raw_type == "payment":
                tx_type = "expense"
            elif raw_type == "income":
                tx_type = "income"
            elif raw_type == "transfer":
                tx_type = "transfer"
            else:
                tx_type = "expense"  # fallback

            accountfrom = self.clean_string(row[4])
            accountto = self.clean_string(row[5])

            if tx_type == "expense":
                account = accountfrom
                amount = self.clean_amount(row[11])
            elif tx_type == "income":
                account = accountto
                amount = self.clean_amount(row[10])
            else:
                account = "transfer"
                amount = self.clean_amount(row[12]) if len(row) > 12 else 0

            category = self.clean_string(row[2])
            subcategory = self.clean_string(row[3])
            item = self.clean_string(row[6])
            note_raw = self.clean_string(row[7])
            merchant = self.clean_string(row[8])
            currency = self.clean_string(row[9]) or "JPY"

            # Preprocess note and tag_mod
            tag_mod = self._extract_tag_mod(note_raw)
            clean_note = self._clean_note_text(note_raw)

            tx_count += 1
            tx_id = self.generate_transaction_id("ZAIM", tx_count)

            tx = FinanceLogTransaction(
                transaction_id=tx_id,
                platform="Zaim",
                type=tx_type,
                date=dt,
                year=dt.strftime("%Y"),
                month=dt.strftime("%Y-%m"),
                account=account,
                amount=amount,
                currencycode=currency,
                category=category,
                subcategory=subcategory,
                item=item,
                payee_payer=merchant,
                tag_raw=note_raw,
                tag_mod=tag_mod,
                note=clean_note,
            )
            transactions.append(tx)

        return transactions

    def _extract_tag_mod(self, note: str) -> str:
        if not note:
            return "Neither ichika/yuri/ryosuke"

        note_lower = note.lower()
        if "#ryosuke" in note_lower:
            return "ryosuke"
        elif "#ichika" in note_lower:
            return "ichika"
        elif "#hakuyo" in note_lower:
            return "hakuyo"
        elif "#yuri" in note_lower:
            return "yuri"
        else:
            return "Neither ichika/yuri/ryosuke"

    def _clean_note_text(self, note: str) -> str:
        if not note:
            return ""
        hash_pos = note.find("#")
        if hash_pos == -1:
            return note.strip()
        return note[:hash_pos].strip()
