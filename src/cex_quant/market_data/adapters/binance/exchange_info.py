"""Pure Binance `exchangeInfo` to canonical instrument mapping."""

from __future__ import annotations

import json
from enum import StrEnum
from json import JSONDecodeError
from typing import Any

from cex_quant.core import AssetId, Money, Price, Quantity, UnixNanos
from cex_quant.instruments import (
    ContractValueType,
    FutureSpecification,
    Instrument,
    InstrumentId,
    InstrumentKind,
    InstrumentStatus,
    PerpetualSpecification,
    SettlementType,
    SpotSpecification,
)

from .normalizer import BINANCE_VENUE, BinanceProduct


class InstrumentMappingErrorCode(StrEnum):
    MALFORMED_PAYLOAD = "malformed_payload"
    MISSING_FIELD = "missing_field"
    INVALID_FIELD = "invalid_field"
    MISSING_FILTER = "missing_filter"
    UNSUPPORTED_PRODUCT = "unsupported_product"


class InstrumentMappingError(ValueError):
    def __init__(
        self,
        *,
        code: InstrumentMappingErrorCode,
        reason: str,
        symbol: str | None = None,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.reason = reason
        self.symbol = symbol
        self.field = field
        context = f" [symbol={symbol}]" if symbol is not None else ""
        if field is not None:
            context += f" [field={field}]"
        super().__init__(f"{code.value}: {reason}{context}")


class BinanceExchangeInfoParser:
    """Map one product family's public exchange information response."""

    def __init__(self, *, product: BinanceProduct) -> None:
        self._product = product

    def parse(self, payload: bytes) -> tuple[Instrument, ...]:
        try:
            decoded = json.loads(payload)
        except (JSONDecodeError, UnicodeDecodeError) as error:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.MALFORMED_PAYLOAD,
                reason="exchangeInfo is not valid UTF-8 JSON",
            ) from error
        if not isinstance(decoded, dict) or not isinstance(
            decoded.get("symbols"), list
        ):
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.MALFORMED_PAYLOAD,
                reason="exchangeInfo must contain a symbols array",
                field="symbols",
            )
        if self._product is BinanceProduct.OPTIONS:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.UNSUPPORTED_PRODUCT,
                reason="Binance options exchangeInfo mapping is not implemented",
            )
        instruments = []
        for raw_symbol in decoded["symbols"]:
            if not isinstance(raw_symbol, dict):
                raise InstrumentMappingError(
                    code=InstrumentMappingErrorCode.INVALID_FIELD,
                    reason="symbol entry must be an object",
                    field="symbols",
                )
            instruments.append(self._parse_symbol(raw_symbol))
        return tuple(instruments)

    def _parse_symbol(self, data: dict[str, Any]) -> Instrument:
        symbol = self._string(data, "symbol")
        base_asset = AssetId(self._string(data, "baseAsset", symbol))
        quote_asset = AssetId(self._string(data, "quoteAsset", symbol))
        filters = self._filters(data, symbol)
        price_filter = self._filter(filters, "PRICE_FILTER", symbol)
        lot_filter = self._filter(filters, "LOT_SIZE", symbol)
        price_increment = self._price(price_filter, "tickSize", symbol)
        quantity_increment = self._quantity(lot_filter, "stepSize", symbol)
        min_quantity = self._quantity(lot_filter, "minQty", symbol)
        min_notional = self._min_notional(filters, symbol)
        status_field = (
            "contractStatus"
            if self._product is BinanceProduct.COIN_M_FUTURES
            else "status"
        )
        status = self._status(self._string(data, status_field, symbol))

        if self._product is BinanceProduct.SPOT:
            kind = InstrumentKind.SPOT
            specification = SpotSpecification()
        else:
            margin_asset = AssetId(self._string(data, "marginAsset", symbol))
            contract_type = self._string(data, "contractType", symbol)
            value_type = (
                ContractValueType.INVERSE
                if self._product is BinanceProduct.COIN_M_FUTURES
                else ContractValueType.LINEAR
            )
            if self._product is BinanceProduct.COIN_M_FUTURES:
                contract_size = self._quantity(data, "contractSize", symbol)
                contract_size_asset = quote_asset
            else:
                contract_size = Quantity.from_str("1")
                contract_size_asset = base_asset
            if contract_type.endswith("PERPETUAL"):
                kind = InstrumentKind.PERPETUAL
                specification = PerpetualSpecification(
                    settlement_asset=margin_asset,
                    margin_asset=margin_asset,
                    contract_size=contract_size,
                    contract_size_asset=contract_size_asset,
                    value_type=value_type,
                )
            else:
                kind = InstrumentKind.FUTURE
                specification = FutureSpecification(
                    settlement_asset=margin_asset,
                    margin_asset=margin_asset,
                    contract_size=contract_size,
                    contract_size_asset=contract_size_asset,
                    value_type=value_type,
                    expiry_time_ns=UnixNanos(
                        self._non_negative_int(data, "deliveryDate", symbol)
                        * 1_000_000
                    ),
                    settlement_type=SettlementType.CASH,
                )

        return Instrument(
            instrument_id=InstrumentId(
                venue=BINANCE_VENUE,
                kind=kind,
                symbol=symbol,
            ),
            base_asset=base_asset,
            quote_asset=quote_asset,
            price_increment=price_increment,
            quantity_increment=quantity_increment,
            min_quantity=min_quantity,
            min_notional=min_notional,
            status=status,
            specification=specification,
        )

    def _filters(
        self, data: dict[str, Any], symbol: str
    ) -> dict[str, dict[str, Any]]:
        raw_filters = data.get("filters")
        if not isinstance(raw_filters, list):
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.MISSING_FIELD,
                reason="filters array is required",
                symbol=symbol,
                field="filters",
            )
        result: dict[str, dict[str, Any]] = {}
        for item in raw_filters:
            if isinstance(item, dict) and isinstance(item.get("filterType"), str):
                result[item["filterType"]] = item
        return result

    @staticmethod
    def _filter(
        filters: dict[str, dict[str, Any]], filter_type: str, symbol: str
    ) -> dict[str, Any]:
        result = filters.get(filter_type)
        if result is None:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.MISSING_FILTER,
                reason=f"{filter_type} is required",
                symbol=symbol,
                field="filters",
            )
        return result

    def _min_notional(
        self, filters: dict[str, dict[str, Any]], symbol: str
    ) -> Money | None:
        candidate = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
        if candidate is None:
            return None
        field = "minNotional" if "minNotional" in candidate else "notional"
        if field not in candidate:
            return None
        try:
            return Money.from_str(str(candidate[field]))
        except ValueError as error:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.INVALID_FIELD,
                reason=str(error),
                symbol=symbol,
                field=f"{candidate.get('filterType')}.{field}",
            ) from error

    @staticmethod
    def _status(value: str) -> InstrumentStatus:
        if value == "TRADING":
            return InstrumentStatus.ACTIVE
        if value in {"HALT", "BREAK", "CLOSE"}:
            return InstrumentStatus.HALTED
        if value in {"EXPIRED", "DELIVERING", "DELIVERED"}:
            return InstrumentStatus.EXPIRED
        return InstrumentStatus.PENDING

    def _price(
        self, data: dict[str, Any], field: str, symbol: str
    ) -> Price:
        try:
            return Price.from_str(str(self._required(data, field, symbol)))
        except ValueError as error:
            raise self._invalid(error, symbol, field) from error

    def _quantity(
        self, data: dict[str, Any], field: str, symbol: str
    ) -> Quantity:
        try:
            return Quantity.from_str(str(self._required(data, field, symbol)))
        except ValueError as error:
            raise self._invalid(error, symbol, field) from error

    def _string(
        self, data: dict[str, Any], field: str, symbol: str | None = None
    ) -> str:
        value = self._required(data, field, symbol)
        if not isinstance(value, str) or not value:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.INVALID_FIELD,
                reason="field must be a non-empty string",
                symbol=symbol,
                field=field,
            )
        return value

    def _non_negative_int(
        self, data: dict[str, Any], field: str, symbol: str
    ) -> int:
        value = self._required(data, field, symbol)
        if isinstance(value, bool):
            value = None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise self._invalid(error, symbol, field) from error
        if parsed < 0:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.INVALID_FIELD,
                reason="field must be non-negative",
                symbol=symbol,
                field=field,
            )
        return parsed

    @staticmethod
    def _required(
        data: dict[str, Any], field: str, symbol: str | None
    ) -> Any:
        if field not in data:
            raise InstrumentMappingError(
                code=InstrumentMappingErrorCode.MISSING_FIELD,
                reason="required field is absent",
                symbol=symbol,
                field=field,
            )
        return data[field]

    @staticmethod
    def _invalid(
        error: Exception, symbol: str, field: str
    ) -> InstrumentMappingError:
        return InstrumentMappingError(
            code=InstrumentMappingErrorCode.INVALID_FIELD,
            reason=str(error) or "invalid field",
            symbol=symbol,
            field=field,
        )


__all__ = [
    "BinanceExchangeInfoParser",
    "InstrumentMappingError",
    "InstrumentMappingErrorCode",
]
