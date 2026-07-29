"""Generic economic-owner references used by Accounting allocation."""

from __future__ import annotations

import re
from dataclasses import dataclass

_OWNER_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,126}[a-z0-9]$")
MAX_OWNER_ID_LENGTH = 512


@dataclass(frozen=True, slots=True, kw_only=True)
class EconomicOwnerTypeRef:
    name: str
    version: int

    def __post_init__(self) -> None:
        if not _OWNER_TYPE_PATTERN.fullmatch(self.name):
            raise ValueError("owner type name is invalid")
        if self.version <= 0:
            raise ValueError("owner type version must be positive")

    @property
    def canonical(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True, slots=True, kw_only=True)
class EconomicOwnerRef:
    owner_type: EconomicOwnerTypeRef
    owner_id: str

    def __post_init__(self) -> None:
        if not self.owner_id or self.owner_id != self.owner_id.strip():
            raise ValueError("owner_id must be non-empty and trimmed")
        if len(self.owner_id) > MAX_OWNER_ID_LENGTH:
            raise ValueError(
                f"owner_id exceeds maximum length {MAX_OWNER_ID_LENGTH}"
            )

    @property
    def canonical(self) -> str:
        return f"{self.owner_type.canonical}:{self.owner_id}"


__all__ = [
    "MAX_OWNER_ID_LENGTH",
    "EconomicOwnerRef",
    "EconomicOwnerTypeRef",
]
