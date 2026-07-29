import unittest
from dataclasses import replace

from cex_quant.accounting import (
    MAX_FINANCIAL_REFERENCE_LENGTH,
    MAX_LEDGER_MEMO_LENGTH,
    MAX_OWNER_ID_LENGTH,
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    EconomicOwnerRef,
    EconomicOwnerTypeRef,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceKind,
    LedgerAccount,
    LedgerAccountId,
    LedgerAccountType,
    LedgerMappingPolicy,
    LedgerPosting,
    LedgerTransaction,
    ObservedFinancialFact,
    map_financial_fact,
)
from cex_quant.core import (
    AccountId,
    AssetId,
    FinancialFactId,
    FinancialObservationId,
    LedgerPostingId,
    Money,
    UnixNanos,
    VenueId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind


def metadata() -> FinancialFactMetadata:
    return FinancialFactMetadata(
        fact_id=FinancialFactId("fact-1"),
        venue=VenueId("binance"),
        account_id=AccountId("account-1"),
        venue_reference="venue-reference-1",
        effective_time_ns=UnixNanos(1_000),
        schema_version=1,
    )


def cash_fact() -> AccountCashFlowFact:
    return AccountCashFlowFact(
        metadata=metadata(),
        cash_flow_type=AccountCashFlowType.FUNDING,
        component=CashComponent(
            asset=AssetId("USDT"),
            signed_amount=Money.from_str("10"),
        ),
    )


def observation() -> FinancialFactObservation:
    return FinancialFactObservation(
        observation_id=FinancialObservationId("observation-1"),
        fact_id=FinancialFactId("fact-1"),
        source_kind=FinancialSourceKind.PRIVATE_STREAM,
        observed_at_ns=UnixNanos(2_000),
        payload_fingerprint="a" * 64,
        source_cursor="cursor-1",
    )


class AccountingContractValidationTests(unittest.TestCase):
    def test_financial_fact_contracts_fail_closed(self) -> None:
        invalid_metadata = (
            lambda: replace(metadata(), fact_id=FinancialFactId("")),
            lambda: replace(metadata(), effective_time_ns=UnixNanos(-1)),
            lambda: replace(metadata(), schema_version=0),
            lambda: replace(metadata(), venue_reference=" bad"),
            lambda: replace(
                metadata(),
                venue_reference="x" * (MAX_FINANCIAL_REFERENCE_LENGTH + 1),
            ),
        )
        invalid_observations = (
            lambda: replace(
                observation(),
                observation_id=FinancialObservationId(""),
            ),
            lambda: replace(observation(), observed_at_ns=UnixNanos(-1)),
            lambda: replace(observation(), payload_fingerprint="A" * 64),
            lambda: replace(observation(), source_cursor=" bad"),
            lambda: replace(observation(), source_cursor=""),
        )
        invalid_components = (
            lambda: CashComponent(
                asset=AssetId(""),
                signed_amount=Money.from_str("1"),
            ),
            lambda: CashComponent(
                asset=AssetId("USDT"),
                signed_amount=Money.from_str("0"),
            ),
        )
        for case in (
            *invalid_metadata,
            *invalid_observations,
            *invalid_components,
        ):
            with self.subTest(case=case), self.assertRaises(ValueError):
                case()

        with self.assertRaises(ValueError):
            AccountCashFlowFact(
                metadata=metadata(),
                cash_flow_type=AccountCashFlowType.FUNDING,
                component=cash_fact().component,
                instrument_id=InstrumentId(
                    venue=VenueId("other"),
                    kind=InstrumentKind.PERPETUAL,
                    symbol="BTCUSDT",
                ),
            )
        with self.assertRaises(ValueError):
            ObservedFinancialFact(
                fact=cash_fact(),
                observation=replace(
                    observation(),
                    fact_id=FinancialFactId("other"),
                ),
            )

    def test_owner_and_ledger_contracts_fail_closed(self) -> None:
        for case in (
            lambda: EconomicOwnerTypeRef(name="BAD", version=1),
            lambda: EconomicOwnerTypeRef(name="owner", version=0),
            lambda: EconomicOwnerRef(
                owner_type=EconomicOwnerTypeRef(
                    name="application.position",
                    version=1,
                ),
                owner_id="",
            ),
            lambda: EconomicOwnerRef(
                owner_type=EconomicOwnerTypeRef(
                    name="application.position",
                    version=1,
                ),
                owner_id="x" * (MAX_OWNER_ID_LENGTH + 1),
            ),
        ):
            with self.subTest(case=case), self.assertRaises(ValueError):
                case()

        account = LedgerAccount(
            ledger_account_id=LedgerAccountId("account-ledger-1"),
            venue=VenueId("binance"),
            account_id=AccountId("account-1"),
            account_type=LedgerAccountType.VENUE_CASH,
            asset=AssetId("USDT"),
        )
        for case in (
            lambda: replace(
                account,
                ledger_account_id=LedgerAccountId(""),
            ),
            lambda: LedgerPosting(
                posting_id=LedgerPostingId("posting-1"),
                account=account,
                signed_amount=Money.from_str("0"),
            ),
            lambda: LedgerPosting(
                posting_id=LedgerPostingId("posting-1"),
                account=account,
                signed_amount=Money.from_str("1"),
                memo=" bad",
            ),
            lambda: LedgerPosting(
                posting_id=LedgerPostingId("posting-1"),
                account=account,
                signed_amount=Money.from_str("1"),
                memo="x" * (MAX_LEDGER_MEMO_LENGTH + 1),
            ),
        ):
            with self.subTest(case=case), self.assertRaises(ValueError):
                case()

    def test_transaction_invariants_reject_malformed_history(self) -> None:
        draft = map_financial_fact(
            cash_fact(),
            LedgerMappingPolicy(version=1, instruments=()),
        )[0]
        transaction = LedgerTransaction(
            transaction_id=draft.transaction_id,
            source_fact_ids=draft.source_fact_ids,
            transaction_type=draft.transaction_type,
            postings=draft.postings,
            effective_time_ns=draft.effective_time_ns,
            posted_at_ns=UnixNanos(2_000),
            ledger_sequence=1,
            mapping_policy_version=draft.mapping_policy_version,
        )
        unbalanced = replace(
            draft.postings[1],
            signed_amount=draft.postings[0].signed_amount,
        )
        malformed = (
            lambda: replace(draft, source_fact_ids=()),
            lambda: replace(
                draft,
                source_fact_ids=(
                    FinancialFactId("z"),
                    FinancialFactId("a"),
                ),
            ),
            lambda: replace(draft, postings=(draft.postings[0],)),
            lambda: replace(
                draft,
                postings=(draft.postings[0], draft.postings[0]),
            ),
            lambda: replace(draft, effective_time_ns=UnixNanos(-1)),
            lambda: replace(draft, mapping_policy_version=0),
            lambda: replace(
                draft,
                reverses_transaction_id=draft.transaction_id,
            ),
            lambda: replace(
                draft,
                postings=(draft.postings[0], unbalanced),
            ),
            lambda: replace(transaction, posted_at_ns=UnixNanos(-1)),
            lambda: replace(transaction, ledger_sequence=0),
        )
        for case in malformed:
            with self.subTest(case=case), self.assertRaises(ValueError):
                case()


if __name__ == "__main__":
    unittest.main()
