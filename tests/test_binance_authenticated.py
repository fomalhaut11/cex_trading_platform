import json
from typing import Any
from unittest import IsolatedAsyncioTestCase, TestCase
from urllib.parse import parse_qs

from cex_quant.core import (
    AccountId,
    ClientOrderId,
    IntentId,
    Price,
    Quantity,
    UnixNanos,
    VenueId,
)
from cex_quant.execution import (
    AuthenticatedBinanceExecutionAdapter,
    BinanceCredentials,
    BinanceHttpRequest,
    BinanceHttpResponse,
    BinanceHttpTransportFailure,
    CancelOrder,
    ExecutionOutcome,
    ExecutionStateUnknownError,
    ExecutionTransportError,
    canonical_query,
    hmac_sha256_hex,
)
from cex_quant.execution.adapters import BinanceProduct
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.oms import OrderRequest, OrderSide, OrderType, TimeInForce


class StaticCredentials:
    def __init__(self, credentials: BinanceCredentials) -> None:
        self.credentials = credentials
        self.requested_accounts: list[AccountId] = []

    def credentials_for(self, account_id: AccountId) -> BinanceCredentials:
        self.requested_accounts.append(account_id)
        return self.credentials


class CapturingTransport:
    def __init__(
        self,
        response: BinanceHttpResponse | None = None,
        failure: BinanceHttpTransportFailure | None = None,
    ) -> None:
        self.response = response
        self.failure = failure
        self.calls: list[tuple[BinanceProduct, BinanceHttpRequest]] = []

    async def send(
        self, product: BinanceProduct, request: BinanceHttpRequest
    ) -> BinanceHttpResponse:
        self.calls.append((product, request))
        if self.failure is not None:
            raise self.failure
        assert self.response is not None
        return self.response


def response(status: int, payload: Any) -> BinanceHttpResponse:
    return BinanceHttpResponse(
        status_code=status,
        body=json.dumps(payload).encode("utf-8"),
    )


def instrument(
    kind: InstrumentKind = InstrumentKind.SPOT,
) -> InstrumentId:
    return InstrumentId(
        venue=VenueId("BINANCE"),
        kind=kind,
        symbol="BTCUSDT",
    )


def order() -> OrderRequest:
    return OrderRequest(
        client_order_id=ClientOrderId("strategy-1"),
        approval_id="approval-1",
        intent_id=IntentId("intent-1"),
        account_id=AccountId("primary"),
        instrument_id=instrument(),
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Quantity.from_str("0.010"),
        created_at_ns=UnixNanos(1),
        limit_price=Price.from_str("60000.0"),
        time_in_force=TimeInForce.GTC,
    )


class BinanceSigningTest(TestCase):
    def test_matches_official_hmac_example(self) -> None:
        payload = (
            "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC"
            "&quantity=1&price=0.1&recvWindow=5000"
            "&timestamp=1499827319559"
        )
        secret = (
            "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
        )

        self.assertEqual(
            hmac_sha256_hex(secret, payload),
            "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71",
        )

    def test_canonical_query_is_sorted_and_percent_encoded(self) -> None:
        symbol = "\uff11\uff12"
        first = canonical_query({"symbol": symbol, "side": "BUY", "a": "x y"})
        second = canonical_query({"a": "x y", "side": "BUY", "symbol": symbol})

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            "a=x%20y&side=BUY&symbol=%EF%BC%91%EF%BC%92",
        )

    def test_credentials_repr_is_redacted(self) -> None:
        credentials = BinanceCredentials(
            api_key="public-key", secret="private-value"
        )
        rendered = repr(credentials)

        self.assertNotIn("public-key", rendered)
        self.assertNotIn("private-value", rendered)
        self.assertIn("redacted", rendered)


class AuthenticatedBinanceAdapterTest(IsolatedAsyncioTestCase):
    def build_adapter(
        self,
        transport: CapturingTransport,
        *,
        credentials: BinanceCredentials | None = None,
        recv_window_ms: int = 5_000,
    ) -> tuple[AuthenticatedBinanceExecutionAdapter, StaticCredentials]:
        provider = StaticCredentials(
            credentials
            or BinanceCredentials(api_key="test-api-key", secret="test-secret")
        )
        return (
            AuthenticatedBinanceExecutionAdapter(
                product=BinanceProduct.SPOT,
                credential_provider=provider,
                transport=transport,
                timestamp_ms=lambda: 1_700_000_000_123,
                recv_window_ms=recv_window_ms,
            ),
            provider,
        )

    async def test_submit_signs_exact_transmitted_query(self) -> None:
        transport = CapturingTransport(
            response(200, {"orderId": 12345, "clientOrderId": "strategy-1"})
        )
        adapter, provider = self.build_adapter(transport)

        result = await adapter.submit(order())

        self.assertIs(result.outcome, ExecutionOutcome.ACCEPTED)
        self.assertEqual(result.venue_order_id, "12345")
        self.assertEqual(provider.requested_accounts, [AccountId("primary")])
        product, request = transport.calls[0]
        self.assertIs(product, BinanceProduct.SPOT)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/api/v3/order")
        self.assertEqual(request.headers["X-MBX-APIKEY"], "test-api-key")
        unsigned, signature = request.query.rsplit("&signature=", 1)
        self.assertEqual(
            signature, hmac_sha256_hex("test-secret", unsigned)
        )
        parsed = parse_qs(unsigned)
        self.assertEqual(parsed["timestamp"], ["1700000000123"])
        self.assertEqual(parsed["recvWindow"], ["5000"])
        self.assertEqual(parsed["newClientOrderId"], ["strategy-1"])

    async def test_cancel_parses_typed_acceptance(self) -> None:
        transport = CapturingTransport(
            response(200, {"orderId": "987", "status": "CANCELED"})
        )
        adapter, _ = self.build_adapter(transport)
        command = CancelOrder(
            account_id=AccountId("primary"),
            instrument_id=instrument(),
            client_order_id=ClientOrderId("strategy-1"),
        )

        result = await adapter.cancel(command)

        self.assertIs(result.outcome, ExecutionOutcome.ACCEPTED)
        self.assertEqual(result.venue_order_id, "987")
        request = transport.calls[0][1]
        self.assertEqual(request.method, "DELETE")
        self.assertIn("origClientOrderId=strategy-1", request.query)

    async def test_business_error_becomes_typed_rejection(self) -> None:
        transport = CapturingTransport(
            response(400, {"code": -1013, "msg": "Invalid quantity."})
        )
        adapter, _ = self.build_adapter(transport)

        result = await adapter.submit(order())

        self.assertIs(result.outcome, ExecutionOutcome.REJECTED)
        self.assertEqual(result.rejection_code, "-1013")
        self.assertEqual(result.rejection_message, "Invalid quantity.")

    async def test_server_error_is_unknown_not_a_rejection(self) -> None:
        transport = CapturingTransport(
            response(504, {"code": -1007, "msg": "Timeout waiting"})
        )
        adapter, _ = self.build_adapter(transport)

        with self.assertRaises(ExecutionStateUnknownError):
            await adapter.submit(order())

    async def test_transport_failure_classification_and_secret_redaction(
        self,
    ) -> None:
        secret = "never-leak-this"
        key = "also-redact-key"
        credentials = BinanceCredentials(api_key=key, secret=secret)
        not_sent = CapturingTransport(
            failure=BinanceHttpTransportFailure(
                f"dial failed {secret} {key}", request_sent=False
            )
        )
        adapter, _ = self.build_adapter(
            not_sent, credentials=credentials
        )

        with self.assertRaises(ExecutionTransportError) as caught:
            await adapter.submit(order())
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(key, str(caught.exception))

        sent = CapturingTransport(
            failure=BinanceHttpTransportFailure(
                f"read failed {secret}", request_sent=True
            )
        )
        adapter, _ = self.build_adapter(sent, credentials=credentials)
        with self.assertRaises(ExecutionStateUnknownError) as caught_unknown:
            await adapter.submit(order())
        self.assertNotIn(secret, str(caught_unknown.exception))

    async def test_malformed_success_is_transport_error(self) -> None:
        adapter, _ = self.build_adapter(
            CapturingTransport(response(200, {"status": "NEW"}))
        )
        with self.assertRaisesRegex(ExecutionTransportError, "orderId"):
            await adapter.submit(order())

    async def test_recv_window_is_bounded(self) -> None:
        transport = CapturingTransport(response(200, {"orderId": 1}))
        with self.assertRaisesRegex(ValueError, "60000"):
            self.build_adapter(transport, recv_window_ms=60_001)


if __name__ == "__main__":
    import unittest

    unittest.main()
