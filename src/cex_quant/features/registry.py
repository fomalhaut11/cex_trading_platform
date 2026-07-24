"""Feature definition registration and deterministic dependency ordering."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .model import FeatureOutput, FeatureRef, FeatureValue


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureContext:
    """Read-only inputs supplied to one feature calculation."""

    event: object
    dependencies: Mapping[FeatureRef, FeatureValue]
    previous: FeatureValue | None


class FeatureCalculator(Protocol):
    def __call__(self, context: FeatureContext) -> FeatureOutput | None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class FeatureDefinition:
    """A versioned calculation activated by selected canonical event types."""

    ref: FeatureRef
    event_types: tuple[type[object], ...]
    calculator: FeatureCalculator
    dependencies: tuple[FeatureRef, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.event_types:
            raise ValueError("event_types cannot be empty")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("feature dependencies cannot contain duplicates")
        if self.ref in self.dependencies:
            raise ValueError("feature cannot depend on itself")


class FeatureRegistrationError(ValueError):
    """Raised when the registered feature graph is invalid."""


class FeatureRegistry:
    """Immutable-after-build registry with a stable topological order."""

    def __init__(self) -> None:
        self._definitions: dict[FeatureRef, FeatureDefinition] = {}

    def register(self, definition: FeatureDefinition) -> None:
        if definition.ref in self._definitions:
            raise FeatureRegistrationError(
                f"duplicate feature definition: {definition.ref}"
            )
        self._definitions[definition.ref] = definition

    def build(self) -> tuple[FeatureDefinition, ...]:
        missing = {
            dependency
            for definition in self._definitions.values()
            for dependency in definition.dependencies
            if dependency not in self._definitions
        }
        if missing:
            labels = ", ".join(str(ref) for ref in sorted(missing))
            raise FeatureRegistrationError(f"missing feature dependencies: {labels}")

        ordered: list[FeatureDefinition] = []
        visiting: set[FeatureRef] = set()
        visited: set[FeatureRef] = set()

        def visit(ref: FeatureRef) -> None:
            if ref in visiting:
                raise FeatureRegistrationError(f"feature dependency cycle at {ref}")
            if ref in visited:
                return
            visiting.add(ref)
            definition = self._definitions[ref]
            for dependency in sorted(definition.dependencies):
                visit(dependency)
            visiting.remove(ref)
            visited.add(ref)
            ordered.append(definition)

        for ref in sorted(self._definitions):
            visit(ref)
        return tuple(ordered)


__all__ = [
    "FeatureCalculator",
    "FeatureContext",
    "FeatureDefinition",
    "FeatureRegistrationError",
    "FeatureRegistry",
]
