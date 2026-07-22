from dataclasses import dataclass
import datetime
import itertools
from typing import Any, Callable, Dict, List, Optional
from finlog.models.transaction import CreditCardTransaction, FinanceLogTransaction
from finlog.matching.strategies.base import BaseSimilarityStrategy
from finlog.matching.strategies.contains_strategy import SimpleContainsStrategy


CARD_ACCOUNT_MAPPINGS: Dict[str, Dict[str, List[str]]] = {
    "ANA VISA Platinum": {
        "unpaid": ["ANA VISA Platinum Unpaid"],
        "paid": ["ANA VISA Platinum Paid"],
    },
    "Amex Proper": {
        "unpaid": ["Amex Proper Unpaid", "Yuri Amex Proper Unpaid"],
        "paid": ["Amex Proper Paid"],
    },
}


def get_card_accounts(card_company: str, unpaid_only: bool = True) -> List[str]:
    """Return allowed Zaim accounts for a given card company based on unpaid_only flag."""
    c_norm = card_company.lower()
    for key, mapping in CARD_ACCOUNT_MAPPINGS.items():
        k_norm = key.lower()
        if k_norm in c_norm or c_norm in k_norm:
            if unpaid_only:
                return mapping["unpaid"]
            return mapping["unpaid"] + mapping["paid"]
    return []


@dataclass
class MatchedPair:
    card_tx: CreditCardTransaction
    zaim_tx: FinanceLogTransaction
    score: float


@dataclass
class ReconciliationResult:
    matched_pairs: List[MatchedPair]
    unmatched_card_txs: List[CreditCardTransaction]
    zaim_view_entries: List[Dict[str, Any]]
    credit_view_entries: List[Dict[str, Any]]


class ReconciliationEngine:
    """Core engine for reconciling credit card transactions against Zaim transactions."""

    def __init__(
        self,
        similarity_strategy: Optional[BaseSimilarityStrategy] = None,
        date_tolerance_days: int = 5,
        unpaid_only: bool = True,
    ):
        self.strategy = similarity_strategy or SimpleContainsStrategy()
        self.date_tolerance_days = date_tolerance_days
        self.unpaid_only = unpaid_only

    def reconcile(
        self,
        card_transactions: List[CreditCardTransaction],
        zaim_transactions: List[FinanceLogTransaction],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ReconciliationResult:
        if not card_transactions:
            return ReconciliationResult(
                matched_pairs=[],
                unmatched_card_txs=[],
                zaim_view_entries=[self._format_zaim_view_entry(z, "Unmatched") for z in zaim_transactions],
                credit_view_entries=[],
            )

        # Calculate card statement date bounds
        card_dates = [c.date for c in card_transactions]
        min_card_date = min(card_dates) - datetime.timedelta(days=self.date_tolerance_days)
        max_card_date = max(card_dates) + datetime.timedelta(days=self.date_tolerance_days)

        matched_card_ids = set()
        matched_zaim_ids = set()
        matched_pairs: List[MatchedPair] = []

        total_cards = len(card_transactions)
        # Find candidate pairs for each card transaction
        for idx, card_tx in enumerate(card_transactions):
            if progress_callback:
                progress_callback(idx + 1, total_cards)
            allowed_accounts = get_card_accounts(card_tx.card_company, unpaid_only=self.unpaid_only)

            candidates = []
            for zaim_tx in zaim_transactions:
                if zaim_tx.transaction_id in matched_zaim_ids:
                    continue

                # Account matching using mapped allowed_accounts if found, otherwise fallback
                if allowed_accounts:
                    if zaim_tx.account not in allowed_accounts:
                        continue
                else:
                    if self.unpaid_only and "unpaid" not in (zaim_tx.account or "").lower():
                        continue
                    if not self._accounts_match(card_tx.card_company, zaim_tx.account):
                        continue

                # Hard Constraint 1: Exact Amount
                if abs(card_tx.amount) != abs(zaim_tx.amount):
                    continue

                # Hard Constraint 3: Date Tolerance Window
                date_diff = abs((card_tx.date - zaim_tx.date).days)
                if date_diff > self.date_tolerance_days:
                    continue

                # Soft Ranking Score
                date_score = 1.0 - (0.2 * date_diff)
                text_score = self.strategy.similarity(card_tx.payee_merchant, zaim_tx.payee_payer or "")
                total_score = (0.4 * date_score) + (0.6 * text_score)

                if total_score >= 0.4:
                    candidates.append((total_score, zaim_tx))

            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_zaim_tx = candidates[0]

                matched_card_ids.add(card_tx.transaction_id)
                matched_zaim_ids.add(best_zaim_tx.transaction_id)
                matched_pairs.append(MatchedPair(card_tx=card_tx, zaim_tx=best_zaim_tx, score=best_score))

        # Identify unmatched card transactions after Phase 1
        unmatched_card_txs = [c for c in card_transactions if c.transaction_id not in matched_card_ids]

        # Phase 2: Bundled (N:1) Matching for unmatched card transactions
        bundled_card_matches: Dict[str, List[str]] = {}
        bundled_zaim_matches: Dict[str, str] = {}

        for card_tx in unmatched_card_txs:
            allowed_accounts = get_card_accounts(card_tx.card_company, unpaid_only=self.unpaid_only)
            norm_card_merchant = self.strategy.normalize(card_tx.payee_merchant)

            # Filter candidate Zaim transactions (unmatched, exact account, exact date, exact normalized merchant)
            candidates = []
            for zaim_tx in zaim_transactions:
                if zaim_tx.transaction_id in matched_zaim_ids:
                    continue

                if allowed_accounts:
                    if zaim_tx.account not in allowed_accounts:
                        continue
                else:
                    if self.unpaid_only and "unpaid" not in (zaim_tx.account or "").lower():
                        continue
                    if not self._accounts_match(card_tx.card_company, zaim_tx.account):
                        continue

                # Exact Date Match
                if card_tx.date != zaim_tx.date:
                    continue

                # Exact Normalized Merchant Match
                norm_zaim_merchant = self.strategy.normalize(zaim_tx.payee_payer or "")
                if norm_card_merchant != norm_zaim_merchant:
                    continue

                candidates.append(zaim_tx)

            if len(candidates) >= 2:
                matching_subset = self._find_matching_subset(candidates, card_tx.amount)
                if matching_subset:
                    matched_card_ids.add(card_tx.transaction_id)
                    z_ids = [z.transaction_id for z in matching_subset]
                    bundled_card_matches[card_tx.transaction_id] = z_ids
                    for z in matching_subset:
                        matched_zaim_ids.add(z.transaction_id)
                        bundled_zaim_matches[z.transaction_id] = card_tx.transaction_id

        # Update unmatched card transactions after Phase 2
        unmatched_card_txs = [c for c in card_transactions if c.transaction_id not in matched_card_ids]

        # Build Zaim View entries
        zaim_view_entries = []
        matched_pair_by_zaim_id = {pair.zaim_tx.transaction_id: pair for pair in matched_pairs}

        for zaim_tx in zaim_transactions:
            if zaim_tx.transaction_id in matched_pair_by_zaim_id:
                pair = matched_pair_by_zaim_id[zaim_tx.transaction_id]
                entry = self._format_zaim_view_entry(
                    zaim_tx,
                    status="Matched",
                    matched_id=pair.card_tx.transaction_id,
                )
            elif zaim_tx.transaction_id in bundled_zaim_matches:
                entry = self._format_zaim_view_entry(
                    zaim_tx,
                    status="Matched (Bundled)",
                    matched_id=bundled_zaim_matches[zaim_tx.transaction_id],
                )
            elif zaim_tx.date < min_card_date or zaim_tx.date > max_card_date:
                entry = self._format_zaim_view_entry(zaim_tx, status="Out of Statement Scope")
            else:
                entry = self._format_zaim_view_entry(zaim_tx, status="Unmatched")
            zaim_view_entries.append(entry)

        # Build Credit View entries
        credit_view_entries = []
        matched_pair_by_card_id = {pair.card_tx.transaction_id: pair for pair in matched_pairs}

        for card_tx in card_transactions:
            if card_tx.transaction_id in matched_pair_by_card_id:
                pair = matched_pair_by_card_id[card_tx.transaction_id]
                entry = self._format_credit_view_entry(
                    card_tx,
                    status="Matched",
                    matched_id=pair.zaim_tx.transaction_id,
                )
            elif card_tx.transaction_id in bundled_card_matches:
                z_ids_str = ", ".join(bundled_card_matches[card_tx.transaction_id])
                entry = self._format_credit_view_entry(
                    card_tx,
                    status="Matched (Bundled)",
                    matched_id=z_ids_str,
                )
            else:
                entry = self._format_credit_view_entry(card_tx, status="Unmatched")
            credit_view_entries.append(entry)

        # Sort Credit View entries by cardholder first, then by date in ASC order
        credit_view_entries.sort(key=lambda x: (x.get("cardholder") or "", x.get("date") or ""))

        return ReconciliationResult(
            matched_pairs=matched_pairs,
            unmatched_card_txs=unmatched_card_txs,
            zaim_view_entries=zaim_view_entries,
            credit_view_entries=credit_view_entries,
        )

    def _accounts_match(self, card_company: str, zaim_account: str) -> bool:
        """Check if zaim_account corresponds to card_company."""
        c_norm = card_company.lower().replace(" ", "")
        z_norm = zaim_account.lower().replace(" ", "")

        if "amex" in c_norm and "amex" in z_norm:
            return True
        if "visa" in c_norm and "visa" in z_norm:
            return True
        return c_norm in z_norm or z_norm in c_norm

    def _format_zaim_view_entry(
        self,
        zaim_tx: FinanceLogTransaction,
        status: str,
        matched_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        d = zaim_tx.to_dict()
        d["match_status"] = status
        d["matched_transaction_id"] = matched_id or ""
        return d

    def _find_matching_subset(
        self, candidates: List[FinanceLogTransaction], target_amount: int, max_size: int = 5
    ) -> Optional[List[FinanceLogTransaction]]:
        """Find a subset of candidate Zaim transactions (size 2 to max_size) summing to target_amount."""
        target = abs(target_amount)
        for k in range(2, min(len(candidates), max_size) + 1):
            for combo in itertools.combinations(candidates, k):
                if sum(abs(z.amount) for z in combo) == target:
                    return list(combo)
        return None

    def _format_credit_view_entry(
        self,
        card_tx: CreditCardTransaction,
        status: str,
        matched_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        d = card_tx.to_dict()
        d["match_status"] = status
        d["matched_transaction_id"] = matched_id or ""
        return d
