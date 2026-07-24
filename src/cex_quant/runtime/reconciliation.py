"""Startup order reconciliation with a bounded private-stream race buffer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from cex_quant.core import ClientOrderId, UnixNanos
from cex_quant.execution import (
    ExecutionGatewayError,
    OrderReconciliationGateway,
    QueryOrder,
)
from cex_quant.oms import (
    OrderReconciliationSnapshot,
    OrderView,
    ReconciliationDisposition,
    ReconciliationResult,
    ReconciliationSource,
)


class ReconciliationOms(Protocol):
    def reconciliation_candidates(self) -> tuple[OrderView, ...]: ...

    def reconcile(
        self,
        snapshot: OrderReconciliationSnapshot,
    ) -> ReconciliationResult: ...

    def reconcile_not_found(
        self,
        client_order_id: ClientOrderId,
        *,
        source: ReconciliationSource,
        observed_at_ns: UnixNanos,
    ) -> ReconciliationResult: ...


class StartupReconciliationState(StrEnum):
    NEW = "new"
    BUFFERING = "buffering"
    RECONCILING = "reconciling"
    LIVE = "live"
    DEGRADED = "degraded"
    FAILED = "failed"


class StartupReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class StartupQueryResult:
    client_order_id: ClientOrderId
    disposition: ReconciliationDisposition | None
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.disposition not in {
            None,
            ReconciliationDisposition.CONFLICT,
            ReconciliationDisposition.NOT_FOUND,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class StartupReconciliationReport:
    state: StartupReconciliationState
    queries: tuple[StartupQueryResult, ...]
    stream_observations: int

    @property
    def ready(self) -> bool:
        return self.state is StartupReconciliationState.LIVE


class StartupOrderReconciliationCoordinator:
    """Subscribe first, buffer events, query REST, then apply by venue time."""

    def __init__(
        self,
        *,
        oms: ReconciliationOms,
        gateway: OrderReconciliationGateway,
        now_ns: Callable[[], UnixNanos],
        max_buffered_observations: int = 10_000,
    ) -> None:
        if max_buffered_observations < 1:
            raise ValueError("max_buffered_observations must be positive")
        self._oms = oms
        self._gateway = gateway
        self._now_ns = now_ns
        self._max_buffered_observations = max_buffered_observations
        self._buffer: list[OrderReconciliationSnapshot] = []
        self._state = StartupReconciliationState.NEW

    @property
    def state(self) -> StartupReconciliationState:
        return self._state

    def begin_buffering(self) -> None:
        if self._state is not StartupReconciliationState.NEW:
            raise StartupReconciliationError(
                f"cannot begin buffering from {self._state.value}"
            )
        self._state = StartupReconciliationState.BUFFERING

    async def on_stream_snapshot(
        self,
        snapshot: OrderReconciliationSnapshot,
    ) -> ReconciliationResult | None:
        if snapshot.source is not ReconciliationSource.USER_STREAM:
            raise ValueError("stream callback requires a USER_STREAM snapshot")
        if self._state in {
            StartupReconciliationState.BUFFERING,
            StartupReconciliationState.RECONCILING,
        }:
            if len(self._buffer) >= self._max_buffered_observations:
                self._state = StartupReconciliationState.FAILED
                raise StartupReconciliationError(
                    "private-stream startup buffer overflow"
                )
            self._buffer.append(snapshot)
            return None
        if self._state in {
            StartupReconciliationState.LIVE,
            StartupReconciliationState.DEGRADED,
        }:
            return self._oms.reconcile(snapshot)
        raise StartupReconciliationError(
            f"cannot accept stream update in {self._state.value}"
        )

    async def reconcile_startup(self) -> StartupReconciliationReport:
        if self._state is not StartupReconciliationState.BUFFERING:
            raise StartupReconciliationError(
                f"cannot reconcile from {self._state.value}"
            )
        self._state = StartupReconciliationState.RECONCILING
        query_results: list[StartupQueryResult] = []
        observations: list[OrderReconciliationSnapshot] = []
        try:
            candidates = self._oms.reconciliation_candidates()
            for view in candidates:
                command = QueryOrder(
                    account_id=view.request.account_id,
                    instrument_id=view.request.instrument_id,
                    client_order_id=view.request.client_order_id,
                )
                try:
                    snapshot = await self._gateway.query_order(command)
                except ExecutionGatewayError as error:
                    query_results.append(
                        StartupQueryResult(
                            client_order_id=command.client_order_id,
                            disposition=None,
                            reason=str(error),
                        )
                    )
                    continue
                if snapshot is None:
                    result = self._oms.reconcile_not_found(
                        command.client_order_id,
                        source=ReconciliationSource.REST_QUERY,
                        observed_at_ns=self._now_ns(),
                    )
                    query_results.append(
                        StartupQueryResult(
                            client_order_id=command.client_order_id,
                            disposition=result.disposition,
                            reason=result.reason,
                        )
                    )
                    continue
                if snapshot.client_order_id != command.client_order_id:
                    raise StartupReconciliationError(
                        "query response client order identity mismatch"
                    )
                if snapshot.source is not ReconciliationSource.REST_QUERY:
                    raise StartupReconciliationError(
                        "query response must use REST_QUERY source"
                    )
                observations.append(snapshot)

            buffered_count = len(self._buffer)
            observations.extend(self._buffer)
            self._buffer.clear()
            observations.sort(key=_observation_order)
            query_by_id = {
                result.client_order_id: result for result in query_results
            }
            observation_conflict = False
            for snapshot in observations:
                result = self._oms.reconcile(snapshot)
                if (
                    result.disposition
                    is ReconciliationDisposition.CONFLICT
                ):
                    observation_conflict = True
                if snapshot.source is ReconciliationSource.REST_QUERY:
                    query_by_id[snapshot.client_order_id] = StartupQueryResult(
                        client_order_id=snapshot.client_order_id,
                        disposition=result.disposition,
                        reason=result.reason,
                    )
            query_results = [
                query_by_id[view.request.client_order_id]
                for view in candidates
                if view.request.client_order_id in query_by_id
            ]
            ready = (
                not observation_conflict
                and len(query_results) == len(candidates)
                and all(result.resolved for result in query_results)
            )
            self._state = (
                StartupReconciliationState.LIVE
                if ready
                else StartupReconciliationState.DEGRADED
            )
            return StartupReconciliationReport(
                state=self._state,
                queries=tuple(query_results),
                stream_observations=buffered_count,
            )
        except BaseException:
            self._state = StartupReconciliationState.FAILED
            raise


def _observation_order(
    snapshot: OrderReconciliationSnapshot,
) -> tuple[int, int, str]:
    source_order = (
        0 if snapshot.source is ReconciliationSource.REST_QUERY else 1
    )
    return (
        int(snapshot.observed_at_ns),
        source_order,
        snapshot.source_update_id,
    )


__all__ = [
    "ReconciliationOms",
    "StartupOrderReconciliationCoordinator",
    "StartupQueryResult",
    "StartupReconciliationError",
    "StartupReconciliationReport",
    "StartupReconciliationState",
]
