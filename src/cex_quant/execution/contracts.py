"""Venue-neutral execution cancellation and immediate gateway results."""

from dataclasses import dataclass
from enum import StrEnum

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelOrder:
    """Cancel by the original idempotent client order identifier."""

    account_id: AccountId
    instrument_id: InstrumentId
    client_order_id: ClientOrderId

    def __post_init__(self) -> None:
        _validate_identifier(self.client_order_id, field_name="client_order_id")


class ExecutionOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True, kw_only=True)
class SubmitResult:
    """Immediate submit result, not canonical order lifecycle state."""

    client_order_id: ClientOrderId
    outcome: ExecutionOutcome
    venue_order_id: VenueOrderId | None = None
    rejection_code: str | None = None
    rejection_message: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.client_order_id, field_name="client_order_id")
        _validate_result(self.outcome, self.rejection_code, self.rejection_message)


@dataclass(frozen=True, slots=True, kw_only=True)
class CancelResult:
    """Immediate cancel result, not canonical order lifecycle state."""

    client_order_id: ClientOrderId
    outcome: ExecutionOutcome
    venue_order_id: VenueOrderId | None = None
    rejection_code: str | None = None
    rejection_message: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.client_order_id, field_name="client_order_id")
        _validate_result(self.outcome, self.rejection_code, self.rejection_message)


def _validate_identifier(value: str, *, field_name: str) -> None:
    if not value or value.strip() != value:
        raise ValueError(f"{field_name} must be a non-empty trimmed string")


def _validate_result(
    outcome: ExecutionOutcome,
    rejection_code: str | None,
    rejection_message: str | None,
) -> None:
    if not isinstance(outcome, ExecutionOutcome):
        raise ValueError("outcome must be an ExecutionOutcome")
    has_rejection = rejection_code is not None or rejection_message is not None
    if outcome is ExecutionOutcome.REJECTED and (
        rejection_code is None or rejection_message is None
    ):
        raise ValueError("rejected result requires rejection_code and message")
    if outcome is not ExecutionOutcome.REJECTED and has_rejection:
        raise ValueError("only a rejected result can contain rejection details")


__all__ = [
    "CancelOrder",
    "CancelResult",
    "ExecutionOutcome",
    "SubmitResult",
]
