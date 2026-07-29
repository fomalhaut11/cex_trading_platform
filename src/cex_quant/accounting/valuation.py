"""Pure policy-bound reporting valuation over original-asset amounts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from itertools import pairwise

from cex_quant.core import AssetId, Money, PositionId, Rate, UnixNanos
from cex_quant.snapshots import DecisionSnapshotId

from .ownership import EconomicOwnerRef

_POLICY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,126}$")


class ValuationCompleteness(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class ConversionTimeBasis(StrEnum):
    ECONOMIC_TIME = "economic_time"
    SNAPSHOT_TIME = "snapshot_time"


class ValuationRoundingMode(StrEnum):
    HALF_EVEN = "half_even"
    DOWN = "down"


class ConversionQuoteConvention(StrEnum):
    DESTINATION_PER_SOURCE = "destination_per_source"


@dataclass(frozen=True, slots=True, kw_only=True)
class ValuationPolicyRef:
    name: str
    version: int
    reporting_asset: AssetId
    allowed_source_ids: tuple[str, ...]
    path_priority: tuple[tuple[AssetId, ...], ...]
    maximum_age_ns: int
    maximum_coherence_ns: int
    maximum_hops: int
    output_scale: int
    rounding_mode: ValuationRoundingMode
    time_basis: ConversionTimeBasis

    def __post_init__(self) -> None:
        if not _POLICY_NAME_PATTERN.fullmatch(self.name):
            raise ValueError("valuation policy name is invalid")
        if self.version <= 0:
            raise ValueError("valuation policy version must be positive")
        _require_identifier(self.reporting_asset, "reporting_asset")
        if (
            self.allowed_source_ids
            != tuple(sorted(self.allowed_source_ids))
            or len(set(self.allowed_source_ids))
            != len(self.allowed_source_ids)
        ):
            raise ValueError(
                "valuation allowed_source_ids must be unique and sorted"
            )
        if any(
            not item or item != item.strip()
            for item in self.allowed_source_ids
        ):
            raise ValueError("valuation source identity is invalid")
        if self.maximum_age_ns < 0 or self.maximum_coherence_ns < 0:
            raise ValueError("valuation time bounds cannot be negative")
        if self.maximum_hops <= 0 or self.maximum_hops > 8:
            raise ValueError("maximum_hops is outside bounds")
        if self.output_scale < 0 or self.output_scale > 18:
            raise ValueError("valuation output_scale is outside bounds")
        if len(set(self.path_priority)) != len(self.path_priority):
            raise ValueError("valuation paths must be unique")
        for path in self.path_priority:
            if len(path) < 2 or len(path) - 1 > self.maximum_hops:
                raise ValueError("valuation path hop count is outside bounds")
            if path[-1] != self.reporting_asset:
                raise ValueError(
                    "valuation path must end in reporting asset"
                )
            if len(set(path)) != len(path):
                raise ValueError("valuation path cannot contain a cycle")
            for asset in path:
                _require_identifier(asset, "path asset")

    @property
    def canonical(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConversionRateEvidence:
    valuation_snapshot_id: DecisionSnapshotId
    policy_version: int
    source_asset: AssetId
    destination_asset: AssetId
    rate: Rate
    quote_convention: ConversionQuoteConvention
    source_id: str
    source_as_of_ns: UnixNanos
    observed_at_ns: UnixNanos
    path: tuple[AssetId, ...]
    hop_index: int
    inverted_from_source: bool = False

    def __post_init__(self) -> None:
        _require_identifier(
            self.valuation_snapshot_id,
            "valuation_snapshot_id",
        )
        _require_identifier(self.source_asset, "source_asset")
        _require_identifier(self.destination_asset, "destination_asset")
        _require_identifier(self.source_id, "source_id")
        if self.policy_version <= 0:
            raise ValueError("conversion policy_version must be positive")
        if self.source_asset == self.destination_asset:
            raise ValueError("conversion edge assets must differ")
        if self.rate.raw <= 0:
            raise ValueError("conversion rate must be positive")
        if self.source_as_of_ns < 0 or self.observed_at_ns < 0:
            raise ValueError("conversion times cannot be negative")
        if self.observed_at_ns < self.source_as_of_ns:
            raise ValueError("conversion observation precedes source time")
        if (
            self.hop_index < 0
            or self.hop_index + 1 >= len(self.path)
            or self.path[self.hop_index] != self.source_asset
            or self.path[self.hop_index + 1] != self.destination_asset
        ):
            raise ValueError("conversion edge does not match path hop")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValuedAmount:
    original_asset: AssetId
    original_amount: Money
    reporting_asset: AssetId
    reporting_amount: Money | None
    evidence: tuple[ConversionRateEvidence, ...]
    completeness: ValuationCompleteness
    issue: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionValueInput:
    position_id: PositionId
    owner: EconomicOwnerRef
    original_asset: AssetId
    unrealized_value: Money


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionValuation:
    position_id: PositionId
    owner: EconomicOwnerRef
    original_asset: AssetId
    original_value: Money
    reporting_value: Money | None
    conversion_evidence: tuple[ConversionRateEvidence, ...]
    completeness: ValuationCompleteness
    issue: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ValuationSnapshot:
    valuation_snapshot_id: DecisionSnapshotId
    as_of_ns: UnixNanos
    reporting_asset: AssetId
    position_values: tuple[PositionValuation, ...]
    unrealized_pnl: Money | None
    valuation_policy: ValuationPolicyRef
    conversion_evidence: tuple[ConversionRateEvidence, ...]
    completeness: ValuationCompleteness


def value_amount(
    *,
    original_asset: AssetId,
    original_amount: Money,
    valuation_snapshot_id: DecisionSnapshotId,
    reference_time_ns: UnixNanos,
    policy: ValuationPolicyRef,
    evidence: tuple[ConversionRateEvidence, ...],
) -> ValuedAmount:
    """Convert through the first declared complete path, never opportunistically."""

    if reference_time_ns < 0:
        raise ValueError("valuation reference_time_ns cannot be negative")
    if original_asset == policy.reporting_asset:
        return ValuedAmount(
            original_asset=original_asset,
            original_amount=original_amount,
            reporting_asset=policy.reporting_asset,
            reporting_amount=original_amount.rescale_exact(
                max(original_amount.scale, policy.output_scale)
            ),
            evidence=(),
            completeness=ValuationCompleteness.COMPLETE,
            issue=None,
        )
    paths = tuple(
        item
        for item in policy.path_priority
        if item[0] == original_asset
    )
    if not paths:
        return _incomplete(
            original_asset,
            original_amount,
            policy,
            "no declared conversion path",
        )
    problems: list[str] = []
    for path in paths:
        selected: list[ConversionRateEvidence] = []
        path_issue: str | None = None
        for hop_index, (source, destination) in enumerate(
            pairwise(path)
        ):
            candidates = tuple(
                item
                for item in evidence
                if (
                    item.valuation_snapshot_id == valuation_snapshot_id
                    and item.policy_version == policy.version
                    and item.path == path
                    and item.hop_index == hop_index
                    and item.source_asset == source
                    and item.destination_asset == destination
                )
            )
            if len(candidates) != 1:
                path_issue = (
                    f"path hop {hop_index} has "
                    f"{len(candidates)} matching rates"
                )
                break
            rate = candidates[0]
            if rate.source_id not in policy.allowed_source_ids:
                path_issue = f"path hop {hop_index} source is not allowed"
                break
            if rate.source_as_of_ns > reference_time_ns:
                path_issue = f"path hop {hop_index} is from the future"
                break
            if (
                reference_time_ns - rate.source_as_of_ns
                > policy.maximum_age_ns
            ):
                path_issue = f"path hop {hop_index} is stale"
                break
            selected.append(rate)
        if path_issue is not None:
            problems.append(path_issue)
            continue
        source_times = tuple(item.source_as_of_ns for item in selected)
        if (
            max(source_times) - min(source_times)
            > policy.maximum_coherence_ns
        ):
            problems.append("path rates are not time-coherent")
            continue
        converted = original_amount.as_decimal()
        for item in selected:
            converted *= item.rate.as_decimal()
        rounding = {
            ValuationRoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
            ValuationRoundingMode.DOWN: ROUND_DOWN,
        }[policy.rounding_mode]
        quantizer = Decimal(1).scaleb(-policy.output_scale)
        rounded = converted.quantize(quantizer, rounding=rounding)
        return ValuedAmount(
            original_asset=original_asset,
            original_amount=original_amount,
            reporting_asset=policy.reporting_asset,
            reporting_amount=Money.from_str(
                format(rounded, f".{policy.output_scale}f")
            ),
            evidence=tuple(selected),
            completeness=ValuationCompleteness.COMPLETE,
            issue=None,
        )
    return _incomplete(
        original_asset,
        original_amount,
        policy,
        "; ".join(problems),
    )


def build_valuation_snapshot(
    *,
    valuation_snapshot_id: DecisionSnapshotId,
    as_of_ns: UnixNanos,
    positions: tuple[PositionValueInput, ...],
    policy: ValuationPolicyRef,
    evidence: tuple[ConversionRateEvidence, ...],
) -> ValuationSnapshot:
    values: list[PositionValuation] = []
    used_evidence: dict[
        tuple[tuple[AssetId, ...], int],
        ConversionRateEvidence,
    ] = {}
    total = Money(raw=0, scale=policy.output_scale)
    complete = True
    for position in positions:
        valued = value_amount(
            original_asset=position.original_asset,
            original_amount=position.unrealized_value,
            valuation_snapshot_id=valuation_snapshot_id,
            reference_time_ns=as_of_ns,
            policy=policy,
            evidence=evidence,
        )
        values.append(
            PositionValuation(
                position_id=position.position_id,
                owner=position.owner,
                original_asset=position.original_asset,
                original_value=position.unrealized_value,
                reporting_value=valued.reporting_amount,
                conversion_evidence=valued.evidence,
                completeness=valued.completeness,
                issue=valued.issue,
            )
        )
        if valued.reporting_amount is None:
            complete = False
        else:
            total = _add_money(total, valued.reporting_amount)
        for item in valued.evidence:
            used_evidence[(item.path, item.hop_index)] = item
    return ValuationSnapshot(
        valuation_snapshot_id=valuation_snapshot_id,
        as_of_ns=as_of_ns,
        reporting_asset=policy.reporting_asset,
        position_values=tuple(values),
        unrealized_pnl=total if complete else None,
        valuation_policy=policy,
        conversion_evidence=tuple(used_evidence.values()),
        completeness=(
            ValuationCompleteness.COMPLETE
            if complete
            else ValuationCompleteness.INCOMPLETE
        ),
    )


def _incomplete(
    original_asset: AssetId,
    original_amount: Money,
    policy: ValuationPolicyRef,
    issue: str,
) -> ValuedAmount:
    return ValuedAmount(
        original_asset=original_asset,
        original_amount=original_amount,
        reporting_asset=policy.reporting_asset,
        reporting_amount=None,
        evidence=(),
        completeness=ValuationCompleteness.INCOMPLETE,
        issue=issue,
    )


def _add_money(first: Money, second: Money) -> Money:
    scale = max(first.scale, second.scale)
    return Money(
        raw=(
            first.raw * 10 ** (scale - first.scale)
            + second.raw * 10 ** (scale - second.scale)
        ),
        scale=scale,
    )


def _require_identifier(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed identifier")


__all__ = [
    "ConversionQuoteConvention",
    "ConversionRateEvidence",
    "ConversionTimeBasis",
    "PositionValuation",
    "PositionValueInput",
    "ValuationCompleteness",
    "ValuationPolicyRef",
    "ValuationRoundingMode",
    "ValuationSnapshot",
    "ValuedAmount",
    "build_valuation_snapshot",
    "value_amount",
]
