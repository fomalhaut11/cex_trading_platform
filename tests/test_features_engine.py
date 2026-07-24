import unittest
from dataclasses import dataclass

from cex_quant.core import (
    EventId,
    EventMetadata,
    EventSource,
    EventTimeSource,
    FeatureId,
    SchemaVersion,
    TimePrecision,
    UnixNanos,
    VenueId,
)
from cex_quant.features import (
    FeatureDefinition,
    FeatureOrigin,
    FeatureOutput,
    FeatureQuality,
    FeatureRef,
    FeatureRegistrationError,
    FeatureRegistry,
    FeatureUpdateDisposition,
    FeatureVersion,
    InvalidFeatureEventError,
    OnlineFeatureEngine,
)
from cex_quant.instruments import InstrumentId, InstrumentKind
from cex_quant.market_data import VenueOptionAnalyticsUpdate


@dataclass(frozen=True, slots=True, kw_only=True)
class TestEvent:
    metadata: EventMetadata
    price: float


def metadata(event_id: str, time_ns: int) -> EventMetadata:
    return EventMetadata(
        event_id=EventId(event_id),
        event_time_ns=UnixNanos(time_ns),
        receive_time_ns=UnixNanos(time_ns + 7),
        source=EventSource(venue=VenueId("test"), channel="test"),
        schema_version=SchemaVersion(1),
        source_time_precision=TimePrecision.NANOSECOND,
        event_time_source=EventTimeSource.VENUE,
    )


class FeatureRegistryTests(unittest.TestCase):
    def test_build_is_topological_and_stable(self) -> None:
        first = FeatureRef(
            feature_id=FeatureId("mid"), version=FeatureVersion(1)
        )
        second = FeatureRef(
            feature_id=FeatureId("return"), version=FeatureVersion(2)
        )
        registry = FeatureRegistry()
        registry.register(
            FeatureDefinition(
                ref=second,
                event_types=(TestEvent,),
                dependencies=(first,),
                calculator=lambda context: None,
            )
        )
        registry.register(
            FeatureDefinition(
                ref=first,
                event_types=(TestEvent,),
                calculator=lambda context: None,
            )
        )

        self.assertEqual(
            tuple(definition.ref for definition in registry.build()),
            (first, second),
        )

    def test_missing_dependency_and_cycle_are_rejected(self) -> None:
        first = FeatureRef(feature_id=FeatureId("a"), version=FeatureVersion(1))
        second = FeatureRef(feature_id=FeatureId("b"), version=FeatureVersion(1))
        missing_registry = FeatureRegistry()
        missing_registry.register(
            FeatureDefinition(
                ref=first,
                event_types=(TestEvent,),
                dependencies=(second,),
                calculator=lambda context: None,
            )
        )
        with self.assertRaises(FeatureRegistrationError):
            missing_registry.build()

        cyclic_registry = FeatureRegistry()
        for ref, dependency in ((first, second), (second, first)):
            cyclic_registry.register(
                FeatureDefinition(
                    ref=ref,
                    event_types=(TestEvent,),
                    dependencies=(dependency,),
                    calculator=lambda context: None,
                )
            )
        with self.assertRaises(FeatureRegistrationError):
            cyclic_registry.build()


class OnlineFeatureEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.price_ref = FeatureRef(
            feature_id=FeatureId("reference_price"),
            version=FeatureVersion(1),
        )
        self.double_ref = FeatureRef(
            feature_id=FeatureId("double_price"),
            version=FeatureVersion(1),
        )
        registry = FeatureRegistry()
        registry.register(
            FeatureDefinition(
                ref=self.double_ref,
                event_types=(TestEvent,),
                dependencies=(self.price_ref,),
                calculator=lambda context: FeatureOutput(
                    value=context.dependencies[self.price_ref].value * 2.0,
                    unit="USD",
                ),
            )
        )
        registry.register(
            FeatureDefinition(
                ref=self.price_ref,
                event_types=(TestEvent,),
                calculator=lambda context: FeatureOutput(
                    value=context.event.price,  # type: ignore[attr-defined]
                    unit="USD",
                ),
            )
        )
        self.engine = OnlineFeatureEngine(
            scope="BTC-USD", definitions=registry.build()
        )

    def test_updates_dependencies_in_same_event_and_attaches_lineage(self) -> None:
        report = self.engine.on_event(
            TestEvent(metadata=metadata("event-1", 100), price=42.5)
        )

        self.assertEqual(report.updated, (self.price_ref, self.double_ref))
        snapshot = self.engine.snapshot()
        double = snapshot.get(self.double_ref)
        assert double is not None
        self.assertEqual(double.value, 85.0)
        self.assertEqual(double.unit, "USD")
        self.assertEqual(double.quality, FeatureQuality.GOOD)
        self.assertEqual(double.metadata.origin, FeatureOrigin.SYSTEM_COMPUTED)
        self.assertEqual(double.metadata.triggering_event_id, EventId("event-1"))
        self.assertEqual(double.metadata.as_of_ns, UnixNanos(100))
        self.assertEqual(double.metadata.computed_at_ns, UnixNanos(107))
        self.assertEqual(double.metadata.dependency_refs, (self.price_ref,))

    def test_snapshots_are_deterministic_and_immutable(self) -> None:
        event = TestEvent(metadata=metadata("event-2", 200), price=10.0)
        self.engine.on_event(event)
        first = self.engine.snapshot()
        second = self.engine.snapshot()

        self.assertEqual(first, second)
        self.assertEqual(
            tuple(value.metadata.ref for value in first.values),
            tuple(sorted((self.price_ref, self.double_ref))),
        )
        with self.assertRaises(AttributeError):
            first.values[0].value = 1.0  # type: ignore[misc]

    def test_no_output_preserves_previous_value(self) -> None:
        ref = FeatureRef(
            feature_id=FeatureId("positive_only"), version=FeatureVersion(1)
        )
        definition = FeatureDefinition(
            ref=ref,
            event_types=(TestEvent,),
            calculator=lambda context: (
                FeatureOutput(value=context.event.price, unit="USD")  # type: ignore[attr-defined]
                if context.event.price > 0  # type: ignore[attr-defined]
                else None
            ),
        )
        engine = OnlineFeatureEngine(scope="BTC-USD", definitions=(definition,))
        engine.on_event(TestEvent(metadata=metadata("one", 1), price=5.0))
        report = engine.on_event(
            TestEvent(metadata=metadata("two", 2), price=-1.0)
        )

        self.assertEqual(
            report.updates[0].disposition, FeatureUpdateDisposition.NO_OUTPUT
        )
        value = engine.snapshot().get(ref)
        assert value is not None
        self.assertEqual(value.value, 5.0)

    def test_rejects_noncanonical_input(self) -> None:
        with self.assertRaises(InvalidFeatureEventError):
            self.engine.on_event(object())

    def test_venue_analytics_reference_lineage_is_explicit(self) -> None:
        ref = FeatureRef(
            feature_id=FeatureId("adjusted_iv"), version=FeatureVersion(1)
        )
        definition = FeatureDefinition(
            ref=ref,
            event_types=(VenueOptionAnalyticsUpdate,),
            calculator=lambda context: FeatureOutput(
                value=context.event.implied_volatility + 0.01,  # type: ignore[union-attr]
                unit="decimal_volatility",
            ),
        )
        engine = OnlineFeatureEngine(scope="BTC-option", definitions=(definition,))
        engine.on_event(
            VenueOptionAnalyticsUpdate(
                metadata=metadata("venue-reference", 300),
                instrument_id=InstrumentId(
                    venue=VenueId("test"),
                    kind=InstrumentKind.OPTION,
                    symbol="BTC-option",
                ),
                implied_volatility=0.6,
            )
        )

        value = engine.snapshot().get(ref)
        assert value is not None
        self.assertEqual(
            value.metadata.origin,
            FeatureOrigin.SYSTEM_COMPUTED_WITH_VENUE_REFERENCE,
        )
        self.assertEqual(
            value.metadata.venue_reference_event_ids,
            (EventId("venue-reference"),),
        )


class FeatureValueValidationTests(unittest.TestCase):
    def test_nonfinite_good_value_is_rejected_but_invalid_is_explicit(self) -> None:
        with self.assertRaises(ValueError):
            FeatureOutput(value=float("nan"), unit="ratio")
        invalid = FeatureOutput(
            value=float("nan"), unit="ratio", quality=FeatureQuality.INVALID
        )
        self.assertEqual(invalid.quality, FeatureQuality.INVALID)


if __name__ == "__main__":
    unittest.main()
