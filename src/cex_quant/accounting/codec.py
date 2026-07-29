"""Canonical JSON-compatible codecs for Accounting evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import TypeAlias, TypeVar

from cex_quant.core import (
    AccountId,
    AssetId,
    BasketLegId,
    ClientOrderId,
    FinancialFactId,
    FinancialObservationId,
    IntentId,
    LedgerAccountId,
    LedgerPostingId,
    LedgerTransactionId,
    Money,
    OrderGroupId,
    Price,
    Quantity,
    TradeId,
    UnixNanos,
    VenueId,
    VenueOrderId,
)
from cex_quant.instruments import InstrumentId, InstrumentKind

from .facts import (
    AccountCashFlowFact,
    AccountCashFlowType,
    CashComponent,
    ExecutionFillFact,
    FillSide,
    FinancialFactMetadata,
    FinancialFactObservation,
    FinancialSourceKind,
    ObservedFinancialFact,
)
from .model import (
    LedgerAccount,
    LedgerAccountType,
    LedgerPosting,
    LedgerTransaction,
    LedgerTransactionType,
)

JsonScalar: TypeAlias = bool | int | str | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
T = TypeVar("T")


class AccountingCodecError(ValueError):
    pass


def encode_observed_financial_fact(value: ObservedFinancialFact) -> JsonObject:
    fact = value.fact
    common: JsonObject = {
        "metadata": _encode_metadata(fact.metadata),
    }
    if isinstance(fact, ExecutionFillFact):
        fact_type = "execution_fill"
        common.update(
            {
                "instrument_id": _encode_instrument_id(fact.instrument_id),
                "client_order_id": str(fact.client_order_id),
                "venue_order_id": str(fact.venue_order_id),
                "venue_trade_id": str(fact.venue_trade_id),
                "side": fact.side.value,
                "fill_quantity": _encode_fixed(fact.fill_quantity),
                "fill_price": _encode_fixed(fact.fill_price),
                "quote_asset": str(fact.quote_asset),
                "quote_amount": _encode_fixed(fact.quote_amount),
                "commission": [
                    _encode_component(item) for item in fact.commission
                ],
                "realized_pnl": [
                    _encode_component(item) for item in fact.realized_pnl
                ],
                "intent_id": _optional_string(fact.intent_id),
                "order_group_id": _optional_string(fact.order_group_id),
                "basket_leg_id": _optional_string(fact.basket_leg_id),
            }
        )
    else:
        fact_type = "account_cash_flow"
        common.update(
            {
                "cash_flow_type": fact.cash_flow_type.value,
                "component": _encode_component(fact.component),
                "instrument_id": (
                    None
                    if fact.instrument_id is None
                    else _encode_instrument_id(fact.instrument_id)
                ),
            }
        )
    return {
        "fact_type": fact_type,
        "fact": common,
        "observation": _encode_observation(value.observation),
    }


def decode_observed_financial_fact(value: JsonObject) -> ObservedFinancialFact:
    try:
        fact_type = _string(value, "fact_type")
        body = _object(value, "fact")
        metadata = _decode_metadata(_object(body, "metadata"))
        instrument_raw = body.get("instrument_id")
        fact: ExecutionFillFact | AccountCashFlowFact
        if fact_type == "execution_fill":
            fact = ExecutionFillFact(
                metadata=metadata,
                instrument_id=_decode_instrument_id(
                    _required_object(instrument_raw, "instrument_id")
                ),
                client_order_id=ClientOrderId(_string(body, "client_order_id")),
                venue_order_id=VenueOrderId(_string(body, "venue_order_id")),
                venue_trade_id=TradeId(_string(body, "venue_trade_id")),
                side=FillSide(_string(body, "side")),
                fill_quantity=Quantity(**_fixed_kwargs(body, "fill_quantity")),
                fill_price=Price(**_fixed_kwargs(body, "fill_price")),
                quote_asset=AssetId(_string(body, "quote_asset")),
                quote_amount=Money(**_fixed_kwargs(body, "quote_amount")),
                commission=tuple(
                    _decode_component(item)
                    for item in _object_list(body, "commission")
                ),
                realized_pnl=tuple(
                    _decode_component(item)
                    for item in _object_list(body, "realized_pnl")
                ),
                intent_id=_optional_new_type(body, "intent_id", IntentId),
                order_group_id=_optional_new_type(
                    body,
                    "order_group_id",
                    OrderGroupId,
                ),
                basket_leg_id=_optional_new_type(
                    body,
                    "basket_leg_id",
                    BasketLegId,
                ),
            )
        elif fact_type == "account_cash_flow":
            fact = AccountCashFlowFact(
                metadata=metadata,
                cash_flow_type=AccountCashFlowType(
                    _string(body, "cash_flow_type")
                ),
                component=_decode_component(_object(body, "component")),
                instrument_id=(
                    None
                    if instrument_raw is None
                    else _decode_instrument_id(
                        _required_object(instrument_raw, "instrument_id")
                    )
                ),
            )
        else:
            raise AccountingCodecError("financial fact type is unsupported")
        observation_raw = _object(value, "observation")
        observation = FinancialFactObservation(
            observation_id=FinancialObservationId(
                _string(observation_raw, "observation_id")
            ),
            fact_id=FinancialFactId(_string(observation_raw, "fact_id")),
            source_kind=FinancialSourceKind(
                _string(observation_raw, "source_kind")
            ),
            observed_at_ns=UnixNanos(
                _integer(observation_raw, "observed_at_ns")
            ),
            source_cursor=_optional_string_value(
                observation_raw,
                "source_cursor",
            ),
            payload_fingerprint=_string(
                observation_raw,
                "payload_fingerprint",
            ),
        )
        return ObservedFinancialFact(fact=fact, observation=observation)
    except (KeyError, TypeError, ValueError):
        raise AccountingCodecError("observed financial fact is invalid") from None


def encode_ledger_transaction(value: LedgerTransaction) -> JsonObject:
    return {
        "transaction_id": str(value.transaction_id),
        "source_fact_ids": [str(item) for item in value.source_fact_ids],
        "transaction_type": value.transaction_type.value,
        "postings": [_encode_posting(item) for item in value.postings],
        "effective_time_ns": int(value.effective_time_ns),
        "posted_at_ns": int(value.posted_at_ns),
        "ledger_sequence": value.ledger_sequence,
        "mapping_policy_version": value.mapping_policy_version,
        "reverses_transaction_id": _optional_string(
            value.reverses_transaction_id
        ),
    }


def decode_ledger_transaction(value: JsonObject) -> LedgerTransaction:
    try:
        source_ids_raw = _list(value, "source_fact_ids")
        source_ids = tuple(
            FinancialFactId(_required_string(item, "source_fact_id"))
            for item in source_ids_raw
        )
        return LedgerTransaction(
            transaction_id=LedgerTransactionId(
                _string(value, "transaction_id")
            ),
            source_fact_ids=source_ids,
            transaction_type=LedgerTransactionType(
                _string(value, "transaction_type")
            ),
            postings=tuple(
                _decode_posting(item)
                for item in _object_list(value, "postings")
            ),
            effective_time_ns=UnixNanos(
                _integer(value, "effective_time_ns")
            ),
            posted_at_ns=UnixNanos(_integer(value, "posted_at_ns")),
            ledger_sequence=_integer(value, "ledger_sequence"),
            mapping_policy_version=_integer(value, "mapping_policy_version"),
            reverses_transaction_id=_optional_new_type(
                value,
                "reverses_transaction_id",
                LedgerTransactionId,
            ),
        )
    except (KeyError, TypeError, ValueError):
        raise AccountingCodecError("ledger transaction is invalid") from None


def observed_fact_checksum(value: ObservedFinancialFact) -> str:
    return _checksum(encode_observed_financial_fact(value)["fact"])


def observation_checksum(value: FinancialFactObservation) -> str:
    return _checksum(_encode_observation(value))


def _encode_observation(value: FinancialFactObservation) -> JsonObject:
    return {
        "observation_id": str(value.observation_id),
        "fact_id": str(value.fact_id),
        "source_kind": value.source_kind.value,
        "observed_at_ns": int(value.observed_at_ns),
        "source_cursor": value.source_cursor,
        "payload_fingerprint": value.payload_fingerprint,
    }


def _encode_metadata(value: FinancialFactMetadata) -> JsonObject:
    return {
        "fact_id": str(value.fact_id),
        "venue": str(value.venue),
        "account_id": str(value.account_id),
        "venue_reference": value.venue_reference,
        "effective_time_ns": int(value.effective_time_ns),
        "schema_version": value.schema_version,
    }


def _decode_metadata(value: JsonObject) -> FinancialFactMetadata:
    return FinancialFactMetadata(
        fact_id=FinancialFactId(_string(value, "fact_id")),
        venue=VenueId(_string(value, "venue")),
        account_id=AccountId(_string(value, "account_id")),
        venue_reference=_string(value, "venue_reference"),
        effective_time_ns=UnixNanos(_integer(value, "effective_time_ns")),
        schema_version=_integer(value, "schema_version"),
    )


def _encode_component(value: CashComponent) -> JsonObject:
    return {
        "asset": str(value.asset),
        "signed_amount": _encode_fixed(value.signed_amount),
    }


def _decode_component(value: JsonObject) -> CashComponent:
    return CashComponent(
        asset=AssetId(_string(value, "asset")),
        signed_amount=Money(**_fixed_kwargs(value, "signed_amount")),
    )


def _encode_instrument_id(value: InstrumentId) -> JsonObject:
    return {
        "venue": str(value.venue),
        "kind": value.kind.value,
        "symbol": value.symbol,
    }


def _decode_instrument_id(value: JsonObject) -> InstrumentId:
    return InstrumentId(
        venue=VenueId(_string(value, "venue")),
        kind=InstrumentKind(_string(value, "kind")),
        symbol=_string(value, "symbol"),
    )


def _encode_posting(value: LedgerPosting) -> JsonObject:
    return {
        "posting_id": str(value.posting_id),
        "account": {
            "ledger_account_id": str(value.account.ledger_account_id),
            "venue": str(value.account.venue),
            "account_id": str(value.account.account_id),
            "account_type": value.account.account_type.value,
            "asset": str(value.account.asset),
        },
        "signed_amount": _encode_fixed(value.signed_amount),
        "memo": value.memo,
    }


def _decode_posting(value: JsonObject) -> LedgerPosting:
    account_raw = _object(value, "account")
    return LedgerPosting(
        posting_id=LedgerPostingId(_string(value, "posting_id")),
        account=LedgerAccount(
            ledger_account_id=LedgerAccountId(
                _string(account_raw, "ledger_account_id")
            ),
            venue=VenueId(_string(account_raw, "venue")),
            account_id=AccountId(_string(account_raw, "account_id")),
            account_type=LedgerAccountType(
                _string(account_raw, "account_type")
            ),
            asset=AssetId(_string(account_raw, "asset")),
        ),
        signed_amount=Money(**_fixed_kwargs(value, "signed_amount")),
        memo=_string(value, "memo", allow_empty=True),
    )


def _encode_fixed(value: Money | Price | Quantity) -> JsonObject:
    return {"raw": value.raw, "scale": value.scale}


def _fixed_kwargs(value: JsonObject, key: str) -> dict[str, int]:
    raw = _object(value, key)
    return {
        "raw": _integer(raw, "raw", allow_negative=True),
        "scale": _integer(raw, "scale"),
    }


def _optional_string(value: object | None) -> str | None:
    return None if value is None else str(value)


def _optional_string_value(value: JsonObject, key: str) -> str | None:
    item = value.get(key)
    if item is None:
        return None
    if not isinstance(item, str):
        raise AccountingCodecError(f"{key} must be a string or null")
    return item


def _optional_new_type(
    value: JsonObject,
    key: str,
    constructor: Callable[[str], T],
) -> T | None:
    item = _optional_string_value(value, key)
    if item is None:
        return None
    return constructor(item)


def _object(value: JsonObject, key: str) -> JsonObject:
    return _required_object(value.get(key), key)


def _required_object(value: JsonValue | None, name: str) -> JsonObject:
    if not isinstance(value, dict):
        raise AccountingCodecError(f"{name} must be an object")
    return value


def _list(value: JsonObject, key: str) -> list[JsonValue]:
    item = value.get(key)
    if not isinstance(item, list):
        raise AccountingCodecError(f"{key} must be a list")
    return item


def _object_list(value: JsonObject, key: str) -> tuple[JsonObject, ...]:
    return tuple(_required_object(item, key) for item in _list(value, key))


def _string(value: JsonObject, key: str, *, allow_empty: bool = False) -> str:
    return _required_string(value.get(key), key, allow_empty=allow_empty)


def _required_string(
    value: JsonValue | None,
    name: str,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise AccountingCodecError(f"{name} must be a string")
    return value


def _integer(
    value: JsonObject,
    key: str,
    *,
    allow_negative: bool = False,
) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise AccountingCodecError(f"{key} must be an integer")
    if not allow_negative and item < 0:
        raise AccountingCodecError(f"{key} cannot be negative")
    return item


def _checksum(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def canonical_json(value: JsonValue) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise AccountingCodecError("value is not canonical JSON") from None


__all__ = [
    "AccountingCodecError",
    "JsonObject",
    "JsonScalar",
    "JsonValue",
    "canonical_json",
    "decode_ledger_transaction",
    "decode_observed_financial_fact",
    "encode_ledger_transaction",
    "encode_observed_financial_fact",
    "observation_checksum",
    "observed_fact_checksum",
]
