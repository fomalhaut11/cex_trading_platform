"""Single-writer state for execution-consistent effective positions."""

from __future__ import annotations

import threading
from decimal import Decimal

from cex_quant.core import AccountId, ClientOrderId, EventId, Quantity
from cex_quant.instruments import InstrumentId

from .risk_inputs import (
    AccountPositionRiskView,
    ExecutionCoverage,
    ExecutionPositionEffect,
    ExecutionPositionEffectBatch,
    InstrumentPositionRiskView,
    PositionRiskReadiness,
    ReconciledAccountBaseline,
)


class PortfolioPositionStateError(RuntimeError):
    """Base error for invalid baseline/overlay transitions."""


class PortfolioPositionCoverageError(PortfolioPositionStateError):
    """An OMS journal scan does not continue the accepted coverage."""


class PortfolioPositionConflictError(PortfolioPositionStateError):
    """An execution identity was reused with different content."""


class PortfolioPositionWriterViolationError(PortfolioPositionStateError):
    """More than one thread attempted to mutate effective positions."""


class ExecutionConsistentPositionState:
    """One account's baseline plus only the not-yet-covered fill effects."""

    def __init__(self, account_id: AccountId) -> None:
        if not account_id:
            raise ValueError("account_id cannot be empty")
        self._account_id = account_id
        self._baseline: ReconciledAccountBaseline | None = None
        self._baseline_quantities: dict[InstrumentId, Decimal] = {}
        self._overlay: dict[InstrumentId, Decimal] = {}
        self._effects: dict[EventId, ExecutionPositionEffect] = {}
        self._batches: dict[int, ExecutionPositionEffectBatch] = {}
        self._cumulative_fills: dict[ClientOrderId, Decimal] = {}
        self._fill_signs: dict[ClientOrderId, int] = {}
        self._coverage = ExecutionCoverage(through_oms_journal_sequence=0)
        self._readiness = PositionRiskReadiness.UNRECONCILED
        self._reason = "authoritative account baseline is missing"
        self._writer_thread_id: int | None = None

    @property
    def account_id(self) -> AccountId:
        return self._account_id

    def accept_baseline(
        self,
        baseline: ReconciledAccountBaseline,
        *,
        allow_recovery_reset: bool = False,
    ) -> None:
        """Accept an authoritative baseline without double-counting covered fills."""

        self._claim_writer()
        if baseline.account.account_id != self._account_id:
            raise PortfolioPositionStateError("baseline account does not match state")
        incoming = baseline.coverage.through_oms_journal_sequence
        current = self._coverage.through_oms_journal_sequence
        if incoming < current:
            raise PortfolioPositionCoverageError("baseline coverage regressed")

        incoming_quantities = {
            position.instrument_id: position.quantity.as_decimal()
            for position in baseline.account.positions
        }
        if self._baseline is not None and incoming == current:
            effective = self._effective_quantities()
            if incoming_quantities != effective and not allow_recovery_reset:
                self._readiness = PositionRiskReadiness.DIVERGENT
                self._reason = (
                    "authoritative account positions diverge at the same OMS watermark"
                )
                return

        self._baseline = baseline
        self._baseline_quantities = incoming_quantities
        self._overlay.clear()
        self._effects.clear()
        self._batches.clear()
        self._cumulative_fills.clear()
        self._fill_signs.clear()
        self._coverage = baseline.coverage
        self._readiness = PositionRiskReadiness.READY
        self._reason = ""

    def apply_execution_batch(
        self,
        batch: ExecutionPositionEffectBatch,
    ) -> None:
        """Advance coverage using a complete durable OMS journal scan."""

        self._claim_writer()
        if self._readiness is not PositionRiskReadiness.READY:
            raise PortfolioPositionStateError("position state is not ready")
        previous_batch = self._batches.get(batch.from_sequence_exclusive)
        if previous_batch is not None:
            if previous_batch == batch:
                return
            self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
            self._reason = "OMS execution batch identity conflict"
            raise PortfolioPositionConflictError(self._reason)
        current = self._coverage.through_oms_journal_sequence
        if batch.from_sequence_exclusive != current:
            self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
            self._reason = "OMS execution coverage is not contiguous"
            raise PortfolioPositionCoverageError(self._reason)

        for effect in batch.effects:
            if effect.account_id != self._account_id:
                raise PortfolioPositionStateError(
                    "execution effect account does not match state"
                )
            previous = self._effects.get(effect.effect_id)
            if previous is not None:
                if previous != effect:
                    self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
                    self._reason = "execution effect identity conflict"
                    raise PortfolioPositionConflictError(self._reason)
                continue
            cumulative = effect.cumulative_filled_quantity.as_decimal()
            prior_cumulative = self._cumulative_fills.get(
                effect.client_order_id,
                Decimal(0),
            )
            if cumulative <= prior_cumulative:
                self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
                self._reason = "cumulative fill did not increase"
                raise PortfolioPositionConflictError(self._reason)
            sign = 1 if effect.signed_fill_delta.raw > 0 else -1
            prior_sign = self._fill_signs.get(effect.client_order_id)
            if prior_sign is not None and prior_sign != sign:
                self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
                self._reason = "fill direction changed for one child order"
                raise PortfolioPositionConflictError(self._reason)
            expected_delta = Decimal(sign) * (cumulative - prior_cumulative)
            if effect.signed_fill_delta.as_decimal() != expected_delta:
                self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
                self._reason = "fill increment does not match cumulative progress"
                raise PortfolioPositionConflictError(self._reason)
            self._effects[effect.effect_id] = effect
            self._cumulative_fills[effect.client_order_id] = cumulative
            self._fill_signs[effect.client_order_id] = sign
            self._overlay[effect.instrument_id] = (
                self._overlay.get(effect.instrument_id, Decimal(0))
                + effect.signed_fill_delta.as_decimal()
            )

        self._coverage = ExecutionCoverage(
            through_oms_journal_sequence=batch.through_sequence_inclusive
        )
        self._batches[batch.from_sequence_exclusive] = batch

    def mark_recovery_required(self, reason: str) -> None:
        self._claim_writer()
        if not reason or reason != reason.strip():
            raise ValueError("recovery reason must be non-empty and trimmed")
        self._readiness = PositionRiskReadiness.RECOVERY_REQUIRED
        self._reason = reason

    def view(self) -> AccountPositionRiskView:
        instruments = set(self._baseline_quantities) | set(self._overlay)
        positions = tuple(
            InstrumentPositionRiskView(
                instrument_id=instrument_id,
                baseline_quantity=_quantity(
                    self._baseline_quantities.get(instrument_id, Decimal(0))
                ),
                post_baseline_fill_delta=_quantity(
                    self._overlay.get(instrument_id, Decimal(0))
                ),
                effective_quantity=_quantity(
                    self._baseline_quantities.get(instrument_id, Decimal(0))
                    + self._overlay.get(instrument_id, Decimal(0))
                ),
            )
            for instrument_id in sorted(instruments, key=str)
        )
        return AccountPositionRiskView(
            account_id=self._account_id,
            reconciliation_id=(
                None if self._baseline is None else self._baseline.reconciliation_id
            ),
            observation_id=(
                None if self._baseline is None else self._baseline.observation_id
            ),
            coverage=self._coverage,
            positions=positions,
            readiness=self._readiness,
            reason=self._reason,
        )

    def _effective_quantities(self) -> dict[InstrumentId, Decimal]:
        return {
            instrument_id: (
                self._baseline_quantities.get(instrument_id, Decimal(0))
                + self._overlay.get(instrument_id, Decimal(0))
            )
            for instrument_id in set(self._baseline_quantities) | set(self._overlay)
        }

    def _claim_writer(self) -> None:
        thread_id = threading.get_ident()
        if self._writer_thread_id is None:
            self._writer_thread_id = thread_id
        elif self._writer_thread_id != thread_id:
            raise PortfolioPositionWriterViolationError(
                "effective position state has a different writer"
            )


def _quantity(value: Decimal) -> Quantity:
    return Quantity.from_str(format(value, "f"))


__all__ = [
    "ExecutionConsistentPositionState",
    "PortfolioPositionConflictError",
    "PortfolioPositionCoverageError",
    "PortfolioPositionStateError",
    "PortfolioPositionWriterViolationError",
]
