"""Fail CI when tracked text contains high-confidence credential patterns."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from re import Pattern


@dataclass(frozen=True, slots=True)
class SecretPattern:
    name: str
    expression: Pattern[str]


PATTERNS = (
    SecretPattern(
        "private key",
        re.compile(
            "-----BEGIN " + r"(?:RSA |EC |OPENSSH )?" + "PRIVATE KEY-----"
        ),
    ),
    SecretPattern(
        "GitHub token",
        re.compile(r"\bgh" + r"(?:p|o|u|s|r)_[A-Za-z0-9]{36,}\b"),
    ),
    SecretPattern(
        "GitHub fine-grained token",
        re.compile(r"\bgithub_" + r"pat_[A-Za-z0-9_]{40,}\b"),
    ),
    SecretPattern(
        "AWS access key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    SecretPattern(
        "OpenAI-style token",
        re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{32,}\b"),
    ),
    SecretPattern(
        "Slack token",
        re.compile(r"\bxox" + r"[abprs]-[A-Za-z0-9-]{20,}\b"),
    ),
)


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line: int
    pattern_name: str


def scan_text(path: Path, text: str) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in PATTERNS:
            if pattern.expression.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line=line_number,
                        pattern_name=pattern.name,
                    )
                )
    return tuple(findings)


def repository_files(repository: Path) -> tuple[Path, ...]:
    completed = subprocess.run(
        ("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"),
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return tuple(
        repository / path.decode("utf-8")
        for path in completed.stdout.split(b"\0")
        if path
    )


def scan_repository(repository: Path) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for path in repository_files(repository):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(path.relative_to(repository), text))
    return tuple(findings)


def main() -> int:
    repository = Path.cwd()
    findings = scan_repository(repository)
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}: "
            f"possible {finding.pattern_name}"
        )
    if findings:
        print(f"secret scan failed with {len(findings)} finding(s)")
        return 1
    print("secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
