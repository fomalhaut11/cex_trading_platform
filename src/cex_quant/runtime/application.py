"""Composition root for the complete synchronous trading application."""

from __future__ import annotations

from cex_quant.execution import ExecutionGateway
from cex_quant.market_data import MarketEvent

from .adapters import AsyncExecutionPortBridge
from .pipeline import (
    FeaturePort,
    HealthPort,
    MarketStatePort,
    OmsPort,
    PipelineRecorderPort,
    PipelineResult,
    PortfolioReadPort,
    RiskPort,
    StrategyPort,
    TradingPipeline,
    ValidationPort,
)


class TradingApplication:
    """Own lifecycle and composition of the mandatory risk-gated pipeline."""

    def __init__(
        self,
        *,
        health: HealthPort,
        validator: ValidationPort,
        market_state: MarketStatePort,
        features: FeaturePort,
        strategy: StrategyPort,
        portfolio: PortfolioReadPort,
        risk: RiskPort,
        oms: OmsPort,
        execution_gateway: ExecutionGateway,
        recorder: PipelineRecorderPort | None = None,
        execution_timeout_seconds: float = 10.0,
    ) -> None:
        self._execution = AsyncExecutionPortBridge(
            execution_gateway,
            timeout_seconds=execution_timeout_seconds,
        )
        self._pipeline = TradingPipeline(
            health=health,
            validator=validator,
            market_state=market_state,
            features=features,
            strategy=strategy,
            portfolio=portfolio,
            risk=risk,
            oms=oms,
            execution=self._execution,
            recorder=recorder,
        )
        self._started = False

    @property
    def pipeline(self) -> TradingPipeline:
        return self._pipeline

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        if self._started:
            return
        self._execution.start()
        self._started = True

    def process(self, event: MarketEvent) -> PipelineResult:
        if not self._started:
            raise RuntimeError("trading application is not started")
        return self._pipeline.process(event)

    def close(self) -> None:
        if not self._started:
            return
        self._execution.close()
        self._started = False

    def __enter__(self) -> TradingApplication:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = ["TradingApplication"]
