import asyncio
from unittest import IsolatedAsyncioTestCase

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.execution import ExecutionQueryError
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import (
    OrderReconciliationSnapshot,
    OrderRequest,
    OrderSide,
    OrderStateMachine,
    OrderStatus,
    OrderType,
    ReconciliationDisposition,
    ReconciliationResult,
    ReconciliationSource,
    UpdateDisposition,
)
from cex_quant.runtime import (
    StartupOrderReconciliationCoordinator,
    StartupReconciliationError,
    StartupReconciliationState,
)


def request() -> OrderRequest:
    return OrderRequest(
        client_order_id=ClientOrderId("startup-1"),
        approval_id="approval-1",
        intent_id=IntentId("intent-1"),
        account_id=AccountId("testnet"),
        instrument_id=InstrumentId(
            venue=VenueId("BINANCE"),
            kind=InstrumentKind.PERPETUAL,
            symbol="BTCUSDT",
        ),
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Quantity.from_str("2"),
        created_at_ns=UnixNanos(100),
        limit_price=Price.from_str("60000"),
    )


def snapshot(
    *,
    source: ReconciliationSource,
    update_id: str,
    status: OrderStatus,
    filled: str,
    observed_at_ns: int,
) -> OrderReconciliationSnapshot:
    return OrderReconciliationSnapshot(
        source=source,
        source_update_id=update_id,
        client_order_id=ClientOrderId("startup-1"),
        venue_order_id=VenueOrderId("42"),
        status=status,
        cumulative_filled_quantity=Quantity.from_str(filled),
        average_fill_price=(
            Price.from_str("60000") if filled != "0" else None
        ),
        observed_at_ns=UnixNanos(observed_at_ns),
    )


class FakeOms:
    def __init__(self) -> None:
        self.machine = OrderStateMachine(request())
        self.machine.mark_submitting(at_ns=UnixNanos(110))
        self.not_found = 0

    def reconciliation_candidates(self) -> tuple[object, ...]:
        view = self.machine.view()
        return () if view.status is OrderStatus.FILLED else (view,)

    def reconcile(
        self,
        value: OrderReconciliationSnapshot,
    ) -> ReconciliationResult:
        update = self.machine.apply_venue_update(value.as_order_event())
        disposition = (
            ReconciliationDisposition.DUPLICATE
            if update.disposition is UpdateDisposition.DUPLICATE
            else ReconciliationDisposition.APPLIED
        )
        return ReconciliationResult(
            disposition=disposition,
            order=update.after,
        )

    def reconcile_not_found(
        self,
        client_order_id: ClientOrderId,
        *,
        source: ReconciliationSource,
        observed_at_ns: UnixNanos,
    ) -> ReconciliationResult:
        del client_order_id, source, observed_at_ns
        self.not_found += 1
        return ReconciliationResult(
            disposition=ReconciliationDisposition.NOT_FOUND,
            order=self.machine.view(),
            reason="not found",
        )


class DelayedGateway:
    def __init__(
        self,
        response: OrderReconciliationSnapshot | None,
        *,
        error: ExecutionQueryError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def query_order(
        self,
        command: object,
    ) -> OrderReconciliationSnapshot | None:
        del command
        self.entered.set()
        await self.release.wait()
        if self.error is not None:
            raise self.error
        return self.response


class StartupReconciliationTests(IsolatedAsyncioTestCase):
    async def test_buffers_stream_during_query_then_converges_by_time(
        self,
    ) -> None:
        oms = FakeOms()
        gateway = DelayedGateway(
            snapshot(
                source=ReconciliationSource.REST_QUERY,
                update_id="rest-open",
                status=OrderStatus.OPEN,
                filled="0",
                observed_at_ns=200,
            )
        )
        coordinator = StartupOrderReconciliationCoordinator(
            oms=oms,  # type: ignore[arg-type]
            gateway=gateway,  # type: ignore[arg-type]
            now_ns=lambda: UnixNanos(250),
        )
        coordinator.begin_buffering()

        task = asyncio.create_task(coordinator.reconcile_startup())
        await gateway.entered.wait()
        await coordinator.on_stream_snapshot(
            snapshot(
                source=ReconciliationSource.USER_STREAM,
                update_id="stream-fill",
                status=OrderStatus.FILLED,
                filled="2",
                observed_at_ns=220,
            )
        )
        gateway.release.set()
        report = await task

        self.assertTrue(report.ready)
        self.assertEqual(report.stream_observations, 1)
        self.assertEqual(oms.machine.view().status, OrderStatus.FILLED)
        self.assertEqual(
            coordinator.state,
            StartupReconciliationState.LIVE,
        )

    async def test_not_found_and_query_failure_remain_degraded(self) -> None:
        for response, error in (
            (None, None),
            (None, ExecutionQueryError("query unavailable")),
        ):
            with self.subTest(error=error):
                oms = FakeOms()
                gateway = DelayedGateway(response, error=error)
                coordinator = StartupOrderReconciliationCoordinator(
                    oms=oms,  # type: ignore[arg-type]
                    gateway=gateway,  # type: ignore[arg-type]
                    now_ns=lambda: UnixNanos(250),
                )
                coordinator.begin_buffering()
                task = asyncio.create_task(
                    coordinator.reconcile_startup()
                )
                await gateway.entered.wait()
                gateway.release.set()

                report = await task

                self.assertFalse(report.ready)
                self.assertEqual(
                    coordinator.state,
                    StartupReconciliationState.DEGRADED,
                )

    async def test_startup_buffer_overflow_fails_closed(self) -> None:
        coordinator = StartupOrderReconciliationCoordinator(
            oms=FakeOms(),  # type: ignore[arg-type]
            gateway=DelayedGateway(None),  # type: ignore[arg-type]
            now_ns=lambda: UnixNanos(250),
            max_buffered_observations=1,
        )
        coordinator.begin_buffering()
        value = snapshot(
            source=ReconciliationSource.USER_STREAM,
            update_id="one",
            status=OrderStatus.OPEN,
            filled="0",
            observed_at_ns=150,
        )
        await coordinator.on_stream_snapshot(value)

        with self.assertRaisesRegex(
            StartupReconciliationError,
            "overflow",
        ):
            await coordinator.on_stream_snapshot(value)
        self.assertEqual(
            coordinator.state,
            StartupReconciliationState.FAILED,
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
