import json
import unittest
from decimal import Decimal
from pathlib import Path

from cex_quant.core import ClientOrderId, UnixNanos
from cex_quant.execution import (
    BinanceOrderNormalizationError,
    BinanceOrderNormalizationErrorCode,
    normalize_binance_order_query,
    normalize_binance_user_order_update,
)
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.oms import (
    OrderStatus,
    ReconciliationSource,
)

FIXTURES = Path(__file__).parent / "fixtures" / "binance"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class BinanceReconciliationTests(unittest.TestCase):
    def test_spot_query_derives_exact_average_price(self) -> None:
        snapshot = normalize_binance_order_query(
            BinanceProduct.SPOT,
            fixture("spot_query_order.json"),
            received_at_ns=UnixNanos(999),
            expected_client_order_id=ClientOrderId("client-spot-1"),
        )

        self.assertEqual(snapshot.source, ReconciliationSource.REST_QUERY)
        self.assertEqual(snapshot.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(
            snapshot.cumulative_filled_quantity.as_decimal(),
            Decimal("0.001"),
        )
        self.assertIsNotNone(snapshot.average_fill_price)
        self.assertEqual(
            snapshot.average_fill_price.as_decimal(),  # type: ignore[union-attr]
            Decimal("60000"),
        )
        self.assertEqual(
            snapshot.observed_at_ns,
            UnixNanos(1_720_000_000_100_000_000),
        )

    def test_spot_enveloped_execution_report_maps_fill(self) -> None:
        snapshot = normalize_binance_user_order_update(
            BinanceProduct.SPOT,
            fixture("spot_execution_report.json"),
        )

        self.assertEqual(snapshot.source, ReconciliationSource.USER_STREAM)
        self.assertEqual(snapshot.source_update_id, "spot:42:9002")
        self.assertEqual(snapshot.status, OrderStatus.FILLED)
        self.assertEqual(
            snapshot.average_fill_price.as_decimal(),  # type: ignore[union-attr]
            60_005,
        )

    def test_usdm_query_and_stream_use_futures_fields(self) -> None:
        query = normalize_binance_order_query(
            BinanceProduct.USD_M,
            fixture("usdm_query_order.json"),
            received_at_ns=UnixNanos(999),
        )
        stream = normalize_binance_user_order_update(
            BinanceProduct.USD_M,
            fixture("usdm_order_trade_update.json"),
        )

        self.assertEqual(query.status, OrderStatus.OPEN)
        self.assertIsNone(query.average_fill_price)
        self.assertEqual(stream.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(
            stream.cumulative_filled_quantity.as_decimal(),
            Decimal("0.10"),
        )
        self.assertEqual(
            stream.average_fill_price.as_decimal(),  # type: ignore[union-attr]
            Decimal("60001.25"),
        )
        self.assertIn("TRADE:501", stream.source_update_id)

    def test_coinm_query_preserves_expired_terminal_status(self) -> None:
        query = normalize_binance_order_query(
            BinanceProduct.COIN_M,
            fixture("coinm_query_order.json"),
            received_at_ns=UnixNanos(999),
        )
        stream = normalize_binance_user_order_update(
            BinanceProduct.COIN_M,
            fixture("coinm_order_trade_update.json"),
        )

        self.assertEqual(query.status, OrderStatus.EXPIRED)
        self.assertTrue(query.reason.startswith("binance_status=EXPIRED"))
        self.assertEqual(stream.status, OrderStatus.FILLED)
        self.assertEqual(
            stream.average_fill_price.as_decimal(),  # type: ignore[union-attr]
            Decimal("59995.5"),
        )

    def test_pending_cancel_and_expired_in_match_are_not_collapsed(self) -> None:
        base = json.loads(fixture("spot_query_order.json"))
        base["status"] = "PENDING_CANCEL"
        pending = normalize_binance_order_query(
            BinanceProduct.SPOT,
            base,
            received_at_ns=UnixNanos(999),
        )
        base["status"] = "EXPIRED_IN_MATCH"
        expired = normalize_binance_order_query(
            BinanceProduct.SPOT,
            base,
            received_at_ns=UnixNanos(999),
        )

        self.assertEqual(pending.status, OrderStatus.CANCEL_PENDING)
        self.assertEqual(expired.status, OrderStatus.EXPIRED)

    def test_identity_mismatch_is_typed(self) -> None:
        with self.assertRaises(BinanceOrderNormalizationError) as raised:
            normalize_binance_order_query(
                BinanceProduct.SPOT,
                fixture("spot_query_order.json"),
                received_at_ns=UnixNanos(999),
                expected_client_order_id=ClientOrderId("other"),
            )
        self.assertEqual(
            raised.exception.code,
            BinanceOrderNormalizationErrorCode.IDENTITY_MISMATCH,
        )

    def test_query_without_update_time_has_stable_update_identity(self) -> None:
        payload = json.loads(fixture("spot_query_order.json"))
        del payload["updateTime"]

        first = normalize_binance_order_query(
            BinanceProduct.SPOT,
            payload,
            received_at_ns=UnixNanos(100),
        )
        second = normalize_binance_order_query(
            BinanceProduct.SPOT,
            payload,
            received_at_ns=UnixNanos(200),
        )

        self.assertEqual(first.source_update_id, second.source_update_id)
        self.assertEqual(first.observed_at_ns, UnixNanos(100))
        self.assertEqual(second.observed_at_ns, UnixNanos(200))

    def test_wrong_event_status_and_malformed_payload_are_typed(self) -> None:
        with self.assertRaises(BinanceOrderNormalizationError) as wrong_event:
            normalize_binance_user_order_update(
                BinanceProduct.SPOT,
                b'{"e":"outboundAccountPosition"}',
            )
        self.assertEqual(
            wrong_event.exception.code,
            BinanceOrderNormalizationErrorCode.WRONG_EVENT_TYPE,
        )

        unsupported = json.loads(fixture("usdm_query_order.json"))
        unsupported["status"] = "MYSTERY"
        with self.assertRaises(BinanceOrderNormalizationError) as wrong_status:
            normalize_binance_order_query(
                BinanceProduct.USD_M,
                unsupported,
                received_at_ns=UnixNanos(999),
            )
        self.assertEqual(
            wrong_status.exception.code,
            BinanceOrderNormalizationErrorCode.UNSUPPORTED_STATUS,
        )

        with self.assertRaises(BinanceOrderNormalizationError) as malformed:
            normalize_binance_order_query(
                BinanceProduct.SPOT,
                b"{",
                received_at_ns=UnixNanos(999),
            )
        self.assertEqual(
            malformed.exception.code,
            BinanceOrderNormalizationErrorCode.MALFORMED_PAYLOAD,
        )


if __name__ == "__main__":
    unittest.main()
