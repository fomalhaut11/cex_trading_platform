"""Pure deterministic mapping from financial facts to balanced ledger drafts."""

from __future__ import annotations

from dataclasses import dataclass

from cex_quant.core import AssetId, Money
from cex_quant.instruments import Instrument, InstrumentId, InstrumentKind

from .facts import (
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    ExecutionFillFact,
    FillSide,
    FinancialSourceFact,
)
from .identifiers import (
    deterministic_ledger_account_id,
    deterministic_ledger_posting_id,
    deterministic_ledger_transaction_id,
)
from .model import (
    LedgerAccount,
    LedgerAccountType,
    LedgerPosting,
    LedgerTransactionDraft,
    LedgerTransactionType,
)

MAX_MAPPING_INSTRUMENTS = 16_384


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerMappingPolicy:
    version: int
    instruments: tuple[Instrument, ...]

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("mapping policy version must be positive")
        if len(self.instruments) > MAX_MAPPING_INSTRUMENTS:
            raise ValueError("mapping policy instrument count exceeds bound")
        keys = tuple(str(item.instrument_id) for item in self.instruments)
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("mapping policy instruments must be unique and sorted")

    def instrument(self, instrument_id: InstrumentId) -> Instrument:
        for instrument in self.instruments:
            if instrument.instrument_id == instrument_id:
                return instrument
        raise UnsupportedFinancialMappingError(
            f"instrument is not registered for Accounting: {instrument_id}"
        )


class FinancialMappingError(ValueError):
    pass


class UnsupportedFinancialMappingError(FinancialMappingError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class _PostingSpec:
    account_type: LedgerAccountType
    asset: AssetId
    amount: Money
    memo: str


def map_financial_fact(
    fact: FinancialSourceFact,
    policy: LedgerMappingPolicy,
) -> tuple[LedgerTransactionDraft, ...]:
    if isinstance(fact, AccountCashFlowFact):
        return (_map_cash_flow(fact, policy),)
    return (_map_fill(fact, policy),)


def _map_cash_flow(
    fact: AccountCashFlowFact,
    policy: LedgerMappingPolicy,
) -> LedgerTransactionDraft:
    transaction_type, offset_type = {
        AccountCashFlowType.FUNDING: (
            LedgerTransactionType.FUNDING,
            LedgerAccountType.FUNDING_INCOME,
        ),
        AccountCashFlowType.COMMISSION: (
            LedgerTransactionType.COMMISSION,
            LedgerAccountType.COMMISSION_EXPENSE,
        ),
        AccountCashFlowType.REBATE: (
            LedgerTransactionType.REBATE,
            LedgerAccountType.REBATE_INCOME,
        ),
        AccountCashFlowType.BORROW_INTEREST: (
            LedgerTransactionType.BORROW_INTEREST,
            LedgerAccountType.BORROW_INTEREST_EXPENSE,
        ),
        AccountCashFlowType.REALIZED_SETTLEMENT: (
            LedgerTransactionType.REALIZED_SETTLEMENT,
            LedgerAccountType.REALIZED_PNL,
        ),
        AccountCashFlowType.DEPOSIT: (
            LedgerTransactionType.TRANSFER,
            LedgerAccountType.TRANSFER_CLEARING,
        ),
        AccountCashFlowType.WITHDRAWAL: (
            LedgerTransactionType.TRANSFER,
            LedgerAccountType.TRANSFER_CLEARING,
        ),
        AccountCashFlowType.TRANSFER: (
            LedgerTransactionType.TRANSFER,
            LedgerAccountType.TRANSFER_CLEARING,
        ),
        AccountCashFlowType.LIQUIDATION: (
            LedgerTransactionType.LIQUIDATION,
            LedgerAccountType.LIQUIDATION_EXPENSE,
        ),
        AccountCashFlowType.INSURANCE: (
            LedgerTransactionType.INSURANCE,
            LedgerAccountType.INSURANCE_CLEARING,
        ),
        AccountCashFlowType.VENUE_ADJUSTMENT: (
            LedgerTransactionType.VENUE_ADJUSTMENT,
            LedgerAccountType.ADJUSTMENT_CLEARING,
        ),
    }[fact.cash_flow_type]
    component = fact.component
    specs = (
        _PostingSpec(
            account_type=LedgerAccountType.VENUE_CASH,
            asset=component.asset,
            amount=component.signed_amount,
            memo=fact.cash_flow_type.value,
        ),
        _PostingSpec(
            account_type=offset_type,
            asset=component.asset,
            amount=_negate(component.signed_amount),
            memo=fact.cash_flow_type.value,
        ),
    )
    return _build_draft(
        fact=fact,
        transaction_type=transaction_type,
        policy=policy,
        specs=specs,
    )


def _map_fill(
    fact: ExecutionFillFact,
    policy: LedgerMappingPolicy,
) -> LedgerTransactionDraft:
    instrument = policy.instrument(fact.instrument_id)
    if instrument.quote_asset != fact.quote_asset:
        raise FinancialMappingError("fill quote asset does not match instrument")
    specs: list[_PostingSpec] = []
    if instrument.instrument_id.kind is InstrumentKind.SPOT:
        base_amount = Money(
            raw=fact.fill_quantity.raw,
            scale=fact.fill_quantity.scale,
        )
        if fact.side is FillSide.SELL:
            base_amount = _negate(base_amount)
        quote_amount = fact.quote_amount
        if fact.side is FillSide.BUY:
            quote_amount = _negate(quote_amount)
        specs.extend(
            _balanced_movement(
                venue_type=LedgerAccountType.VENUE_INVENTORY,
                offset_type=LedgerAccountType.TRADE_CLEARING,
                asset=instrument.base_asset,
                amount=base_amount,
                memo="spot_fill_base",
            )
        )
        specs.extend(
            _balanced_movement(
                venue_type=LedgerAccountType.VENUE_CASH,
                offset_type=LedgerAccountType.TRADE_CLEARING,
                asset=instrument.quote_asset,
                amount=quote_amount,
                memo="spot_fill_quote",
            )
        )
        transaction_type = LedgerTransactionType.SPOT_FILL
    else:
        transaction_type = LedgerTransactionType.DERIVATIVE_FILL
    for component in fact.realized_pnl:
        specs.extend(
            _balanced_component(
                component,
                offset_type=LedgerAccountType.REALIZED_PNL,
                memo="realized_pnl",
            )
        )
    for component in fact.commission:
        if component.signed_amount.as_decimal() >= 0:
            raise FinancialMappingError(
                "fill commission must be a negative account movement"
            )
        specs.extend(
            _balanced_component(
                component,
                offset_type=LedgerAccountType.COMMISSION_EXPENSE,
                memo="commission",
            )
        )
    if not specs:
        raise UnsupportedFinancialMappingError(
            "derivative fill has no financial components"
        )
    return _build_draft(
        fact=fact,
        transaction_type=transaction_type,
        policy=policy,
        specs=tuple(specs),
    )


def _balanced_component(
    component: CashComponent,
    *,
    offset_type: LedgerAccountType,
    memo: str,
) -> tuple[_PostingSpec, _PostingSpec]:
    return _balanced_movement(
        venue_type=LedgerAccountType.VENUE_CASH,
        offset_type=offset_type,
        asset=component.asset,
        amount=component.signed_amount,
        memo=memo,
    )


def _balanced_movement(
    *,
    venue_type: LedgerAccountType,
    offset_type: LedgerAccountType,
    asset: AssetId,
    amount: Money,
    memo: str,
) -> tuple[_PostingSpec, _PostingSpec]:
    return (
        _PostingSpec(
            account_type=venue_type,
            asset=asset,
            amount=amount,
            memo=memo,
        ),
        _PostingSpec(
            account_type=offset_type,
            asset=asset,
            amount=_negate(amount),
            memo=memo,
        ),
    )


def _build_draft(
    *,
    fact: FinancialSourceFact,
    transaction_type: LedgerTransactionType,
    policy: LedgerMappingPolicy,
    specs: tuple[_PostingSpec, ...],
) -> LedgerTransactionDraft:
    metadata = fact.metadata
    accounts = tuple(
        LedgerAccount(
            ledger_account_id=deterministic_ledger_account_id(
                venue=metadata.venue,
                account_id=metadata.account_id,
                account_type=spec.account_type,
                asset=spec.asset,
            ),
            venue=metadata.venue,
            account_id=metadata.account_id,
            account_type=spec.account_type,
            asset=spec.asset,
        )
        for spec in specs
    )
    posting_specs = tuple(
        (
            account.ledger_account_id,
            spec.asset,
            spec.amount,
            spec.memo,
        )
        for account, spec in zip(accounts, specs, strict=True)
    )
    transaction_id = deterministic_ledger_transaction_id(
        source_fact_ids=(metadata.fact_id,),
        transaction_type=transaction_type,
        effective_time_ns=metadata.effective_time_ns,
        mapping_policy_version=policy.version,
        posting_specs=posting_specs,
    )
    postings = tuple(
        LedgerPosting(
            posting_id=deterministic_ledger_posting_id(transaction_id, index),
            account=account,
            signed_amount=spec.amount,
            memo=spec.memo,
        )
        for index, (account, spec) in enumerate(
            zip(accounts, specs, strict=True)
        )
    )
    return LedgerTransactionDraft(
        transaction_id=transaction_id,
        source_fact_ids=(metadata.fact_id,),
        transaction_type=transaction_type,
        postings=postings,
        effective_time_ns=metadata.effective_time_ns,
        mapping_policy_version=policy.version,
    )


def _negate(value: Money) -> Money:
    return Money(raw=-value.raw, scale=value.scale)


__all__ = [
    "MAX_MAPPING_INSTRUMENTS",
    "FinancialMappingError",
    "LedgerMappingPolicy",
    "UnsupportedFinancialMappingError",
    "map_financial_fact",
]
