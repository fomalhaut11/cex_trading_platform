"""Synthetic ADR-011 contracts used only by deterministic offline tests."""

from __future__ import annotations

from dataclasses import dataclass

from cex_quant.core import (
    AccountId,
    ExecutionPermitId,
    ExecutionPlanId,
    GroupActionId,
    ObjectiveTypeId,
    PortfolioApprovalId,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    ExecutionAction,
    ExecutionActionPermit,
    ExecutionPlanRef,
    ExecutionStage,
    ExecutionStagePermit,
    OrderGroupAdmission,
    OrderGroupView,
    OrderSide,
    OrderType,
    PositionSide,
    TimeInForce,
    create_execution_stage,
    create_execution_stage_permit,
    deterministic_group_action_id,
    execution_action_checksum,
    execution_plan_parameters_checksum,
)
from cex_quant.snapshots import DecisionSnapshotId
from cex_quant.strategy import (
    BasketTargetIntent,
    BasketTargetLeg,
    ObjectiveTypeRef,
    basket_target_intent_checksum,
    create_basket_target_intent,
    deterministic_basket_leg_id,
)

ACCOUNT_ID = AccountId("primary")
DECISION_SNAPSHOT_ID = DecisionSnapshotId("decision-snapshot-011")
STRATEGY_ID = StrategyId("generic-multi-leg")
OBJECTIVE = ObjectiveTypeRef(
    objective_type_id=ObjectiveTypeId("portfolio.multi_leg"),
    version=1,
)
DEFAULT_PERMIT_EXPIRY = UnixNanos(4_500)


@dataclass(slots=True)
class ManualClock:
    value: int = 1_200

    def __call__(self) -> UnixNanos:
        return UnixNanos(self.value)

    def step(self, amount: int = 10) -> UnixNanos:
        self.value += amount
        return UnixNanos(self.value)


def instrument(
    kind: InstrumentKind,
    symbol: str,
    *,
    venue: str = "BINANCE",
) -> InstrumentId:
    return InstrumentId(
        venue=VenueId(venue),
        kind=kind,
        symbol=symbol,
    )


def leg(
    kind: InstrumentKind,
    symbol: str,
    target: str,
    *,
    account_id: AccountId = ACCOUNT_ID,
    venue: str = "BINANCE",
) -> BasketTargetLeg:
    instrument_id = instrument(kind, symbol, venue=venue)
    return BasketTargetLeg(
        leg_id=deterministic_basket_leg_id(
            decision_snapshot_id=DECISION_SNAPSHOT_ID,
            account_id=account_id,
            instrument_id=instrument_id,
        ),
        account_id=account_id,
        instrument_id=instrument_id,
        target_quantity=Quantity.from_str(target),
    )


def two_leg_basket() -> BasketTargetIntent:
    return _basket(
        (
            leg(InstrumentKind.SPOT, "BTCUSDT", "10"),
            leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-10"),
        )
    )


def three_leg_basket() -> BasketTargetIntent:
    return _basket(
        (
            leg(InstrumentKind.OPTION, "BTC-30000-C", "10"),
            leg(InstrumentKind.OPTION, "BTC-35000-C", "-10"),
            leg(InstrumentKind.PERPETUAL, "BTCUSDT", "-0.35"),
        )
    )


def four_leg_basket() -> BasketTargetIntent:
    return _basket(
        (
            leg(InstrumentKind.OPTION, "BTC-30000-C", "10"),
            leg(InstrumentKind.OPTION, "BTC-30000-P", "-10"),
            leg(InstrumentKind.SPOT, "BTCUSDT", "-10"),
            leg(InstrumentKind.PERPETUAL, "BTCUSDT", "10"),
        )
    )


def cross_venue_basket() -> BasketTargetIntent:
    return _basket(
        (
            leg(
                InstrumentKind.SPOT,
                "BTCUSDT",
                "10",
                account_id=AccountId("binance-primary"),
            ),
            leg(
                InstrumentKind.PERPETUAL,
                "BTC-USDT-SWAP",
                "-10",
                account_id=AccountId("okx-primary"),
                venue="OKX",
            ),
        )
    )


def max_leg_basket() -> BasketTargetIntent:
    return _basket(
        tuple(
            leg(InstrumentKind.OPTION, f"BTC-{30_000 + index}-C", "1")
            for index in range(16)
        )
    )


def admission(
    basket: BasketTargetIntent | None = None,
    *,
    approval_id: str = "portfolio-approval-011",
) -> OrderGroupAdmission:
    value = basket or two_leg_basket()
    return OrderGroupAdmission(
        approval_id=PortfolioApprovalId(approval_id),
        basket=value,
        basket_checksum=basket_target_intent_checksum(value),
        approved_at_ns=UnixNanos(1_100),
        valid_until_ns=UnixNanos(4_800),
        risk_policy_version=7,
    )


def execution_plan() -> ExecutionPlanRef:
    return ExecutionPlanRef(
        execution_plan_id=ExecutionPlanId("sequential-one-in-flight"),
        version=3,
        parameters_checksum=execution_plan_parameters_checksum(
            {"max_working_actions": 1, "price_policy": "passive_then_cross"}
        ),
    )


def action_for(
    view: OrderGroupView,
    *,
    leg_index: int,
    now_ns: UnixNanos,
    leg_attempt_sequence: int = 1,
    quantity: str = "1",
    action_kind: str = "market_attempt",
) -> ExecutionAction:
    leg_view = view.legs[leg_index]
    side = (
        OrderSide.BUY if leg_view.target_quantity.as_decimal() >= 0 else OrderSide.SELL
    )
    action_id = deterministic_group_action_id(
        group_id=view.order_group_id,
        expected_group_revision=view.revision,
        basket_leg_id=leg_view.basket_leg_id,
        execution_plan=view.execution_plan,
        action_kind=action_kind,
        leg_attempt_sequence=leg_attempt_sequence,
    )
    return ExecutionAction(
        group_id=view.order_group_id,
        expected_group_revision=view.revision,
        action_id=GroupActionId(action_id),
        basket_leg_id=leg_view.basket_leg_id,
        account_id=leg_view.account_id,
        instrument_id=leg_view.instrument_id,
        side=side,
        order_type=OrderType.MARKET,
        quantity=Quantity.from_str(quantity),
        time_in_force=TimeInForce.GTC,
        limit_price=None,
        stop_price=None,
        reduce_only=False,
        post_only=False,
        position_side=PositionSide.NET,
        execution_plan=view.execution_plan,
        created_at_ns=now_ns,
    )


def permit_for(
    action: ExecutionAction,
    *,
    issued_at_ns: UnixNanos,
    valid_until_ns: UnixNanos = DEFAULT_PERMIT_EXPIRY,
    permit_id: str = "execution-permit-011",
) -> ExecutionActionPermit:
    return ExecutionActionPermit(
        permit_id=ExecutionPermitId(permit_id),
        group_id=action.group_id,
        expected_group_revision=action.expected_group_revision,
        action_id=action.action_id,
        action_checksum=execution_action_checksum(action),
        risk_snapshot_id=DecisionSnapshotId("risk-snapshot-011"),
        issued_at_ns=issued_at_ns,
        valid_until_ns=valid_until_ns,
        risk_policy_version=8,
    )


def stage_for(
    view: OrderGroupView,
    *,
    leg_indices: tuple[int, ...] = (0,),
    now_ns: UnixNanos,
    dispatch_width: int = 1,
) -> ExecutionStage:
    actions = tuple(
        action_for(
            view,
            leg_index=leg_index,
            now_ns=now_ns,
            action_kind=f"stage_market_attempt_{leg_index}",
        )
        for leg_index in leg_indices
    )
    return create_execution_stage(
        group_id=view.order_group_id,
        base_group_revision=view.revision,
        execution_plan=view.execution_plan,
        actions=actions,
        dispatch_width=dispatch_width,
        created_at_ns=now_ns,
    )


def stage_permit_for(
    stage: ExecutionStage,
    *,
    issued_at_ns: UnixNanos,
    valid_until_ns: UnixNanos = DEFAULT_PERMIT_EXPIRY,
) -> ExecutionStagePermit:
    action_permits = tuple(
        permit_for(
            action,
            issued_at_ns=issued_at_ns,
            valid_until_ns=valid_until_ns,
            permit_id=(
                "execution-stage-action-permit-"
                f"{index}-{str(action.action_id)[:16]}"
            ),
        )
        for index, action in enumerate(stage.actions, start=1)
    )
    return create_execution_stage_permit(
        stage=stage,
        action_permits=action_permits,
        partial_execution_envelope_checksum="0" * 64,
        risk_snapshot_id=action_permits[0].risk_snapshot_id,
        issued_at_ns=issued_at_ns,
        valid_until_ns=valid_until_ns,
        risk_policy_version=action_permits[0].risk_policy_version,
    )


def _basket(legs: tuple[BasketTargetLeg, ...]) -> BasketTargetIntent:
    return create_basket_target_intent(
        strategy_id=STRATEGY_ID,
        decision_snapshot_id=DECISION_SNAPSHOT_ID,
        objective=OBJECTIVE,
        legs=legs,
        decision_time_ns=UnixNanos(1_000),
        valid_until_ns=UnixNanos(5_000),
        policy_version=4,
        reason="generic portfolio target",
    )
