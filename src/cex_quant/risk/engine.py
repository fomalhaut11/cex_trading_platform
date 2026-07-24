"""Pure, deterministic pre-trade evaluation of position target intents."""

from decimal import Decimal

from cex_quant.core import Money, Price, Quantity, UnixNanos
from cex_quant.features import FeatureQuality
from cex_quant.instruments import (
    ContractValueType,
    FutureSpecification,
    Instrument,
    InstrumentStatus,
    OptionSpecification,
    PerpetualSpecification,
    SpotSpecification,
)
from cex_quant.observability import HealthStatus
from cex_quant.strategy import PositionTargetIntent

from .model import (
    RiskContext,
    RiskDecision,
    RiskDecisionStatus,
    RiskLimits,
    RiskRejectReason,
)


class RiskEngine:
    """Stateless policy: caller owns positions and rolling intent counters."""

    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits

    @property
    def limits(self) -> RiskLimits:
        return self._limits

    def evaluate(
        self,
        intent: PositionTargetIntent,
        context: RiskContext,
    ) -> RiskDecision:
        """Approve or reject an intent using only the supplied snapshot."""

        target = intent.target_quantity.as_decimal()
        current_strategy = context.current_strategy_position.as_decimal()
        current_global = context.current_global_position.as_decimal()
        projected_global = current_global + (target - current_strategy)

        reasons = self._validate_inputs(intent, context)
        strategy_notional: Money | None = None
        global_notional: Money | None = None
        if not reasons:
            try:
                strategy_notional = _money(
                    _notional(context.instrument, target, context.reference_price)
                )
                global_notional = _money(
                    _notional(
                        context.instrument,
                        projected_global,
                        context.reference_price,
                    )
                )
            except UnsupportedNotionalModelError:
                reasons.append(RiskRejectReason.UNSUPPORTED_NOTIONAL_MODEL)

        if not reasons:
            self._apply_limits(
                target=target,
                projected_global=projected_global,
                strategy_notional=strategy_notional,
                global_notional=global_notional,
                context=context,
                reasons=reasons,
            )

        status = (
            RiskDecisionStatus.REJECT
            if reasons
            else RiskDecisionStatus.ALLOW
        )
        return RiskDecision(
            status=status,
            intent=intent,
            reasons=tuple(reasons),
            projected_strategy_position=intent.target_quantity,
            projected_global_position=_quantity(projected_global),
            projected_strategy_notional=strategy_notional,
            projected_global_notional=global_notional,
        )

    def _validate_inputs(
        self,
        intent: PositionTargetIntent,
        context: RiskContext,
    ) -> list[RiskRejectReason]:
        reasons: list[RiskRejectReason] = []
        now = int(context.now_ns)
        if int(intent.decision_time_ns) > now:
            reasons.append(RiskRejectReason.INTENT_FROM_FUTURE)
        if (
            intent.valid_until_ns is not None
            and now > int(intent.valid_until_ns)
        ):
            reasons.append(RiskRejectReason.INTENT_EXPIRED)
        if intent.strategy_id != context.strategy_id:
            reasons.append(RiskRejectReason.STRATEGY_MISMATCH)
        if intent.instrument_id != context.instrument.instrument_id:
            reasons.append(RiskRejectReason.INSTRUMENT_MISMATCH)
        if context.instrument.status is not InstrumentStatus.ACTIVE:
            reasons.append(RiskRejectReason.INSTRUMENT_NOT_ACTIVE)
        if context.clock_status is not HealthStatus.HEALTHY:
            reasons.append(RiskRejectReason.CLOCK_UNHEALTHY)
        if context.reference_price is None:
            reasons.append(RiskRejectReason.REFERENCE_PRICE_MISSING)
        elif context.reference_price.raw <= 0:
            reasons.append(RiskRejectReason.REFERENCE_PRICE_INVALID)

        self._check_freshness(
            as_of_ns=context.market_data_as_of_ns,
            valid_until_ns=None,
            now=now,
            max_age_ns=self._limits.max_market_data_age_ns,
            missing_reason=RiskRejectReason.MARKET_DATA_MISSING,
            stale_reason=RiskRejectReason.MARKET_DATA_STALE,
            reasons=reasons,
        )
        if self._limits.require_fresh_features:
            if (
                context.feature_quality is None
                and context.feature_data_as_of_ns is not None
            ):
                reasons.append(RiskRejectReason.FEATURE_DATA_MISSING)
            elif context.feature_quality is not FeatureQuality.GOOD:
                reasons.append(RiskRejectReason.FEATURE_DATA_INVALID)
            self._check_freshness(
                as_of_ns=context.feature_data_as_of_ns,
                valid_until_ns=context.feature_data_valid_until_ns,
                now=now,
                max_age_ns=self._limits.max_feature_data_age_ns,
                missing_reason=RiskRejectReason.FEATURE_DATA_MISSING,
                stale_reason=RiskRejectReason.FEATURE_DATA_STALE,
                reasons=reasons,
            )
        return reasons

    @staticmethod
    def _check_freshness(
        *,
        as_of_ns: UnixNanos | None,
        valid_until_ns: UnixNanos | None,
        now: int,
        max_age_ns: int,
        missing_reason: RiskRejectReason,
        stale_reason: RiskRejectReason,
        reasons: list[RiskRejectReason],
    ) -> None:
        if as_of_ns is None:
            reasons.append(missing_reason)
            return
        as_of = int(as_of_ns)
        if as_of > now or now - as_of > max_age_ns:
            reasons.append(stale_reason)
            return
        if valid_until_ns is not None and now > int(valid_until_ns):
            reasons.append(stale_reason)

    def _apply_limits(
        self,
        *,
        target: Decimal,
        projected_global: Decimal,
        strategy_notional: Money | None,
        global_notional: Money | None,
        context: RiskContext,
        reasons: list[RiskRejectReason],
    ) -> None:
        limits = self._limits
        if (
            limits.max_abs_strategy_position is not None
            and abs(target)
            > limits.max_abs_strategy_position.as_decimal()
        ):
            reasons.append(RiskRejectReason.STRATEGY_POSITION_LIMIT)
        if (
            limits.max_abs_global_position is not None
            and abs(projected_global)
            > limits.max_abs_global_position.as_decimal()
        ):
            reasons.append(RiskRejectReason.GLOBAL_POSITION_LIMIT)
        if (
            limits.max_strategy_notional is not None
            and strategy_notional is not None
            and strategy_notional.as_decimal()
            > limits.max_strategy_notional.as_decimal()
        ):
            reasons.append(RiskRejectReason.STRATEGY_NOTIONAL_LIMIT)
        if (
            limits.max_global_notional is not None
            and global_notional is not None
            and global_notional.as_decimal()
            > limits.max_global_notional.as_decimal()
        ):
            reasons.append(RiskRejectReason.GLOBAL_NOTIONAL_LIMIT)
        if (
            limits.max_strategy_intents_per_window is not None
            and context.strategy_intents_in_window
            >= limits.max_strategy_intents_per_window
        ):
            reasons.append(RiskRejectReason.STRATEGY_INTENT_RATE_LIMIT)
        if (
            limits.max_global_intents_per_window is not None
            and context.global_intents_in_window
            >= limits.max_global_intents_per_window
        ):
            reasons.append(RiskRejectReason.GLOBAL_INTENT_RATE_LIMIT)


class UnsupportedNotionalModelError(ValueError):
    """Raised internally when a product cannot be valued unambiguously."""


def _notional(
    instrument: Instrument,
    signed_quantity: Decimal,
    reference_price: Price | None,
) -> Decimal:
    if reference_price is None:
        raise UnsupportedNotionalModelError
    quantity = abs(signed_quantity)
    price = reference_price.as_decimal()
    specification = instrument.specification
    if isinstance(specification, SpotSpecification):
        return quantity * price
    if isinstance(
        specification,
        (PerpetualSpecification, FutureSpecification),
    ):
        size = specification.contract_size.as_decimal()
        if specification.value_type is ContractValueType.LINEAR:
            return quantity * size * price
        if specification.value_type is ContractValueType.INVERSE:
            return quantity * size
        raise UnsupportedNotionalModelError
    if isinstance(specification, OptionSpecification):
        return quantity * specification.contract_size.as_decimal() * price
    raise UnsupportedNotionalModelError


def _quantity(value: Decimal) -> Quantity:
    return Quantity.from_str(format(value, "f"))


def _money(value: Decimal) -> Money:
    return Money.from_str(format(value, "f"))


__all__ = ["RiskEngine"]
