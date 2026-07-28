---
id: AI-20260727-005
title: Funding Arbitrage Architecture Resolution
origin: joint
status: ACCEPTED
created: 2026-07-27
code_baseline: 97d10e33f8d69c2535a542bee9f095aec1c312b9
review_source_commit: e4eab0e928e3bb8da0fdc608931876eddb0fcb78
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_response.md
  - 30_web_gpt_review.md
  - 31_web_gpt_adr009_review.md
  - 40_codex_adr009_review_response.md
  - ../../../development/multi_leg_portfolio_trading_plan.md
  - ../../../adr/ADR-009-portfolio-decision-snapshot.md
external_share: allowed
sensitivity: public-project
---

# Funding Arbitrage Architecture Resolution

## 1. Decision

接受 Codex 容量审查和 Web GPT 附条件审查的共同方向：

> Funding Arbitrage 是第一个 Carry Application 和交易基础设施压力测试，不是当前可以
> 直接编码的普通策略。

在六项 ADR 逐项通过并晋升为正式架构基线以前：

- 不创建 `funding_arbitrage.py`；
- 不创建会绕过 Risk/OMS 的 Carry Engine；
- 不进入 Testnet 多腿交易；
- 不宣称 Funding Arbitrage MVP 已经开始实现。

本决议状态为 `ACCEPTED`，不是 `PROMOTED`。只有六项 ADR 和相应正式文档落地后，相关
决定才分别转为 `PROMOTED`。

## 2. Accepted Architecture Direction

### 2.1 Deterministic correlated snapshot

采用跨市场、跨账户的逻辑一致快照，不因本应用引入通用 Event Bus。

“Atomic Snapshot”的正式含义是：

- 一个不可变的决策输入；
- 在单一组装点发布；
- 保留每个来源各自的 `as_of_ns`、quality 和 provenance；
- 定义最大 source skew；
- 缺失、过期、顺序不明或 skew 超限时 fail closed。

它不宣称 Spot、Perpetual、Funding 和 Account 数据在物理上同时到达。

### 2.2 Generic basket objective

采用 venue-neutral、bounded N-leg Basket/Portfolio Target Intent 表达一个组合交易目标。
Funding 的双腿只是第一个验证用例，不为两腿、三腿或四腿分别建立 OMS。Basket legs 在
进入首个 venue submit 前必须共同完成完整性、余额、margin、freshness 和 portfolio-risk
预检。

具体类型名称、leg 数量上限、是否直接通用化以及 v1 字段由 ADR-010 决定。

### 2.3 Durable parent-child OMS

采用通用、持久化 Parent Order Group 与 bounded Child Orders。必须覆盖：

- idempotency；
- child identity；
- partial fill；
- generic `PARTIALLY_EXECUTED`；
- unknown execution state；
- hedge timeout；
- compensation/recovery；
- restart replay；
- venue reconciliation；
- operator halt。

OMS Order Group 只拥有执行目标的通用生命周期。Carry application 根据 child fills 和
net Delta 将 `PARTIALLY_EXECUTED` 解释为 `PARTIALLY_HEDGED`。Carry Position 的
`ACTIVE/CLOSING/CLOSED` 状态由 application aggregate 拥有，实际 venue position 仍由
Portfolio/Account State 提供权威事实。

### 2.4 Portfolio risk

保留中央、不可绕过的 Risk 边界，并扩展为 basket/portfolio assessment。至少覆盖：

- net delta；
- basis stress；
- funding reversal；
- legging exposure and duration；
- gross/net notional；
- collateral and available balance；
- initial/maintenance margin；
- liquidation distance；
- fees/slippage reserve；
- stale account or market state；
- continuous post-trade carry supervision。

### 2.5 Financial ledger

采用明确 cash-flow ledger 与 PnL attribution。Funding cash flow、trading commission、
transfer/borrow/withdrawal 等成本使用不同类型，不把 funding payment 混称为 fee。

### 2.6 Application boundary

接受 `cex_quant.applications.carry` 方向。预期领域结构为：

```text
applications/
  carry/
    funding_arbitrage/
```

是否在首版建立更广泛的 `basis_arbitrage`、`calendar_spread` 等空目录由 ADR-014 决定；
不为尚未实现的应用提前创建占位代码。

## 3. Review Disposition

| Proposal or finding | Disposition | Resolution |
|---|---|---|
| Funding Arbitrage 不应直接编码 | Adopt | 先完成 ADR 与核心能力 |
| 当前不需要通用 Event Bus | Adopt | 使用确定性 correlated snapshot |
| Atomic Snapshot | Modify | 定义为带来源时间和 skew 的逻辑一致快照 |
| Generic bounded N-leg Basket Intent | Adopt with ADR | 首腿提交前进行整篮子预检 |
| Generic Parent/Child OMS | Adopt | 不按腿数拆模块；必须支持 partial/unknown/restart |
| `PARTIALLY_EXECUTED` | Adopt | OMS 通用执行状态 |
| `PARTIALLY_HEDGED` | Modify | Carry application 根据 OMS facts 和净 Delta 派生 |
| `ACTIVE/CLOSED` Parent Order | Modify | 归属 Carry Position，不由 OMS 长期持有 |
| Portfolio Risk | Adopt | pre-trade basket risk + continuous supervision |
| Funding/fee/PnL ledger | Adopt | funding 与 commission 分类型核算 |
| `cex_quant.applications.carry` | Adopt in principle | 精确依赖规则由 ADR-014 固化 |
| 直接进入 Testnet | Reject | 核心能力和离线验收完成前禁止 |

## 4. ADR Queue

以下编号在本决议中登记为计划项；ADR 文件创建并通过审查后才成为正式架构基线。

| Order | Planned ADR | Scope | Required exit evidence | Status |
|---:|---|---|---|---|
| 1 | ADR-009 Portfolio Snapshot Model | 多 scope 状态所有权、时间、quality、skew、组装和读取 | 契约、所有权图、stale/skew 失败场景 | ACCEPTED_2026_07_28 |
| 2 | ADR-010 Basket Intent Architecture | Generic bounded N-leg objective、identity、limits、版本与整篮子预检 | schema、边界、单腿 intent 兼容策略 | READY_TO_DRAFT |
| 3 | ADR-011 Parent-Child Order Model | Generic Order Group lifecycle、bounded children、partial、unknown、补偿和恢复 | 状态机、journal/replay 设计、两腿与三腿故障矩阵 | BLOCKED_BY_ADR_010 |
| 4 | ADR-012 Portfolio Risk Extension | basket projection、delta、basis、margin、liquidation、持续监督 | 风险上下文、拒绝原因、fail-closed 场景 | BLOCKED_BY_ADR_009_010 |
| 5 | ADR-013 Financial Ledger Model | funding、commission、cash flow、valuation 和 attribution | double-entry/ledger 选择、reconciliation、PnL 恒等式 | BLOCKED_BY_ADR_009 |
| 6 | ADR-014 Carry Application Boundary | applications/carry 所有权、依赖、聚合和 runtime assembly | 模块拓扑、公开 API、禁止依赖规则 | BLOCKED_BY_ADR_009_010_011_012_013 |

## 5. ADR Review Protocol

每项 ADR 按以下流程单独推进：

```text
Draft ADR
  -> Codex code and architecture verification
  -> Web GPT architecture review
  -> user decision
  -> Accepted ADR
  -> implementation task
  -> tests and validation
```

不得因为本决议接受了 ADR 队列，就预先把六项 ADR 标记为 accepted。

每份 ADR 至少包含：

- context and problem；
- decision；
- alternatives；
- invariants；
- ownership and dependency rules；
- failure semantics；
- persistence/recovery；
- compatibility and migration；
- security and operational effects；
- required tests；
- explicit non-goals。

## 6. Implementation Gate

Funding Arbitrage application implementation只能在下列条件同时满足后开始：

1. ADR-009～ADR-014 均被正式接受；
2. 受影响的 interfaces 和 module topology 已更新；
3. 核心能力拆分为独立任务和验收项；
4. Basket Risk 在任何 child submit 前完成；
5. Order Group journal/recovery 设计已有故障测试；
6. Account/margin 数据来源和 reconciliation 已定义；
7. Financial Ledger 的 funding/fee/PnL 恒等式已定义；
8. 离线 acceptance plan 已批准。

开始核心能力实现不等于允许 Testnet。Testnet 还需要独立凭证、外部环境和恢复验收。

## 7. Original Next Action — Completed

下一项工作是起草：

```text
ADR-009 Portfolio Snapshot Model
```

ADR-009 应先解决：

- Market、Funding、Account、Position、Health 的状态所有权；
- snapshot assembler 的单写者和读取者；
- per-source timestamps；
- maximum source skew；
- completeness/freshness/quality；
- deterministic replay；
- bounded state；
- fail-closed behavior；
- 与现有 per-instrument Market State、Feature State、Account State 的兼容关系。

该审查门禁已于 2026-07-28 完成。后续状态见第 9 节。

## 8. Authorization Boundary

本决议只授权按顺序起草和审查六项 ADR。

它不授权：

- Funding Arbitrage 源码实现；
- Basket Order 实盘执行；
- Binance Testnet 多腿交易；
- 生产部署；
- 真实资金交易。

## 9. ADR-009 Review Update — 2026-07-28

Web GPT 已完成对 ADR-009 的架构审查，并接受以下核心方向：

- Snapshot 是通用决策基础设施，不只是 Carry 的私有数据聚合；
- 当前同步、确定性运行时可以保留；
- Event Bus 不能替代 freshness、coherence 和 ownership；
- immutable、explicit readiness、fail closed；
- event、arrival 和 monotonic time 分离。

Codex 核对后认为 ADR-009 不需要结构性修改。现有草案已经把 Snapshot 分为：

```text
cex_quant.snapshots
  -> 通用 observation、policy、readiness 和 metadata

cex_quant.applications.<application>.<TypedSnapshot>
  -> 应用专属、强类型的最终决策输入
```

同时保留本决议已有修正：通用 OMS 使用 `PARTIALLY_EXECUTED`；
`PARTIALLY_HEDGED`、`HEDGED`、`ACTIVE` 和 `CLOSED` 由 Carry application
aggregate 根据 OMS 和 Portfolio 权威事实派生。

当前状态是：

```text
Web GPT review: ACCEPT
Codex verification: NO STRUCTURAL REVISION REQUIRED
Project owner decision: ACCEPT
ADR-009 status: Accepted
Generic Snapshot implementation: AUTHORIZED AS T025/T026/A012
Funding application implementation: NOT AUTHORIZED
```

项目负责人于 2026-07-28 明确接受 ADR-009。通用 Snapshot Infrastructure
进入 T025、T026 和 A012；ADR-010 可以开始起草。完整逐项答复见
`40_codex_adr009_review_response.md`。

## 10. ADR-009 Implementation and ADR-010 Draft

ADR-009 接受后，通用能力按以下任务实现：

```text
T025 Generic Snapshot contracts, policy and assessment
T026 Runtime SnapshotCoordinator and evidence port
A012 Offline coherence, replay and restart acceptance
```

实现保持通用性，使用三来源 synthetic application 验证，不包含 Funding
Arbitrage 应用代码。ADR-010 Basket Intent Architecture 已起草，状态为
`Proposed — ready for architecture review`。

离线验证结果：

```text
Full regression: 379 passed
Acceptance: 31 passed
Strict MyPy: 86 source files
Branch coverage: 86.34% (gate: 85%)
Ruff / compile / secret scan: passed
```

ADR-009 implementation promotion commit:

```text
66e0d6cb9cfbafa0246dcee20e3ec414cbff97b7
```

ADR-010 审查重点：

- Basket leg 是否显式包含 canonical `AccountId`；
- V1 hard cap 是否为 16；
- `valid_until_ns` 是否强制；
- duplicate account/instrument scope 规则；
- whole-Basket binary Risk approval；
- 与 `PositionTargetIntent` 的兼容性。

在 ADR-010 被 Web GPT 审查并由项目负责人接受前，不实现 Basket 源码。

## 11. ADR-010 Compatibility Review and Acceptance

项目负责人要求 ADR-010 不能直接接受，必须先根据当前代码检查并修订：

- Intent 模型兼容性；
- core identifiers；
- `StrategyDecision` 和 `StrategyRuntime`；
- Objective Type 长期演进；
- Basket lifecycle 所有权；
- leg 排序策略。

Codex 完成源码核对后，ADR-010 作出以下修订：

```text
Basket identity:
  reuse existing IntentId

New cross-domain IDs:
  BasketLegId
  ObjectiveTypeId

Objective Type:
  versioned registered ObjectiveTypeRef
  no central enum
  no raw executable string

StrategyDecision:
  dataclass shape unchanged
  DecisionIntent union and runtime validation extend additively

Strategy input:
  add DecisionSnapshotPublication
  validate Basket snapshot causation

Basket lifecycle:
  none in ADR-010
  execution lifecycle -> ADR-011
  economic lifecycle -> ADR-014

Leg order:
  canonical account/instrument key
  not BasketLegId order
```

项目负责人此前给出的条件是完成这些检查和修改后接受。条件已满足，
ADR-010 状态更新为 `Accepted`。T027/T028/A013 获得授权，但范围只包括
Basket 契约和 Strategy 兼容性，不包括 OMS、Risk 或 Execution。
