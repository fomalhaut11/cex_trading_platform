"""Project contiguous durable OMS fill effects into Portfolio inputs."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from cex_quant.core import AccountId, EventId, Quantity
from cex_quant.oms import (
    GroupActionPreparedEntry,
    GroupStagePreparedEntry,
    OmsJournal,
    OrderCreatedEntry,
    OrderRequest,
    OrderSide,
    VenueEventEntry,
)
from cex_quant.portfolio import (
    ExecutionPositionEffect,
    ExecutionPositionEffectBatch,
)


class OmsExecutionProjectionError(RuntimeError):
    pass


class OmsExecutionEffectProjector:
    """Derive signed incremental fills from a complete ordered OMS scan."""

    def __init__(self, journal: OmsJournal) -> None:
        self._journal = journal

    def project(
        self,
        account_id: AccountId,
        *,
        from_sequence_exclusive: int,
    ) -> ExecutionPositionEffectBatch | None:
        if not account_id:
            raise ValueError("account_id cannot be empty")
        if from_sequence_exclusive < 0:
            raise ValueError("projection start cannot be negative")
        requests: dict[str, OrderRequest] = {}
        cumulative: dict[str, Decimal] = {}
        effects: list[ExecutionPositionEffect] = []
        through_sequence = 0
        for sequence, entry in enumerate(self._journal.read(), start=1):
            through_sequence = sequence
            if isinstance(entry, GroupActionPreparedEntry):
                _remember_request(requests, entry.request)
                continue
            if isinstance(entry, GroupStagePreparedEntry):
                for stage_request in entry.requests:
                    _remember_request(requests, stage_request)
                continue
            if isinstance(entry, OrderCreatedEntry):
                _remember_request(requests, entry.request)
                continue
            if not isinstance(entry, VenueEventEntry):
                continue
            event = entry.event
            key = str(event.client_order_id)
            current = event.cumulative_filled_quantity.as_decimal()
            previous = cumulative.get(key, Decimal(0))
            if current < previous:
                raise OmsExecutionProjectionError(
                    "OMS cumulative fill regressed during projection"
                )
            cumulative[key] = current
            if sequence <= from_sequence_exclusive or current == previous:
                continue
            request = requests.get(key)
            if request is None:
                raise OmsExecutionProjectionError(
                    "fill event has no preceding durable order request"
                )
            if request.account_id != account_id:
                continue
            unsigned_delta = current - previous
            signed_delta = (
                unsigned_delta
                if request.side is OrderSide.BUY
                else -unsigned_delta
            )
            effects.append(
                ExecutionPositionEffect(
                    effect_id=_effect_id(
                        sequence=sequence,
                        request=request,
                        venue_update_id=event.venue_update_id,
                        cumulative=current,
                    ),
                    oms_journal_sequence=sequence,
                    client_order_id=request.client_order_id,
                    account_id=request.account_id,
                    instrument_id=request.instrument_id,
                    cumulative_filled_quantity=(
                        event.cumulative_filled_quantity
                    ),
                    signed_fill_delta=Quantity.from_str(
                        format(signed_delta, "f")
                    ),
                    accepted_at_ns=event.event_time_ns,
                )
            )
        if through_sequence < from_sequence_exclusive:
            raise OmsExecutionProjectionError(
                "Portfolio coverage exceeds the durable OMS journal"
            )
        if through_sequence == from_sequence_exclusive:
            return None
        return ExecutionPositionEffectBatch(
            from_sequence_exclusive=from_sequence_exclusive,
            through_sequence_inclusive=through_sequence,
            effects=tuple(effects),
        )


def _remember_request(
    requests: dict[str, OrderRequest],
    request: OrderRequest,
) -> None:
    key = str(request.client_order_id)
    previous = requests.get(key)
    if previous is not None and previous != request:
        raise OmsExecutionProjectionError(
            "client order identity changed during OMS projection"
        )
    requests[key] = request


def _effect_id(
    *,
    sequence: int,
    request: OrderRequest,
    venue_update_id: str,
    cumulative: Decimal,
) -> EventId:
    encoded = json.dumps(
        {
            "client_order_id": str(request.client_order_id),
            "cumulative": format(cumulative, "f"),
            "oms_journal_sequence": sequence,
            "venue_update_id": venue_update_id,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return EventId(hashlib.sha256(encoded).hexdigest())


__all__ = [
    "OmsExecutionEffectProjector",
    "OmsExecutionProjectionError",
]
