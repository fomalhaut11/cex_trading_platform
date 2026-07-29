"""Single-writer durable Accounting ledger state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import get_ident

from cex_quant.core import (
    FinancialFactId,
    FinancialObservationId,
    LedgerAccountId,
    LedgerTransactionId,
    Money,
    UnixNanos,
)

from .codec import observation_checksum, observed_fact_checksum
from .facts import ObservedFinancialFact
from .journal import (
    AccountingJournal,
    AccountingJournalEntry,
    AccountingJournalError,
)
from .mapping import LedgerMappingPolicy, map_financial_fact
from .model import (
    LedgerAccount,
    LedgerBalance,
    LedgerTransaction,
    LedgerTransactionDraft,
    LedgerTransactionType,
)
from .reversal import create_reversal_draft


class LedgerIngestDisposition(StrEnum):
    POSTED = "posted"
    REVERSED = "reversed"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    EXISTING_FACT_NEW_OBSERVATION = "existing_fact_new_observation"


class AccountingLedgerError(RuntimeError):
    pass


class AccountingIdentityConflictError(AccountingLedgerError):
    pass


class AccountingPersistenceError(AccountingLedgerError):
    pass


class AccountingRecoveryError(AccountingLedgerError):
    pass


class AccountingWriterViolationError(AccountingLedgerError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerIngestResult:
    disposition: LedgerIngestDisposition
    transactions: tuple[LedgerTransaction, ...]
    ledger_sequence: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountingLedgerView:
    fact_count: int
    observation_count: int
    transactions: tuple[LedgerTransaction, ...]
    balances: tuple[LedgerBalance, ...]
    ledger_sequence: int
    healthy: bool
    error_type: str | None
    error_message: str | None


class AccountingLedger:
    """Converge observed facts and publish state only after durable append."""

    def __init__(
        self,
        journal: AccountingJournal,
        *,
        mapping_policy: LedgerMappingPolicy,
    ) -> None:
        self._journal = journal
        self._mapping_policy = mapping_policy
        self._writer_thread_id = get_ident()
        self._failure: BaseException | None = None
        self._fact_checksums: dict[FinancialFactId, str] = {}
        self._observation_checksums: dict[FinancialObservationId, str] = {}
        self._transactions: dict[LedgerTransactionId, LedgerTransaction] = {}
        self._transaction_order: list[LedgerTransactionId] = []
        self._reversals: dict[LedgerTransactionId, LedgerTransactionId] = {}
        self._accounts: dict[LedgerAccountId, LedgerAccount] = {}
        self._balances: dict[LedgerAccountId, Money] = {}
        self._ledger_sequence = 0
        try:
            for entry in journal.read():
                self._apply_entry(entry, replay=True)
        except (AccountingJournalError, AccountingLedgerError) as error:
            self._failure = error
            raise AccountingRecoveryError(
                f"Accounting journal replay failed: {error}"
            ) from error

    @property
    def mapping_policy(self) -> LedgerMappingPolicy:
        return self._mapping_policy

    def ingest(
        self,
        observed: ObservedFinancialFact,
        *,
        posted_at_ns: UnixNanos,
    ) -> LedgerIngestResult:
        self._assert_writer()
        self._raise_if_failed()
        if posted_at_ns < 0:
            raise ValueError("posted_at_ns cannot be negative")
        observation_id = observed.observation.observation_id
        incoming_observation_checksum = observation_checksum(
            observed.observation
        )
        prior_observation_checksum = self._observation_checksums.get(
            observation_id
        )
        if prior_observation_checksum is not None:
            if prior_observation_checksum != incoming_observation_checksum:
                self._latch_and_raise_conflict(
                    "same observation identity has changed content"
                )
            return LedgerIngestResult(
                disposition=LedgerIngestDisposition.DUPLICATE_OBSERVATION,
                transactions=(),
                ledger_sequence=self._ledger_sequence,
            )

        fact_id = observed.fact.metadata.fact_id
        incoming_fact_checksum = observed_fact_checksum(observed)
        prior_fact_checksum = self._fact_checksums.get(fact_id)
        if prior_fact_checksum is not None:
            if prior_fact_checksum != incoming_fact_checksum:
                self._latch_and_raise_conflict(
                    "same financial fact identity has changed content"
                )
            entry = AccountingJournalEntry(observed=observed, transactions=())
            self._append_then_apply(entry)
            return LedgerIngestResult(
                disposition=(
                    LedgerIngestDisposition.EXISTING_FACT_NEW_OBSERVATION
                ),
                transactions=(),
                ledger_sequence=self._ledger_sequence,
            )

        drafts = map_financial_fact(observed.fact, self._mapping_policy)
        transactions = self._commit_drafts(
            drafts,
            posted_at_ns=posted_at_ns,
        )
        entry = AccountingJournalEntry(
            observed=observed,
            transactions=transactions,
        )
        self._append_then_apply(entry)
        return LedgerIngestResult(
            disposition=LedgerIngestDisposition.POSTED,
            transactions=transactions,
            ledger_sequence=self._ledger_sequence,
        )

    def reverse(
        self,
        observed: ObservedFinancialFact,
        *,
        transaction_id: LedgerTransactionId,
        posted_at_ns: UnixNanos,
    ) -> LedgerIngestResult:
        """Durably post one exact compensating transaction.

        ``observed`` is the authenticated correction evidence. The original
        transaction remains immutable and can be reversed at most once.
        """

        self._assert_writer()
        self._raise_if_failed()
        if posted_at_ns < 0:
            raise ValueError("posted_at_ns cannot be negative")
        observation_id = observed.observation.observation_id
        incoming_observation_checksum = observation_checksum(
            observed.observation
        )
        prior_observation_checksum = self._observation_checksums.get(
            observation_id
        )
        if prior_observation_checksum is not None:
            if prior_observation_checksum != incoming_observation_checksum:
                self._latch_and_raise_conflict(
                    "same observation identity has changed content"
                )
            return LedgerIngestResult(
                disposition=LedgerIngestDisposition.DUPLICATE_OBSERVATION,
                transactions=(),
                ledger_sequence=self._ledger_sequence,
            )

        fact_id = observed.fact.metadata.fact_id
        incoming_fact_checksum = observed_fact_checksum(observed)
        prior_fact_checksum = self._fact_checksums.get(fact_id)
        if prior_fact_checksum is not None:
            if prior_fact_checksum != incoming_fact_checksum:
                self._latch_and_raise_conflict(
                    "same financial fact identity has changed content"
                )
            if not self._fact_reversed_transaction(
                fact_id=fact_id,
                transaction_id=transaction_id,
            ):
                self._latch_and_raise_conflict(
                    "financial fact was already used for another posting"
                )
            entry = AccountingJournalEntry(observed=observed, transactions=())
            self._append_then_apply(entry)
            return LedgerIngestResult(
                disposition=(
                    LedgerIngestDisposition.EXISTING_FACT_NEW_OBSERVATION
                ),
                transactions=(),
                ledger_sequence=self._ledger_sequence,
            )

        try:
            original = self._transactions[transaction_id]
        except KeyError:
            raise KeyError(
                f"unknown ledger transaction: {transaction_id}"
            ) from None
        if transaction_id in self._reversals:
            raise AccountingIdentityConflictError(
                f"ledger transaction is already reversed: {transaction_id}"
            )
        draft = create_reversal_draft(
            original,
            correction_fact_id=fact_id,
            effective_time_ns=observed.fact.metadata.effective_time_ns,
            mapping_policy_version=self._mapping_policy.version,
        )
        transactions = self._commit_drafts(
            (draft,),
            posted_at_ns=posted_at_ns,
        )
        entry = AccountingJournalEntry(
            observed=observed,
            transactions=transactions,
        )
        self._append_then_apply(entry)
        return LedgerIngestResult(
            disposition=LedgerIngestDisposition.REVERSED,
            transactions=transactions,
            ledger_sequence=self._ledger_sequence,
        )

    def transaction(
        self,
        transaction_id: LedgerTransactionId,
    ) -> LedgerTransaction:
        try:
            return self._transactions[transaction_id]
        except KeyError:
            raise KeyError(f"unknown ledger transaction: {transaction_id}") from None

    def view(self) -> AccountingLedgerView:
        transactions = tuple(
            self._transactions[item] for item in self._transaction_order
        )
        balances = tuple(
            LedgerBalance(
                account=self._accounts[account_id],
                balance=self._balances[account_id],
            )
            for account_id in sorted(self._accounts, key=str)
        )
        failure = self._failure
        return AccountingLedgerView(
            fact_count=len(self._fact_checksums),
            observation_count=len(self._observation_checksums),
            transactions=transactions,
            balances=balances,
            ledger_sequence=self._ledger_sequence,
            healthy=failure is None,
            error_type=None if failure is None else type(failure).__name__,
            error_message=None if failure is None else str(failure),
        )

    def _append_then_apply(self, entry: AccountingJournalEntry) -> None:
        try:
            self._journal.append(entry)
        except BaseException as error:
            self._failure = error
            raise AccountingPersistenceError(
                f"Accounting journal append failed: {error}"
            ) from error
        try:
            self._apply_entry(entry, replay=False)
        except AccountingLedgerError as error:
            self._failure = error
            raise

    def _apply_entry(
        self,
        entry: AccountingJournalEntry,
        *,
        replay: bool,
    ) -> None:
        observed = entry.observed
        observation_id = observed.observation.observation_id
        if observation_id in self._observation_checksums:
            raise AccountingRecoveryError(
                "Accounting journal contains duplicate observation identity"
            )
        fact_id = observed.fact.metadata.fact_id
        fact_checksum = observed_fact_checksum(observed)
        existing_fact_checksum = self._fact_checksums.get(fact_id)
        if existing_fact_checksum is None:
            if not entry.transactions:
                raise AccountingRecoveryError(
                    "new financial fact has no ledger transaction"
                )
            self._fact_checksums[fact_id] = fact_checksum
        else:
            if existing_fact_checksum != fact_checksum:
                raise AccountingRecoveryError(
                    "Accounting journal fact identity conflict"
                )
            if entry.transactions:
                raise AccountingRecoveryError(
                    "existing financial fact was posted more than once"
                )

        for transaction in entry.transactions:
            if transaction.transaction_id in self._transactions:
                raise AccountingRecoveryError(
                    "Accounting journal transaction identity collision"
                )
            expected_sequence = self._ledger_sequence + 1
            if transaction.ledger_sequence != expected_sequence:
                raise AccountingRecoveryError(
                    "Accounting ledger sequence is not contiguous"
                )
            if fact_id not in transaction.source_fact_ids:
                raise AccountingRecoveryError(
                    "ledger transaction omits source fact"
                )
            self._apply_transaction(transaction)
        self._observation_checksums[observation_id] = observation_checksum(
            observed.observation
        )
        if replay and entry.transactions:
            posted_times = {item.posted_at_ns for item in entry.transactions}
            if len(posted_times) != 1:
                raise AccountingRecoveryError(
                    "one journal entry has inconsistent posting times"
                )

    def _apply_transaction(self, transaction: LedgerTransaction) -> None:
        self._validate_reversal(transaction)
        self._transactions[transaction.transaction_id] = transaction
        self._transaction_order.append(transaction.transaction_id)
        if transaction.reverses_transaction_id is not None:
            self._reversals[
                transaction.reverses_transaction_id
            ] = transaction.transaction_id
        self._ledger_sequence = transaction.ledger_sequence
        for posting in transaction.postings:
            account_id = posting.account.ledger_account_id
            existing_account = self._accounts.get(account_id)
            if existing_account is not None and existing_account != posting.account:
                raise AccountingRecoveryError(
                    "ledger account identity has changed content"
                )
            self._accounts[account_id] = posting.account
            current = self._balances.get(
                account_id,
                Money(raw=0, scale=posting.signed_amount.scale),
            )
            self._balances[account_id] = _add_money(
                current,
                posting.signed_amount,
            )

    def _validate_reversal(self, transaction: LedgerTransaction) -> None:
        reversed_id = transaction.reverses_transaction_id
        if transaction.transaction_type is LedgerTransactionType.REVERSAL:
            if reversed_id is None:
                raise AccountingRecoveryError(
                    "reversal transaction omits original transaction identity"
                )
        elif reversed_id is not None:
            raise AccountingRecoveryError(
                "non-reversal transaction declares reversal identity"
            )
        else:
            return
        if reversed_id in self._reversals:
            raise AccountingRecoveryError(
                "ledger transaction was reversed more than once"
            )
        original = self._transactions.get(reversed_id)
        if original is None:
            raise AccountingRecoveryError(
                "reversal precedes or references unknown transaction"
            )
        if original.transaction_type is LedgerTransactionType.REVERSAL:
            raise AccountingRecoveryError(
                "reversal transaction cannot reverse another reversal"
            )
        if len(original.postings) != len(transaction.postings):
            raise AccountingRecoveryError(
                "reversal posting count differs from original"
            )
        for original_posting, reversal_posting in zip(
            original.postings,
            transaction.postings,
            strict=True,
        ):
            if original_posting.account != reversal_posting.account:
                raise AccountingRecoveryError(
                    "reversal posting account differs from original"
                )
            if (
                original_posting.signed_amount.scale
                != reversal_posting.signed_amount.scale
                or original_posting.signed_amount.raw
                != -reversal_posting.signed_amount.raw
            ):
                raise AccountingRecoveryError(
                    "reversal posting is not the exact economic inverse"
                )

    def _commit_drafts(
        self,
        drafts: tuple[LedgerTransactionDraft, ...],
        *,
        posted_at_ns: UnixNanos,
    ) -> tuple[LedgerTransaction, ...]:
        return tuple(
            LedgerTransaction(
                transaction_id=draft.transaction_id,
                source_fact_ids=draft.source_fact_ids,
                transaction_type=draft.transaction_type,
                postings=draft.postings,
                effective_time_ns=draft.effective_time_ns,
                posted_at_ns=posted_at_ns,
                ledger_sequence=self._ledger_sequence + index,
                mapping_policy_version=draft.mapping_policy_version,
                reverses_transaction_id=draft.reverses_transaction_id,
            )
            for index, draft in enumerate(drafts, start=1)
        )

    def _assert_writer(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise AccountingWriterViolationError(
                "Accounting ledger mutation attempted by non-owner thread"
            )

    def _raise_if_failed(self) -> None:
        if self._failure is not None:
            raise AccountingPersistenceError(
                f"Accounting ledger is failed: {self._failure}"
            ) from self._failure

    def _latch_and_raise_conflict(self, message: str) -> None:
        error = AccountingIdentityConflictError(message)
        self._failure = error
        raise error

    def _fact_reversed_transaction(
        self,
        *,
        fact_id: FinancialFactId,
        transaction_id: LedgerTransactionId,
    ) -> bool:
        reversal_id = self._reversals.get(transaction_id)
        if reversal_id is None:
            return False
        reversal = self._transactions[reversal_id]
        return fact_id in reversal.source_fact_ids


def _add_money(first: Money, second: Money) -> Money:
    scale = max(first.scale, second.scale)
    first_raw = first.raw * 10 ** (scale - first.scale)
    second_raw = second.raw * 10 ** (scale - second.scale)
    return Money(raw=first_raw + second_raw, scale=scale)


__all__ = [
    "AccountingIdentityConflictError",
    "AccountingLedger",
    "AccountingLedgerError",
    "AccountingLedgerView",
    "AccountingPersistenceError",
    "AccountingRecoveryError",
    "AccountingWriterViolationError",
    "LedgerIngestDisposition",
    "LedgerIngestResult",
]
