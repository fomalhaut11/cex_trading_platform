"""Pure Carry hedge assessment from authoritative Portfolio position views."""

from __future__ import annotations

from decimal import Decimal

from cex_quant.core import Quantity, UnixNanos
from cex_quant.portfolio import (
    AccountPositionRiskView,
    PositionRiskReadiness,
)

from .funding_arbitrage.model import FundingCarryPair, quantity_to_base
from .model import CarryHedgeAssessment, CarryHedgeState
from .ownership import CarryLegOwnership


def assess_linear_funding_carry_hedge(
    *,
    pair: FundingCarryPair,
    ownership: tuple[CarryLegOwnership, ...],
    positions: tuple[AccountPositionRiskView, ...],
    tolerance_base_quantity: Quantity,
    assessed_at_ns: UnixNanos,
    policy_version: int,
) -> CarryHedgeAssessment:
    """Classify residual Delta without using OMS fill quantities as truth."""

    if tolerance_base_quantity.as_decimal() < 0:
        raise ValueError("hedge tolerance cannot be negative")
    scopes = {
        (item.account_id, item.instrument_id): item
        for item in ownership
    }
    required = (
        (
            pair.spot_account_id,
            pair.spot_instrument_id,
            pair.spot_base_units_per_quantity,
        ),
        (
            pair.perpetual_account_id,
            pair.perpetual_instrument_id,
            pair.perpetual_base_units_per_quantity,
        ),
    )
    if any(
        (account_id, instrument_id) not in scopes
        for account_id, instrument_id, _ in required
    ):
        return _unknown(
            "Carry ownership does not cover both pair legs",
            assessed_at_ns=assessed_at_ns,
            policy_version=policy_version,
        )
    by_account = {item.account_id: item for item in positions}
    base_contributions: list[Decimal] = []
    for account_id, instrument_id, multiplier in required:
        account = by_account.get(account_id)
        if account is None or account.readiness is not PositionRiskReadiness.READY:
            return _unknown(
                "authoritative Portfolio position is not READY",
                assessed_at_ns=assessed_at_ns,
                policy_version=policy_version,
            )
        current = next(
            (
                item.effective_quantity
                for item in account.positions
                if item.instrument_id == instrument_id
            ),
            Quantity.from_str("0"),
        )
        baseline = scopes[(account_id, instrument_id)].baseline_quantity
        owned_quantity = Quantity.from_str(
            format(current.as_decimal() - baseline.as_decimal(), "f")
        )
        base_contributions.append(
            quantity_to_base(
                owned_quantity,
                base_units_per_quantity=multiplier,
            ).as_decimal()
        )
    residual = sum(base_contributions, Decimal(0))
    gross = sum((abs(item) for item in base_contributions), Decimal(0))
    tolerance = tolerance_base_quantity.as_decimal()
    if abs(residual) <= tolerance:
        state = CarryHedgeState.HEDGED
    elif abs(residual) >= max(gross - tolerance, Decimal(0)):
        state = CarryHedgeState.UNHEDGED
    else:
        state = CarryHedgeState.PARTIALLY_HEDGED
    return CarryHedgeAssessment(
        state=state,
        signed_residual_base_quantity=Quantity.from_str(
            format(residual, "f")
        ),
        assessed_at_ns=assessed_at_ns,
        policy_version=policy_version,
    )


def _unknown(
    reason: str,
    *,
    assessed_at_ns: UnixNanos,
    policy_version: int,
) -> CarryHedgeAssessment:
    return CarryHedgeAssessment(
        state=CarryHedgeState.UNKNOWN,
        signed_residual_base_quantity=None,
        assessed_at_ns=assessed_at_ns,
        policy_version=policy_version,
        reason=reason,
    )


__all__ = ["assess_linear_funding_carry_hedge"]
