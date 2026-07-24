"""Single-writer deterministic online feature engine."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from cex_quant.core import EventMetadata
from cex_quant.market_data import VenueOptionAnalyticsUpdate

from .model import (
    FeatureMetadata,
    FeatureOrigin,
    FeatureRef,
    FeatureSnapshot,
    FeatureValue,
)
from .registry import FeatureContext, FeatureDefinition


class FeatureUpdateDisposition(StrEnum):
    UPDATED = "updated"
    NOT_TRIGGERED = "not_triggered"
    MISSING_DEPENDENCY = "missing_dependency"
    NO_OUTPUT = "no_output"


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureUpdate:
    ref: FeatureRef
    disposition: FeatureUpdateDisposition


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureUpdateReport:
    updates: tuple[FeatureUpdate, ...]

    @property
    def updated(self) -> tuple[FeatureRef, ...]:
        return tuple(
            item.ref
            for item in self.updates
            if item.disposition is FeatureUpdateDisposition.UPDATED
        )


class InvalidFeatureEventError(TypeError):
    """Raised when an event lacks canonical metadata."""


class OnlineFeatureEngine:
    """Updates registered features synchronously in dependency order.

    One instance owns one explicit scope (normally an instrument). The caller
    serializes events for that scope; calculations perform no I/O.
    """

    def __init__(
        self, *, scope: str, definitions: tuple[FeatureDefinition, ...]
    ) -> None:
        if not scope:
            raise ValueError("feature engine scope cannot be empty")
        refs = tuple(definition.ref for definition in definitions)
        if len(set(refs)) != len(refs):
            raise ValueError("feature definitions must be unique")
        self._scope = scope
        self._definitions = definitions
        self._values: dict[FeatureRef, FeatureValue] = {}

    def on_event(self, event: object) -> FeatureUpdateReport:
        metadata = getattr(event, "metadata", None)
        if not isinstance(metadata, EventMetadata):
            raise InvalidFeatureEventError(
                "feature input must expose canonical EventMetadata"
            )

        updates: list[FeatureUpdate] = []
        for definition in self._definitions:
            if not isinstance(event, definition.event_types):
                disposition = FeatureUpdateDisposition.NOT_TRIGGERED
            elif not all(ref in self._values for ref in definition.dependencies):
                disposition = FeatureUpdateDisposition.MISSING_DEPENDENCY
            else:
                dependencies = MappingProxyType(
                    {ref: self._values[ref] for ref in definition.dependencies}
                )
                output = definition.calculator(
                    FeatureContext(
                        event=event,
                        dependencies=dependencies,
                        previous=self._values.get(definition.ref),
                    )
                )
                if output is None:
                    disposition = FeatureUpdateDisposition.NO_OUTPUT
                else:
                    dependency_refs = tuple(sorted(definition.dependencies))
                    venue_reference_event_ids = {
                        event_id
                        for value in dependencies.values()
                        for event_id in value.metadata.venue_reference_event_ids
                    }
                    if isinstance(event, VenueOptionAnalyticsUpdate):
                        venue_reference_event_ids.add(metadata.event_id)
                    sorted_reference_ids = tuple(
                        sorted(venue_reference_event_ids)
                    )
                    self._values[definition.ref] = FeatureValue(
                        value=output.value,
                        unit=output.unit,
                        quality=output.quality,
                        metadata=FeatureMetadata(
                            ref=definition.ref,
                            scope=self._scope,
                            as_of_ns=metadata.event_time_ns,
                            computed_at_ns=metadata.receive_time_ns,
                            triggering_event_id=metadata.event_id,
                            dependency_refs=dependency_refs,
                            origin=(
                                FeatureOrigin.SYSTEM_COMPUTED_WITH_VENUE_REFERENCE
                                if sorted_reference_ids
                                else FeatureOrigin.SYSTEM_COMPUTED
                            ),
                            venue_reference_event_ids=sorted_reference_ids,
                            valid_until_ns=output.valid_until_ns,
                        ),
                    )
                    disposition = FeatureUpdateDisposition.UPDATED
            updates.append(
                FeatureUpdate(ref=definition.ref, disposition=disposition)
            )
        return FeatureUpdateReport(updates=tuple(updates))

    def snapshot(self) -> FeatureSnapshot:
        values = tuple(
            self._values[ref]
            for ref in sorted(self._values)
        )
        return FeatureSnapshot(scope=self._scope, values=values)


__all__ = [
    "FeatureUpdate",
    "FeatureUpdateDisposition",
    "FeatureUpdateReport",
    "InvalidFeatureEventError",
    "OnlineFeatureEngine",
]
