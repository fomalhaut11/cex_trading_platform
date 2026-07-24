"""Single-writer deterministic account state."""

from __future__ import annotations

from collections import OrderedDict
from enum import StrEnum
from threading import get_ident

from cex_quant.core import AccountId, AssetId, UnixNanos, VenueId
from cex_quant.instruments import InstrumentId

from .contracts import AccountSnapshot, AccountUpdate, Balance, Position


class AccountUpdateDisposition(StrEnum):
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"


class AccountUpdateConflictError(ValueError):
    """The same venue update ID was reused for different content."""


class AccountScopeError(ValueError):
    """An update belongs to a different account or venue."""


class AccountWriterViolationError(RuntimeError):
    """A thread other than the state owner attempted a mutation."""


class AccountState:
    """Mutable single-writer owner that exposes immutable snapshots.

    This class is intentionally lock-free. Runtime composition must assign one
    writer and publish snapshots to readers.
    """

    def __init__(
        self,
        *,
        account_id: AccountId,
        venue: VenueId,
        max_seen_update_ids: int = 4096,
    ) -> None:
        if not account_id:
            raise ValueError("account_id cannot be empty")
        if not venue:
            raise ValueError("venue cannot be empty")
        if max_seen_update_ids <= 0:
            raise ValueError("max_seen_update_ids must be positive")
        self._account_id = account_id
        self._venue = venue
        self._writer_thread_id = get_ident()
        self._max_seen_update_ids = max_seen_update_ids
        self._balances: dict[AssetId, Balance] = {}
        self._positions: dict[InstrumentId, Position] = {}
        self._seen: OrderedDict[str, AccountUpdate] = OrderedDict()
        self._last_event_time_ns: UnixNanos | None = None
        self._last_sequence: int | None = None

    def apply(self, update: AccountUpdate) -> AccountUpdateDisposition:
        """Apply one absolute update atomically."""

        self._assert_writer()
        if update.account_id != self._account_id or update.venue != self._venue:
            raise AccountScopeError("update does not belong to this account state")
        prior = self._seen.get(update.venue_update_id)
        if prior is not None:
            if prior != update:
                raise AccountUpdateConflictError(
                    "venue_update_id was reused for different content"
                )
            return AccountUpdateDisposition.DUPLICATE
        if self._is_out_of_order(update):
            return AccountUpdateDisposition.OUT_OF_ORDER

        next_balances = self._balances.copy()
        next_positions = self._positions.copy()
        next_balances.update((item.asset, item) for item in update.balances)
        next_positions.update(
            (item.instrument_id, item) for item in update.positions
        )
        self._balances = next_balances
        self._positions = next_positions
        self._last_event_time_ns = UnixNanos(
            max(
                self._last_event_time_ns or update.event_time_ns,
                update.event_time_ns,
            )
        )
        if update.sequence is not None:
            self._last_sequence = update.sequence
        self._remember(update)
        return AccountUpdateDisposition.APPLIED

    def snapshot(self) -> AccountSnapshot:
        """Freeze current state with stable asset/instrument ordering."""

        balances = tuple(
            sorted(self._balances.values(), key=lambda item: str(item.asset))
        )
        positions = tuple(
            sorted(
                self._positions.values(),
                key=lambda item: str(item.instrument_id),
            )
        )
        return AccountSnapshot(
            account_id=self._account_id,
            venue=self._venue,
            balances=balances,
            positions=positions,
            as_of_time_ns=self._last_event_time_ns,
            sequence=self._last_sequence,
        )

    def _is_out_of_order(self, update: AccountUpdate) -> bool:
        if self._last_sequence is not None:
            return (
                update.sequence is None
                or update.sequence <= self._last_sequence
            )
        if update.sequence is not None:
            return False
        return (
            self._last_event_time_ns is not None
            and update.event_time_ns < self._last_event_time_ns
        )

    def _remember(self, update: AccountUpdate) -> None:
        self._seen[update.venue_update_id] = update
        if len(self._seen) > self._max_seen_update_ids:
            self._seen.popitem(last=False)

    def _assert_writer(self) -> None:
        if get_ident() != self._writer_thread_id:
            raise AccountWriterViolationError(
                "account state may only be mutated by its owner thread"
            )


__all__ = [
    "AccountScopeError",
    "AccountState",
    "AccountUpdateConflictError",
    "AccountUpdateDisposition",
    "AccountWriterViolationError",
]
