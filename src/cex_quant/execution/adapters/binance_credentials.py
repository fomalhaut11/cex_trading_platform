"""Explicit environment-backed Binance credential delivery adapter."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from cex_quant.core import AccountId

from .binance_authenticated import BinanceCredentials

_ENVIRONMENT_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")


class BinanceCredentialError(RuntimeError):
    """Sanitized credential lookup failure."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceCredentialBinding:
    """Environment variable names for one explicitly selected account."""

    api_key_variable: str
    secret_variable: str

    def __post_init__(self) -> None:
        if not _ENVIRONMENT_NAME.fullmatch(self.api_key_variable):
            raise ValueError("api_key_variable is invalid")
        if not _ENVIRONMENT_NAME.fullmatch(self.secret_variable):
            raise ValueError("secret_variable is invalid")
        if self.api_key_variable == self.secret_variable:
            raise ValueError("credential variables must be distinct")


@dataclass(slots=True, kw_only=True)
class EnvironmentBinanceCredentialProvider:
    """Read fresh values per lookup so external rotation takes effect."""

    bindings: Mapping[AccountId, BinanceCredentialBinding]
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, Mapping):
            raise ValueError("bindings must be a mapping")
        copied: dict[AccountId, BinanceCredentialBinding] = {}
        used_names: set[str] = set()
        for account_id, binding in self.bindings.items():
            if (
                not isinstance(account_id, str)
                or not account_id
                or not isinstance(binding, BinanceCredentialBinding)
            ):
                raise ValueError("credential binding is invalid")
            names = {
                binding.api_key_variable,
                binding.secret_variable,
            }
            if used_names.intersection(names):
                raise ValueError(
                    "credential variables cannot be shared across accounts"
                )
            used_names.update(names)
            copied[account_id] = binding
        if not copied:
            raise ValueError("at least one credential binding is required")
        if not isinstance(self.environ, Mapping):
            raise ValueError("environ must be a mapping")
        self.bindings = MappingProxyType(copied)

    def __repr__(self) -> str:
        return (
            "EnvironmentBinanceCredentialProvider("
            "bindings=<redacted>, environ=<redacted>)"
        )

    def credentials_for(
        self,
        account_id: AccountId,
    ) -> BinanceCredentials:
        binding = self.bindings.get(account_id)
        if binding is None:
            raise BinanceCredentialError(
                "Binance credentials are not configured for account"
            )
        try:
            api_key = self.environ[binding.api_key_variable]
            secret = self.environ[binding.secret_variable]
        except Exception:
            raise BinanceCredentialError(
                "Binance credential environment is unavailable"
            ) from None
        if not (_valid_secret_value(api_key) and _valid_secret_value(secret)):
            raise BinanceCredentialError(
                "Binance credential environment is invalid"
            )
        return BinanceCredentials(api_key=api_key, secret=secret)


def _valid_secret_value(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and not any(
            ord(character) < 32 or ord(character) == 127
            for character in value
        )
    )


__all__ = [
    "BinanceCredentialBinding",
    "BinanceCredentialError",
    "EnvironmentBinanceCredentialProvider",
]
