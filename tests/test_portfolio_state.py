from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from threading import Thread

from cex_quant.core import AccountId, AssetId, Money, Price, Quantity, VenueId
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.portfolio import (
    AccountScopeError,
    AccountState,
    AccountUpdate,
    AccountUpdateConflictError,
    AccountUpdateDisposition,
    AccountWriterViolationError,
    Balance,
    Position,
    PositionAccounting,
)

VENUE = VenueId("binance")
ACCOUNT = AccountId("main")


def money(value: str) -> Money:
    return Money.from_str(value)


def quantity(value: str) -> Quantity:
    return Quantity.from_str(value)


def price(value: str) -> Price:
    return Price.from_str(value)


def instrument(kind: InstrumentKind, symbol: str) -> InstrumentId:
    return InstrumentId(venue=VENUE, kind=kind, symbol=symbol)


class PortfolioContractsTest(unittest.TestCase):
    def test_balance_requires_exact_partition_across_scales(self) -> None:
        balance = Balance(
            asset=AssetId("USDT"),
            total=money("10.00"),
            available=money("7.5"),
            locked=money("2.500"),
        )
        self.assertEqual(balance.total.as_decimal(), money("10").as_decimal())
        with self.assertRaises(ValueError):
            Balance(
                asset=AssetId("USDT"),
                total=money("10"),
                available=money("9"),
                locked=money("2"),
            )

    def test_contracts_are_immutable(self) -> None:
        balance = Balance(
            asset=AssetId("BTC"),
            total=money("1"),
            available=money("1"),
            locked=money("0"),
        )
        with self.assertRaises(FrozenInstanceError):
            balance.total = money("2")  # type: ignore[misc]

    def test_position_supports_required_accounting_conventions(self) -> None:
        cases = (
            (InstrumentKind.SPOT, PositionAccounting.SPOT, "BTCUSDT"),
            (InstrumentKind.PERPETUAL, PositionAccounting.LINEAR, "BTCUSDT"),
            (InstrumentKind.FUTURE, PositionAccounting.INVERSE, "BTCUSD_2509"),
            (InstrumentKind.OPTION, PositionAccounting.OPTION, "BTC-2509-C"),
        )
        for kind, accounting, symbol in cases:
            with self.subTest(accounting=accounting):
                value = Position(
                    instrument_id=instrument(kind, symbol),
                    accounting=accounting,
                    quantity=quantity("-2"),
                    average_entry_price=price("100"),
                    cost_basis=money("200"),
                    realized_pnl=money("-3"),
                    pnl_asset=AssetId("USDT"),
                )
                self.assertEqual(value.quantity.as_decimal(), -2)

    def test_quanto_is_explicitly_rejected(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "quanto"):
            Position(
                instrument_id=instrument(
                    InstrumentKind.PERPETUAL, "QUANTO-PERP"
                ),
                accounting=PositionAccounting.QUANTO,
                quantity=quantity("1"),
                average_entry_price=price("10"),
                cost_basis=money("10"),
                realized_pnl=money("0"),
                pnl_asset=AssetId("USD"),
            )

    def test_non_flat_position_requires_entry_price(self) -> None:
        with self.assertRaisesRegex(ValueError, "average_entry_price"):
            Position(
                instrument_id=instrument(InstrumentKind.SPOT, "ETHUSDT"),
                accounting=PositionAccounting.SPOT,
                quantity=quantity("1"),
                cost_basis=money("10"),
                realized_pnl=money("0"),
                pnl_asset=AssetId("USDT"),
            )


class AccountStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AccountState(account_id=ACCOUNT, venue=VENUE)
        self.usdt = Balance(
            asset=AssetId("USDT"),
            total=money("100"),
            available=money("80"),
            locked=money("20"),
        )
        self.btc = Position(
            instrument_id=instrument(InstrumentKind.SPOT, "BTCUSDT"),
            accounting=PositionAccounting.SPOT,
            quantity=quantity("1"),
            average_entry_price=price("50000"),
            cost_basis=money("50000"),
            realized_pnl=money("0"),
            pnl_asset=AssetId("USDT"),
        )

    def update(
        self,
        update_id: str,
        *,
        sequence: int | None,
        event_time: int,
        balances: tuple[Balance, ...] = (),
        positions: tuple[Position, ...] = (),
    ) -> AccountUpdate:
        return AccountUpdate(
            venue_update_id=update_id,
            account_id=ACCOUNT,
            venue=VENUE,
            sequence=sequence,
            event_time_ns=event_time,
            balances=balances,
            positions=positions,
        )

    def test_applies_absolute_values_and_freezes_sorted_snapshot(self) -> None:
        btc_balance = Balance(
            asset=AssetId("BTC"),
            total=money("1"),
            available=money("1"),
            locked=money("0"),
        )
        result = self.state.apply(
            self.update(
                "u1",
                sequence=10,
                event_time=100,
                balances=(self.usdt, btc_balance),
                positions=(self.btc,),
            )
        )
        snapshot = self.state.snapshot()
        self.assertEqual(result, AccountUpdateDisposition.APPLIED)
        self.assertEqual(
            [str(item.asset) for item in snapshot.balances],
            ["BTC", "USDT"],
        )
        self.assertEqual(snapshot.positions, (self.btc,))
        self.assertEqual(snapshot.sequence, 10)

    def test_duplicate_is_idempotent_and_conflict_is_rejected(self) -> None:
        update = self.update(
            "u1", sequence=1, event_time=10, balances=(self.usdt,)
        )
        self.assertEqual(
            self.state.apply(update), AccountUpdateDisposition.APPLIED
        )
        self.assertEqual(
            self.state.apply(update), AccountUpdateDisposition.DUPLICATE
        )
        conflicting = self.update("u1", sequence=2, event_time=20)
        with self.assertRaises(AccountUpdateConflictError):
            self.state.apply(conflicting)

    def test_sequence_rejects_old_and_missing_sequence(self) -> None:
        self.state.apply(self.update("u1", sequence=5, event_time=100))
        self.assertEqual(
            self.state.apply(self.update("u2", sequence=4, event_time=200)),
            AccountUpdateDisposition.OUT_OF_ORDER,
        )
        self.assertEqual(
            self.state.apply(self.update("u3", sequence=None, event_time=300)),
            AccountUpdateDisposition.OUT_OF_ORDER,
        )
        self.assertEqual(self.state.snapshot().sequence, 5)

    def test_sequence_is_authoritative_without_regressing_as_of_time(self) -> None:
        self.state.apply(self.update("u1", sequence=1, event_time=100))
        self.assertEqual(
            self.state.apply(
                self.update("u2", sequence=2, event_time=90)
            ),
            AccountUpdateDisposition.APPLIED,
        )
        self.assertEqual(self.state.snapshot().as_of_time_ns, 100)

    def test_time_ordering_without_sequences_allows_equal_timestamp(self) -> None:
        self.assertEqual(
            self.state.apply(self.update("u1", sequence=None, event_time=10)),
            AccountUpdateDisposition.APPLIED,
        )
        self.assertEqual(
            self.state.apply(self.update("u2", sequence=None, event_time=10)),
            AccountUpdateDisposition.APPLIED,
        )
        self.assertEqual(
            self.state.apply(self.update("u3", sequence=None, event_time=9)),
            AccountUpdateDisposition.OUT_OF_ORDER,
        )

    def test_update_is_atomic_and_scope_is_enforced(self) -> None:
        wrong = AccountUpdate(
            venue_update_id="x",
            account_id=AccountId("other"),
            venue=VENUE,
            event_time_ns=1,
            balances=(self.usdt,),
        )
        with self.assertRaises(AccountScopeError):
            self.state.apply(wrong)
        self.assertEqual(self.state.snapshot().balances, ())

    def test_mutation_from_non_owner_thread_is_rejected(self) -> None:
        errors: list[BaseException] = []

        def mutate() -> None:
            try:
                self.state.apply(
                    self.update("u1", sequence=1, event_time=1)
                )
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=mutate)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], AccountWriterViolationError)
        self.assertIsNone(self.state.snapshot().sequence)

    def test_seen_id_memory_is_bounded_with_ordering_as_backstop(self) -> None:
        state = AccountState(
            account_id=ACCOUNT, venue=VENUE, max_seen_update_ids=1
        )
        first = self.update("u1", sequence=1, event_time=1)
        state.apply(first)
        state.apply(self.update("u2", sequence=2, event_time=2))
        self.assertEqual(
            state.apply(first), AccountUpdateDisposition.OUT_OF_ORDER
        )

    def test_absolute_update_replaces_only_named_entities(self) -> None:
        self.state.apply(
            self.update(
                "u1",
                sequence=1,
                event_time=10,
                balances=(self.usdt,),
                positions=(self.btc,),
            )
        )
        changed = Balance(
            asset=AssetId("USDT"),
            total=money("90"),
            available=money("90"),
            locked=money("0"),
        )
        self.state.apply(
            self.update(
                "u2", sequence=2, event_time=20, balances=(changed,)
            )
        )
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot.balances, (changed,))
        self.assertEqual(snapshot.positions, (self.btc,))


if __name__ == "__main__":
    unittest.main()
