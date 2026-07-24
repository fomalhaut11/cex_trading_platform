"""Acceptance scenario for durable OMS restart and venue reconciliation."""

import tempfile
import unittest
from pathlib import Path

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    StrategyId,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.execution import (
    QueryOrder,
    normalize_binance_order_query,
    normalize_binance_user_order_update,
)
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    JsonLinesOmsJournal,
    OrderReconciliationSnapshot,
    OrderSide,
    OrderStatus,
    OrderType,
    ReconciliationDisposition,
    ReconciliationSource,
)
from cex_quant.risk import RiskDecision, RiskDecisionStatus
from cex_quant.runtime import (
    CanonicalOmsApplicationService,
    OrderParameters,
    StartupOrderReconciliationCoordinator,
)
from cex_quant.strategy import PositionTargetIntent

INSTRUMENT = InstrumentId(
    venue=VenueId("BINANCE"),
    kind=InstrumentKind.PERPETUAL,
    symbol="BTCUSDT",
)


class _Accounts:
    def account_id(self, intent: PositionTargetIntent) -> AccountId:
        del intent
        return AccountId("testnet")


class _Identities:
    def approval_id(
        self,
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> str:
        del intent, decision
        return "approval-recovery-1"

    def client_order_id(
        self,
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> ClientOrderId:
        del intent, decision
        return ClientOrderId("recovery-order-1")


class _Orders:
    def parameters(
        self,
        intent: PositionTargetIntent,
        decision: RiskDecision,
    ) -> OrderParameters:
        del intent, decision
        return OrderParameters(
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Quantity.from_str("2"),
            limit_price=Price.from_str("60000"),
        )


def _intent() -> PositionTargetIntent:
    return PositionTargetIntent(
        intent_id=IntentId("intent-recovery-1"),
        strategy_id=StrategyId("strategy-recovery"),
        instrument_id=INSTRUMENT,
        target_quantity=Quantity.from_str("2"),
        decision_time_ns=UnixNanos(100),
        valid_until_ns=UnixNanos(1_000),
    )


def _decision() -> RiskDecision:
    intent = _intent()
    return RiskDecision(
        status=RiskDecisionStatus.ALLOW,
        intent=intent,
        reasons=(),
        projected_strategy_position=intent.target_quantity,
        projected_global_position=intent.target_quantity,
        projected_strategy_notional=None,
        projected_global_notional=None,
    )


def _service(journal: JsonLinesOmsJournal) -> CanonicalOmsApplicationService:
    return CanonicalOmsApplicationService(
        accounts=_Accounts(),
        identities=_Identities(),
        orders=_Orders(),
        now_ns=lambda: UnixNanos(150),
        journal=journal,
    )


class OmsRecoveryAcceptanceTests(unittest.TestCase):
    def test_restart_then_rest_and_user_stream_converge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(journal_path) as journal:
                before_crash = _service(journal)
                request = before_crash.create_order(_intent(), _decision())
                before_crash.mark_submitting(
                    request.client_order_id,
                    at_ns=UnixNanos(160),
                )

            with JsonLinesOmsJournal(journal_path) as journal:
                recovered = _service(journal)
                candidates = recovered.reconciliation_candidates()
                self.assertEqual(len(candidates), 1)
                self.assertEqual(
                    candidates[0].status,
                    OrderStatus.SUBMITTING,
                )

                rest = recovered.reconcile(
                    OrderReconciliationSnapshot(
                        source=ReconciliationSource.REST_QUERY,
                        source_update_id="rest-order-42",
                        client_order_id=request.client_order_id,
                        venue_order_id=VenueOrderId("42"),
                        status=OrderStatus.OPEN,
                        cumulative_filled_quantity=Quantity.from_str("0"),
                        observed_at_ns=UnixNanos(200),
                    )
                )
                stream = recovered.reconcile(
                    OrderReconciliationSnapshot(
                        source=ReconciliationSource.USER_STREAM,
                        source_update_id="execution-report-43",
                        client_order_id=request.client_order_id,
                        venue_order_id=VenueOrderId("42"),
                        status=OrderStatus.FILLED,
                        cumulative_filled_quantity=Quantity.from_str("2"),
                        average_fill_price=Price.from_str("59999.5"),
                        observed_at_ns=UnixNanos(220),
                    )
                )

                self.assertEqual(
                    rest.disposition,
                    ReconciliationDisposition.APPLIED,
                )
                self.assertEqual(
                    stream.disposition,
                    ReconciliationDisposition.APPLIED,
                )
                self.assertEqual(stream.order.status, OrderStatus.FILLED)
                self.assertEqual(
                    recovered.reconciliation_candidates(),
                    (),
                )

            with JsonLinesOmsJournal(journal_path) as journal:
                final_restart = _service(journal)
                final = final_restart.order(request.client_order_id)
                self.assertEqual(final.status, OrderStatus.FILLED)
                self.assertEqual(
                    final.cumulative_filled_quantity.as_decimal(),
                    2,
                )

    def test_binance_rest_and_user_stream_payloads_converge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(journal_path) as journal:
                oms = _service(journal)
                request = oms.create_order(_intent(), _decision())
                oms.mark_submitting(
                    request.client_order_id,
                    at_ns=UnixNanos(160),
                )
                rest = normalize_binance_order_query(
                    BinanceProduct.USD_M,
                    {
                        "avgPrice": "0",
                        "clientOrderId": "recovery-order-1",
                        "executedQty": "0",
                        "orderId": 99,
                        "status": "NEW",
                        "updateTime": 1,
                    },
                    received_at_ns=UnixNanos(1_000_000),
                    expected_client_order_id=request.client_order_id,
                )
                stream = normalize_binance_user_order_update(
                    BinanceProduct.USD_M,
                    {
                        "e": "ORDER_TRADE_UPDATE",
                        "E": 3,
                        "T": 2,
                        "o": {
                            "c": "recovery-order-1",
                            "ap": "60000",
                            "x": "TRADE",
                            "X": "FILLED",
                            "i": 99,
                            "z": "2",
                            "t": 7,
                        },
                    },
                    expected_client_order_id=request.client_order_id,
                )

                self.assertEqual(
                    oms.reconcile(rest).disposition,
                    ReconciliationDisposition.APPLIED,
                )
                filled = oms.reconcile(stream)
                self.assertEqual(filled.order.status, OrderStatus.FILLED)

            with JsonLinesOmsJournal(journal_path) as journal:
                recovered = _service(journal)
                self.assertEqual(
                    recovered.order(request.client_order_id).status,
                    OrderStatus.FILLED,
                )


class _QueryGateway:
    def __init__(
        self,
        snapshot: OrderReconciliationSnapshot,
    ) -> None:
        self.snapshot = snapshot

    async def query_order(
        self,
        command: QueryOrder,
    ) -> OrderReconciliationSnapshot:
        self.assert_identity = command.client_order_id
        return self.snapshot


class OmsStartupReconciliationAcceptanceTests(
    unittest.IsolatedAsyncioTestCase
):
    async def test_stream_buffer_and_rest_query_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "oms.jsonl"
            with JsonLinesOmsJournal(journal_path) as journal:
                before_restart = _service(journal)
                request = before_restart.create_order(_intent(), _decision())
                before_restart.mark_submitting(
                    request.client_order_id,
                    at_ns=UnixNanos(160),
                )

            rest = normalize_binance_order_query(
                BinanceProduct.USD_M,
                {
                    "avgPrice": "0",
                    "clientOrderId": "recovery-order-1",
                    "executedQty": "0",
                    "orderId": 99,
                    "status": "NEW",
                    "updateTime": 1,
                },
                received_at_ns=UnixNanos(1_000_000),
            )
            stream = normalize_binance_user_order_update(
                BinanceProduct.USD_M,
                {
                    "e": "ORDER_TRADE_UPDATE",
                    "E": 3,
                    "T": 2,
                    "o": {
                        "c": "recovery-order-1",
                        "ap": "60000",
                        "x": "TRADE",
                        "X": "FILLED",
                        "i": 99,
                        "z": "2",
                        "t": 7,
                    },
                },
            )

            with JsonLinesOmsJournal(journal_path) as journal:
                recovered = _service(journal)
                gateway = _QueryGateway(rest)
                coordinator = StartupOrderReconciliationCoordinator(
                    oms=recovered,
                    gateway=gateway,
                    now_ns=lambda: UnixNanos(3_000_000),
                )
                coordinator.begin_buffering()
                await coordinator.on_stream_snapshot(stream)

                report = await coordinator.reconcile_startup()

                self.assertTrue(report.ready)
                self.assertEqual(
                    recovered.order(request.client_order_id).status,
                    OrderStatus.FILLED,
                )
                self.assertEqual(
                    gateway.assert_identity,
                    request.client_order_id,
                )

            with JsonLinesOmsJournal(journal_path) as journal:
                final = _service(journal)
                self.assertEqual(
                    final.order(request.client_order_id).status,
                    OrderStatus.FILLED,
                )


if __name__ == "__main__":
    unittest.main()
