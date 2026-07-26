"""Concrete deployment assembly for secure operator control."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from cex_quant.execution import ExecutionGateway
from cex_quant.market_data import MarketEvent
from cex_quant.observability import Clock, HealthCheck

from .application import TradingApplication
from .operations import (
    OperatorAction,
    OperatorCommand,
    OperatorControlDurabilityError,
    OperatorController,
    OperatorRiskGate,
    RiskEvaluator,
    RuntimeHealthService,
)
from .operations_journal import JsonLinesOperatorCommandJournal
from .operator_auth import (
    AuthenticatedOperatorCommandService,
    EnvironmentOperatorKeyProvider,
    HmacOperatorCommandAuthenticator,
    OperatorKeyBinding,
)
from .operator_endpoint import (
    OperatorAuditSink,
    OperatorCommandEndpoint,
    OperatorRequestRateLimiter,
)
from .pipeline import (
    FeaturePort,
    MarketStatePort,
    OmsPort,
    PipelineRecorderPort,
    PipelineResult,
    PortfolioReadPort,
    StrategyPort,
    ValidationPort,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorControlDeploymentConfig:
    """Non-secret inputs required to assemble operator control."""

    journal_path: Path
    key_bindings: Mapping[str, OperatorKeyBinding]
    command_history_size: int = 256
    max_journal_records: int = 10_000
    max_validity_ns: int = 60_000_000_000
    clock_skew_ns: int = 5_000_000_000

    def __post_init__(self) -> None:
        if not isinstance(self.journal_path, Path):
            raise ValueError("journal_path must be a Path")
        if not self.journal_path.parent.is_dir():
            raise ValueError("journal parent directory must already exist")
        if not isinstance(self.key_bindings, Mapping) or not self.key_bindings:
            raise ValueError("key_bindings must be a non-empty mapping")
        copied_bindings = dict(self.key_bindings)
        if any(
            not isinstance(key_id, str)
            or not isinstance(binding, OperatorKeyBinding)
            for key_id, binding in copied_bindings.items()
        ):
            raise ValueError("key_bindings contains an invalid binding")
        object.__setattr__(
            self,
            "key_bindings",
            MappingProxyType(copied_bindings),
        )
        for name, value in (
            ("command_history_size", self.command_history_size),
            ("max_journal_records", self.max_journal_records),
            ("max_validity_ns", self.max_validity_ns),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise ValueError(f"{name} must be a positive int")
        if (
            not isinstance(self.clock_skew_ns, int)
            or isinstance(self.clock_skew_ns, bool)
            or self.clock_skew_ns < 0
        ):
            raise ValueError("clock_skew_ns must be a non-negative int")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorEndpointDeploymentConfig:
    """Non-secret resource limits for the external operator endpoint."""

    max_request_bytes: int = 4_096
    max_concurrency: int = 4
    max_requests_per_window: int = 10
    rate_window_ns: int = 1_000_000_000
    max_clients: int = 128

    def __post_init__(self) -> None:
        for name, value in (
            ("max_request_bytes", self.max_request_bytes),
            ("max_concurrency", self.max_concurrency),
            ("max_requests_per_window", self.max_requests_per_window),
            ("rate_window_ns", self.rate_window_ns),
            ("max_clients", self.max_clients),
        ):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
            ):
                raise ValueError(f"{name} must be a positive int")


class OperatorControlRuntime:
    """Own the journal, controller, authentication and health composition."""

    def __init__(
        self,
        *,
        config: OperatorControlDeploymentConfig,
        clock: Clock,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(config, OperatorControlDeploymentConfig):
            raise ValueError("config must be an OperatorControlDeploymentConfig")
        self._clock = clock
        self._journal = JsonLinesOperatorCommandJournal(
            config.journal_path,
            max_records=config.max_journal_records,
        )
        try:
            self.controller = OperatorController(
                clock=clock,
                command_history_size=config.command_history_size,
                journal=self._journal,
            )
            provider = EnvironmentOperatorKeyProvider(
                bindings=config.key_bindings,
                environ=os.environ if environ is None else environ,
            )
            authenticator = HmacOperatorCommandAuthenticator(
                clock=clock,
                key_provider=provider,
                max_validity_ns=config.max_validity_ns,
                clock_skew_ns=config.clock_skew_ns,
            )
            self.commands = AuthenticatedOperatorCommandService(
                authenticator=authenticator,
                controller=self.controller,
            )
            self.health = RuntimeHealthService(
                component="operator-runtime",
                clock=clock,
                checks=(self.controller,),
            )
        except Exception:
            self._journal.close()
            raise
        self._closed = False
        self._endpoint: OperatorCommandEndpoint | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    def risk_gate(self, delegate: RiskEvaluator) -> OperatorRiskGate:
        if self._closed:
            raise RuntimeError("operator control runtime is closed")
        return OperatorRiskGate(
            delegate=delegate,
            controller=self.controller,
        )

    def create_endpoint(
        self,
        *,
        config: OperatorEndpointDeploymentConfig,
        audit_sink: OperatorAuditSink,
    ) -> OperatorCommandEndpoint:
        if self._closed:
            raise RuntimeError("operator control runtime is closed")
        if not isinstance(config, OperatorEndpointDeploymentConfig):
            raise ValueError(
                "config must be an OperatorEndpointDeploymentConfig"
            )
        if self._endpoint is not None:
            raise RuntimeError("operator endpoint is already assembled")
        endpoint = OperatorCommandEndpoint(
            clock=self._clock,
            executor=self.commands,
            audit_sink=audit_sink,
            rate_limiter=OperatorRequestRateLimiter(
                clock=self._clock,
                max_requests=config.max_requests_per_window,
                window_ns=config.rate_window_ns,
                max_clients=config.max_clients,
            ),
            failure_handler=self._halt_for_endpoint_failure,
            max_request_bytes=config.max_request_bytes,
            max_concurrency=config.max_concurrency,
        )
        self._endpoint = endpoint
        return endpoint

    def close(self) -> None:
        if self._closed:
            return
        self._journal.close()
        self._closed = True

    def __enter__(self) -> OperatorControlRuntime:
        if self._closed:
            raise RuntimeError("operator control runtime is closed")
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _halt_for_endpoint_failure(self, code: str) -> None:
        snapshot = self.controller.snapshot
        command = OperatorCommand(
            command_id=(
                "operator-endpoint-failure-"
                f"{snapshot.generation + 1}-{int(self._clock.wall_time_ns())}"
            ),
            action=OperatorAction.HALT,
            actor="operator-endpoint",
            reason=f"fail closed after {code.lower()}",
        )
        try:
            self.controller.apply(command)
        except OperatorControlDurabilityError:
            return


class TradingDeploymentRuntime:
    """Assemble the core application with mandatory operator safety gates."""

    def __init__(
        self,
        *,
        operator_config: OperatorControlDeploymentConfig,
        clock: Clock,
        health_checks: tuple[HealthCheck, ...],
        validator: ValidationPort,
        market_state: MarketStatePort,
        features: FeaturePort,
        strategy: StrategyPort,
        portfolio: PortfolioReadPort,
        risk: RiskEvaluator,
        oms: OmsPort,
        execution_gateway: ExecutionGateway,
        recorder: PipelineRecorderPort | None = None,
        environ: Mapping[str, str] | None = None,
        execution_timeout_seconds: float = 10.0,
    ) -> None:
        if not isinstance(health_checks, tuple):
            raise ValueError("health_checks must be a tuple")
        self.operator = OperatorControlRuntime(
            config=operator_config,
            clock=clock,
            environ=environ,
        )
        try:
            checks = (*health_checks, self.operator.controller)
            self.health = RuntimeHealthService(
                component="trading-runtime",
                clock=clock,
                checks=checks,
            )
            self.application = TradingApplication(
                health=self.health,
                validator=validator,
                market_state=market_state,
                features=features,
                strategy=strategy,
                portfolio=portfolio,
                risk=self.operator.risk_gate(risk),
                oms=oms,
                execution_gateway=execution_gateway,
                recorder=recorder,
                execution_timeout_seconds=execution_timeout_seconds,
            )
        except Exception:
            self.operator.close()
            raise
        self._closed = False

    @property
    def started(self) -> bool:
        return self.application.started

    @property
    def closed(self) -> bool:
        return self._closed

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("trading deployment runtime is closed")
        self.application.start()

    def process(self, event: MarketEvent) -> PipelineResult:
        if self._closed:
            raise RuntimeError("trading deployment runtime is closed")
        return self.application.process(event)

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.application.close()
        finally:
            self.operator.close()
            self._closed = True

    def __enter__(self) -> TradingDeploymentRuntime:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = [
    "OperatorControlDeploymentConfig",
    "OperatorControlRuntime",
    "OperatorEndpointDeploymentConfig",
    "TradingDeploymentRuntime",
]
