# AI Collaboration Index

此索引登记 AI 交换文档及其最终去向。状态必须与主题目录中的 resolution 一致。

## Active Topics

| ID | Topic | Origin | Status | Code baseline | Input | Current response |
|---|---|---|---|---|---|---|
| AI-20260727-002 | Funding Arbitrage Engine Design | Web GPT / Codex | ADR-009/010/011 PROMOTED; ADR-012 READY_FOR_REVIEW | `a752d3bff06a1b73b1103f543c64a2b6b64d2016` | [ADR-012 current-code audit](topics/funding_arbitrage/82_codex_adr012_current_code_audit.md) | [ADR-012 proposal handoff](topics/funding_arbitrage/83_codex_adr012_proposal_handoff.md) |

## Completed and Reference Exchanges

| ID | Topic | Origin | Status | Code baseline | Artifact | Promoted to |
|---|---|---|---|---|---|---|
| AI-20260727-001 | Current implementation external review | Codex | PROMOTED | `674949992a69e84468f10fb7dfd699ca03e44a2d` | [External review package](../development/external_review_package_2026-07-27.md) | External review baseline; report commit `6a38a855259bc51df6abc56c5b9722f9a6c4bb4e` |

## Registering a New Topic

1. Choose the next unused document ID for the date.
2. Create `topics/YYYY-MM-DD_short-topic/`.
3. Copy only the required templates from `templates/`.
4. Add one row under Active Topics.
5. After resolution, update the status and record exact promoted paths and commit.

## Index Rules

- Do not mark an item `PROMOTED` without a target document/code path and commit.
- Do not delete rejected or superseded records; their history prevents repeated debate.
- Do not put local absolute paths in this index.
- A link to `main` is convenient but not audit evidence; record a full commit SHA.
