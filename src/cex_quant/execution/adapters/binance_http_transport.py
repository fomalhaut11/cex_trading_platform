"""Bounded asyncio HTTPS transport for authenticated Binance requests."""

from __future__ import annotations

import asyncio
import math
import re
import ssl
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

from .binance import BinanceProduct
from .binance_authenticated import (
    BinanceHttpRequest,
    BinanceHttpResponse,
    BinanceHttpTransportFailure,
)

RestBaseUrlResolver = Callable[[BinanceProduct], str]


class TlsConnectionOpener(Protocol):
    """Injectable asyncio TLS connection boundary used by offline tests."""

    def __call__(
        self,
        host: str,
        port: int,
        ssl_context: ssl.SSLContext,
        server_hostname: str,
    ) -> Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]: ...


async def _open_tls_connection(
    host: str,
    port: int,
    ssl_context: ssl.SSLContext,
    server_hostname: str,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    return await asyncio.open_connection(
        host,
        port,
        ssl=ssl_context,
        server_hostname=server_hostname,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class BinanceHttpTimeouts:
    connect_seconds: float = 5.0
    read_seconds: float = 10.0
    total_seconds: float = 15.0

    def __post_init__(self) -> None:
        for name, value in (
            ("connect_seconds", self.connect_seconds),
            ("read_seconds", self.read_seconds),
            ("total_seconds", self.total_seconds),
        ):
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be positive")
        if self.total_seconds < self.connect_seconds:
            raise ValueError("total_seconds must be at least connect_seconds")


@dataclass(slots=True, kw_only=True)
class AsyncioBinanceHttpTransport:
    """Send one HTTP/1.1 request over a fresh bounded TLS connection."""

    rest_base_url: RestBaseUrlResolver = field(repr=False)
    timeouts: BinanceHttpTimeouts = field(
        default_factory=BinanceHttpTimeouts
    )
    max_response_body_bytes: int = 1_048_576
    max_response_header_bytes: int = 65_536
    connection_opener: TlsConnectionOpener = field(
        default=_open_tls_connection,
        repr=False,
    )
    ssl_context: ssl.SSLContext = field(
        default_factory=ssl.create_default_context,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not callable(self.rest_base_url):
            raise ValueError("rest_base_url must be callable")
        if not isinstance(self.timeouts, BinanceHttpTimeouts):
            raise ValueError("timeouts must be BinanceHttpTimeouts")
        for name, value in (
            ("max_response_body_bytes", self.max_response_body_bytes),
            ("max_response_header_bytes", self.max_response_header_bytes),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive int")
        if not callable(self.connection_opener):
            raise ValueError("connection_opener must be callable")
        if not isinstance(self.ssl_context, ssl.SSLContext):
            raise ValueError("ssl_context must be an SSLContext")

    async def send(
        self,
        product: BinanceProduct,
        request: BinanceHttpRequest,
    ) -> BinanceHttpResponse:
        if not isinstance(product, BinanceProduct):
            raise ValueError("product must be a BinanceProduct")
        if not isinstance(request, BinanceHttpRequest):
            raise ValueError("request must be a BinanceHttpRequest")
        try:
            resolved_base_url = self.rest_base_url(product)
        except Exception:
            raise BinanceHttpTransportFailure(
                "Binance REST endpoint resolution failed",
                request_sent=False,
            ) from None
        endpoint = _parse_base_url(resolved_base_url)
        request_bytes = _encode_request(endpoint, request)
        writer: asyncio.StreamWriter | None = None
        request_sent = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeouts.total_seconds
        try:
            async with asyncio.timeout(self.timeouts.total_seconds):
                try:
                    async with asyncio.timeout(self.timeouts.connect_seconds):
                        reader, writer = await self.connection_opener(
                            endpoint.host,
                            endpoint.port,
                            self.ssl_context,
                            endpoint.host,
                        )
                except TimeoutError:
                    raise BinanceHttpTransportFailure(
                        "Binance HTTP connection timed out",
                        request_sent=False,
                    ) from None
                except Exception:
                    raise BinanceHttpTransportFailure(
                        "Binance HTTP connection failed",
                        request_sent=False,
                    ) from None

                request_sent = True
                try:
                    writer.write(request_bytes)
                    await writer.drain()
                    async with asyncio.timeout(self.timeouts.read_seconds):
                        return await _read_response(
                            reader,
                            max_header_bytes=self.max_response_header_bytes,
                            max_body_bytes=self.max_response_body_bytes,
                        )
                except BinanceHttpTransportFailure:
                    raise
                except TimeoutError:
                    raise BinanceHttpTransportFailure(
                        "Binance HTTP response timed out",
                        request_sent=True,
                    ) from None
                except Exception:
                    raise BinanceHttpTransportFailure(
                        "Binance HTTP request failed after send",
                        request_sent=True,
                    ) from None
        except BinanceHttpTransportFailure:
            raise
        except TimeoutError:
            raise BinanceHttpTransportFailure(
                "Binance HTTP total timeout exceeded",
                request_sent=request_sent,
            ) from None
        finally:
            if writer is not None:
                try:
                    writer.close()
                    remaining = deadline - loop.time()
                    if remaining > 0:
                        async with asyncio.timeout(remaining):
                            await writer.wait_closed()
                except Exception:
                    pass


@dataclass(frozen=True, slots=True)
class _Endpoint:
    host: str
    port: int


def _parse_base_url(value: str) -> _Endpoint:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("REST base URL must be a non-empty trimmed string")
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        raise ValueError("REST base URL must use https")
    if parsed.hostname is None:
        raise ValueError("REST base URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("REST base URL must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("REST base URL must contain only an HTTPS origin")
    try:
        port = parsed.port or 443
    except ValueError:
        raise ValueError("REST base URL has an invalid port") from None
    return _Endpoint(host=parsed.hostname.lower(), port=port)


_METHODS = frozenset({"GET", "POST", "PUT", "DELETE"})
_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_BLOCKED_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


def _encode_request(
    endpoint: _Endpoint,
    request: BinanceHttpRequest,
) -> bytes:
    if request.method not in _METHODS:
        raise ValueError("HTTP method is not allowed")
    if (
        not request.path.startswith("/")
        or request.path.startswith("//")
        or "?" in request.path
        or "#" in request.path
        or "\\" in request.path
        or _contains_unsafe_target_character(request.path)
    ):
        raise ValueError("HTTP path is unsafe")
    if (
        request.query.startswith("?")
        or "#" in request.query
        or _contains_unsafe_target_character(request.query)
    ):
        raise ValueError("HTTP query is unsafe")
    headers = _validated_headers(request.headers)
    target = request.path
    if request.query:
        target = f"{target}?{request.query}"
    host_header = endpoint.host if endpoint.port == 443 else (
        f"{endpoint.host}:{endpoint.port}"
    )
    lines = [
        f"{request.method} {target} HTTP/1.1",
        f"Host: {host_header}",
        "Connection: close",
        "Content-Length: 0",
        *(f"{name}: {value}" for name, value in headers),
        "",
        "",
    ]
    try:
        return "\r\n".join(lines).encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("HTTP request fields must be ASCII") from None


def _validated_headers(
    headers: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    validated: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, value in headers.items():
        if not isinstance(name, str) or not _HEADER_NAME.fullmatch(name):
            raise ValueError("HTTP header name is unsafe")
        if not isinstance(value, str) or _contains_control(value):
            raise ValueError("HTTP header value is unsafe")
        lowered = name.lower()
        if lowered in seen or lowered in _BLOCKED_HEADERS:
            raise ValueError("HTTP header is duplicated or transport-owned")
        seen.add(lowered)
        validated.append((name, value))
    return tuple(validated)


async def _read_response(
    reader: asyncio.StreamReader,
    *,
    max_header_bytes: int,
    max_body_bytes: int,
) -> BinanceHttpResponse:
    try:
        header_block = await reader.readuntil(b"\r\n\r\n")
    except asyncio.LimitOverrunError:
        raise BinanceHttpTransportFailure(
            "Binance HTTP response headers exceed configured limit",
            request_sent=True,
        ) from None
    if len(header_block) > max_header_bytes:
        raise BinanceHttpTransportFailure(
            "Binance HTTP response headers exceed configured limit",
            request_sent=True,
        )
    status_code, headers = _parse_response_headers(header_block)
    transfer_encoding = headers.get("transfer-encoding")
    content_length = headers.get("content-length")
    if transfer_encoding is not None:
        if transfer_encoding.lower() != "chunked" or content_length is not None:
            raise BinanceHttpTransportFailure(
                "Binance HTTP response framing is unsupported",
                request_sent=True,
            )
        body = await _read_chunked_body(reader, max_body_bytes=max_body_bytes)
    elif content_length is not None:
        length = _parse_content_length(content_length)
        if length > max_body_bytes:
            raise BinanceHttpTransportFailure(
                "Binance HTTP response body exceeds configured limit",
                request_sent=True,
            )
        body = await reader.readexactly(length)
    else:
        body = await reader.read(max_body_bytes + 1)
        if len(body) > max_body_bytes:
            raise BinanceHttpTransportFailure(
                "Binance HTTP response body exceeds configured limit",
                request_sent=True,
            )
    return BinanceHttpResponse(status_code=status_code, body=body)


def _parse_response_headers(
    header_block: bytes,
) -> tuple[int, dict[str, str]]:
    try:
        lines = header_block[:-4].decode("iso-8859-1").split("\r\n")
        version, status, _ = lines[0].split(" ", 2)
        status_code = int(status)
    except (UnicodeDecodeError, ValueError, IndexError):
        raise BinanceHttpTransportFailure(
            "Binance HTTP response status is malformed",
            request_sent=True,
        ) from None
    if version not in {"HTTP/1.0", "HTTP/1.1"} or not 100 <= status_code <= 599:
        raise BinanceHttpTransportFailure(
            "Binance HTTP response status is malformed",
            request_sent=True,
        )
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        lowered = name.strip().lower()
        if (
            not separator
            or not _HEADER_NAME.fullmatch(name)
            or lowered in headers
            or _contains_control(value.lstrip(" \t"), allow_tab=True)
        ):
            raise BinanceHttpTransportFailure(
                "Binance HTTP response headers are malformed",
                request_sent=True,
            )
        headers[lowered] = value.strip()
    return status_code, headers


def _parse_content_length(value: str) -> int:
    if not value.isascii() or not value.isdigit():
        raise BinanceHttpTransportFailure(
            "Binance HTTP content length is malformed",
            request_sent=True,
        )
    return int(value)


async def _read_chunked_body(
    reader: asyncio.StreamReader,
    *,
    max_body_bytes: int,
) -> bytes:
    body = bytearray()
    while True:
        size_line = await reader.readuntil(b"\r\n")
        if len(size_line) > 128:
            raise BinanceHttpTransportFailure(
                "Binance HTTP chunk framing is malformed",
                request_sent=True,
            )
        raw_size = size_line[:-2].split(b";", 1)[0]
        try:
            size = int(raw_size, 16)
        except ValueError:
            raise BinanceHttpTransportFailure(
                "Binance HTTP chunk framing is malformed",
                request_sent=True,
            ) from None
        if size < 0 or len(body) + size > max_body_bytes:
            raise BinanceHttpTransportFailure(
                "Binance HTTP response body exceeds configured limit",
                request_sent=True,
            )
        if size == 0:
            trailer = await reader.readuntil(b"\r\n")
            if trailer != b"\r\n":
                raise BinanceHttpTransportFailure(
                    "Binance HTTP response trailers are unsupported",
                    request_sent=True,
                )
            return bytes(body)
        body.extend(await reader.readexactly(size))
        if await reader.readexactly(2) != b"\r\n":
            raise BinanceHttpTransportFailure(
                "Binance HTTP chunk framing is malformed",
                request_sent=True,
            )


def _contains_control(value: str, *, allow_tab: bool = False) -> bool:
    return any(
        (
            ord(character) < 32
            and not (allow_tab and character == "\t")
        )
        or ord(character) == 127
        for character in value
    )


def _contains_unsafe_target_character(value: str) -> bool:
    return any(not 33 <= ord(character) <= 126 for character in value)


__all__ = [
    "AsyncioBinanceHttpTransport",
    "BinanceHttpTimeouts",
    "RestBaseUrlResolver",
    "TlsConnectionOpener",
]
