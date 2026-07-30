# AI Collaboration Index

此索引登记 AI 交换文档及其最终去向。状态必须与主题目录中的 resolution 一致。

## Active Topics

| ID | Topic | Origin | Status | Code baseline | Input | Current response |
|---|---|---|---|---|---|---|
| AI-20260727-002 | Funding Arbitrage Engine Design | Web GPT / Codex | ADR-009-012 PROMOTED; ADR-014 DESIGN_AND_OFFLINE_IMPLEMENTATION_ACCEPTED; EXECUTION_PROMOTION_PLANNED; EXTERNAL_BLOCKED | `40d10125318ebafc6c9979dc6ee3447c10739657` | [ADR-012 formal closure](topics/funding_arbitrage/96_web_gpt_adr012_formal_closure.md) | [ADR-014 final acceptance](topics/carry_application/70_web_gpt_adr014_final_acceptance.md) |
| AI-20260729-012 | Financial Ledger and PnL Attribution | Web GPT / Codex / Project Owner | ADR-013 APPROVED_IN_PRINCIPLE; OFFLINE_T036_T039_A016_COMPLETE; FINAL_REVIEW_PENDING; EXTERNAL_BLOCKED | `1969fdd9c184c679da3c63a2d40ca3b642d70021` | [Project-owner continuation](topics/financial_ledger/41_project_owner_offline_continuation.md) | [Offline implementation handoff](topics/financial_ledger/50_codex_adr013_offline_implementation_handoff.md) |
| AI-20260729-006 | Carry Application Architecture | Web GPT / Codex | ADR-014 DESIGN_AND_OFFLINE_IMPLEMENTATION_ACCEPTED; T040_T044_A017_CLOSED; EXTERNAL_BLOCKED | `40d10125318ebafc6c9979dc6ee3447c10739657` | [Offline implementation handoff](topics/carry_application/60_codex_adr014_offline_implementation_handoff.md) | [Final Web GPT acceptance](topics/carry_application/70_web_gpt_adr014_final_acceptance.md) |

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
