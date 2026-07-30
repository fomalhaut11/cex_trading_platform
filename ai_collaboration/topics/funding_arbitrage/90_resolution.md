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
  - 82_codex_adr012_current_code_audit.md
  - 83_codex_adr012_proposal_handoff.md
  - 84_codex_adr013_current_code_audit.md
  - 85_codex_adr013_proposal_handoff.md
  - 86_codex_adr014_current_code_audit.md
  - 87_codex_adr014_proposal_handoff.md
  - 88_codex_20260729_batch_review_handoff.md
  - 94_web_gpt_adr012_final_acceptance.md
  - 95_web_gpt_adr012_final_committee_review.md
  - 96_web_gpt_adr012_formal_closure.md
  - ../financial_ledger/10_web_gpt_input.md
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
预检。该整篮子准入只允许创建一个持久化 Order Group，不等于所有 child 的 execution
permission；每个改变 exposure 的 child submit 还需要 ADR-011/012 定义的精确、有限、
一次性动作许可。

具体类型名称、leg 数量上限、是否直接通用化以及 v1 字段由 ADR-010 决定。

### 2.3 Durable parent-child OMS

采用通用、持久化 Parent Order Group 与 bounded Child Orders。必须覆盖：

- idempotency；
- child identity；
- partial fill；
- child `PARTIALLY_FILLED` facts and group progress views；
- unknown execution state；
- hedge timeout；
- compensation/recovery；
- restart replay；
- venue reconciliation；
- operator halt。

OMS Order Group 只拥有持久化执行控制生命周期和 child facts。Carry application 根据
child fills、Portfolio 权威仓位和 net Delta 派生 `PARTIALLY_HEDGED`。OMS group 的
`ACTIVE/CLOSING/CLOSED` 是执行控制状态，不代表经济 Carry Position 的同名状态；实际
venue position 仍由 Portfolio/Account State 提供权威事实。

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
| Partial execution facts | Modify | `PARTIALLY_FILLED` 属于 child；group 提供聚合 progress view，不设 `PARTIALLY_EXECUTED` 控制状态 |
| `PARTIALLY_HEDGED` | Modify | Carry application 根据 OMS facts 和净 Delta 派生 |
| `ACTIVE/CLOSED` Parent Order | Refine in ADR-011 | OMS 可用作 group 控制状态，但不表示 Carry 经济状态 |
| Portfolio Risk | Adopt | pre-trade basket risk + continuous supervision |
| Funding/fee/PnL ledger | Adopt | funding 与 commission 分类型核算 |
| `cex_quant.applications.carry` | Adopt in principle | 精确依赖规则由 ADR-014 固化 |
| 直接进入 Testnet | Reject | 核心能力和离线验收完成前禁止 |

## 4. ADR Queue

以下编号在本决议中登记为计划项；ADR 文件创建并通过审查后才成为正式架构基线。

| Order | Planned ADR | Scope | Required exit evidence | Status |
|---:|---|---|---|---|
| 1 | ADR-009 Portfolio Snapshot Model | 多 scope 状态所有权、时间、quality、skew、组装和读取 | 契约、所有权图、stale/skew 失败场景 | ACCEPTED_2026_07_28 |
| 2 | ADR-010 Basket Intent Architecture | Generic bounded N-leg objective、identity、limits、版本与整篮子预检 | schema、边界、单腿 intent 兼容策略 | ACCEPTED_IMPLEMENTED_2026_07_28 |
| 3 | ADR-011 Parent Order Group and Multi-leg Execution Model | Generic Order Group lifecycle、Execution Plan/Action、per-action permission、durable handoff、bounded children、partial、unknown 和恢复 | 状态机、identity、journal/replay、单腿兼容与故障矩阵 | ACCEPTED_2026_07_28_T029_T031_A014_AUTHORIZED |
| 4 | ADR-012 Portfolio Risk and Grouped Execution Authorization | execution-consistent position、basket projection、delta、basis、margin、liquidation、reservation、逐 action permit、持续监督 | 风险上下文、拒绝原因、durability、recovery 和 fail-closed 场景 | ACCEPTED_2026_07_29_T032_T035_A015_COMPLETE_OFFLINE |
| 5 | ADR-013 Financial Ledger and PnL Attribution | fill/account facts、balanced per-asset ledger、reconciliation、allocation、valuation 和 attribution | source schema、ledger invariant、reconciliation、PnL 恒等式 | PROPOSED_READY_FOR_REVIEW_2026_07_28 |
| 6 | ADR-014 Carry Application Boundary | applications/carry 所有权、正交状态、ownership、依赖和 runtime assembly | 模块拓扑、公开 API、禁止依赖规则 | PROPOSED_READY_FOR_REVIEW_2026_07_28 |

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

同时保留本决议的所有权边界并由 Accepted ADR-011 进一步收紧：
`PARTIALLY_FILLED` 是 child fact；OMS group 使用独立控制状态；
`PARTIALLY_HEDGED` 和 `HEDGED` 由 Carry application 根据 OMS 和 Portfolio
权威事实派生。OMS group 的 `ACTIVE/CLOSED` 不等于 Carry position 的经济状态。

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

## 12. ADR-010 Implementation Acceptance

T027、T028 和 A013 已于 2026-07-28 完成。

实现包括通用二至十六腿 Basket 契约、版本化 Objective Type Registry、
确定性身份与校验和序列化、Strategy Snapshot 因果校验，以及现有单腿
Pipeline 在 Risk/OMS 前对 Basket 的明确拒绝。

指定验收场景全部通过：

```text
PositionTargetIntent unchanged
BTC Spot +10 / BTC Perpetual -10 Basket generated
Option spread + Delta hedge three-leg Basket generated
Snapshot ID mismatch rejected
Single-leg Pipeline rejects Basket before Risk/OMS/Execution
```

完整证据见 `50_codex_adr010_implementation_acceptance.md`。

验证基线：

```text
397 tests passed
129 subtests passed
34 acceptance tests passed
88 source files pass strict MyPy
86.34% branch coverage
Ruff / compile / secret scan passed
```

本次 ADR-010 实现未创建 Parent/Child Order Group、子订单、交易所请求、
组合 Risk 或 Funding Arbitrage 应用。当时的下一架构审查边界是 ADR-011；
该 ADR 现已在后续审查中接受。

## 13. ADR-011 Review and Acceptance

Web GPT 的 ADR-011 审查输入已固化为
`60_web_gpt_adr011_review.md`。Codex 已检查当前 OMS model、`OrderRequest`、
Execution adapter、journal、reconciliation 和实际 runtime composition，
结果见 `61_codex_adr011_current_code_audit.md`。

`ADR-011-parent-order-group-multi-leg-execution.md` 当前状态为 `Accepted`。
它明确区分 Basket admission、Order Group execution intent、
Execution Plan、Execution Action、Child Order Attempt 与单次 execution permission，
并规定 Parent Order Group 只拥有持久化执行控制和 child facts；实际
Portfolio exposure、Delta、basis、margin 和 `HEDGED` 判断仍由 ADR-012
及后续 Carry application 拥有。

第二轮 Web GPT 审查已解决并被纳入八项技术问题：V1 单 exposure-changing
in-flight submit、同一身份的有限技术重传、Risk 加 operator 恢复、Portfolio
确认关闭、ADR-012 实现边界、ID 名称、16/8/64 operational bounds 和 mixed-version
journal。Codex 逐项响应见 `63_codex_adr011_review_response.md`。

项目负责人提交该条件审查并要求 Codex 读取执行；Codex 在全部修订完成后按
审查流程将 ADR-011 提升为 `Accepted`。T029-T031/A014 获得有界离线授权，
但 T031 必须在 exposure-changing Order Group child 到达 Execution adapter
之前 fail closed。真实 Portfolio action permit、外部组合提交、Funding
Arbitrage、Testnet 和生产执行仍由 ADR-012 及后续门禁阻断。

## 14. ADR-011 Implementation Acceptance

T029、T030、T031 和 A014 已于 2026-07-28 完成。

实现保持以下边界：

```text
ADR-010 BasketTargetIntent
  -> ADR-011 OrderGroupAdmission
  -> Order Group + ExecutionPlanRef
  -> ExecutionAction
  -> synthetic ExecutionActionPermit
  -> durable Child Order Attempt
  -X-> grouped external Execution (historical ADR-011 gate)
```

OMS 新增通用 N-leg 执行控制、精确 action/permit/revision/expiry 校验、
每腿 signed fill/working vector、单 action permit 绑定、同身份一次有限
技术重传、`RECOVERY_REQUIRED`、16/8/64 硬边界、较低部署边界以及
V1/V2 混合日志重放。

旧单腿路径也已使用共享 durable handoff：`SUBMITTING` 在外部 I/O 前
持久化，同步 accepted/rejected/definitely-not-sent/unknown 结果返回 OMS。
异步 bridge timeout 被分类为 unknown，而不是可盲目重试的 failure。

未实现：

- Delta、basis、margin、liquidation 或 hedge 计算；
- 真实 `ExecutionActionPermit` 发行；
- Funding/Carry 特化；
- grouped Execution adapter 路由或外部提交；
- Testnet/生产多腿执行。

自包含实现验收证据见
`80_codex_adr011_implementation_acceptance.md`；下一架构边界是 ADR-012。

## 15. ADR-012 Proposal

Codex 已在代码基线
`a752d3bff06a1b73b1103f543c64a2b6b64d2016`
上完成 ADR-012 当前代码审计，并形成：

- `82_codex_adr012_current_code_audit.md`；
- `83_codex_adr012_proposal_handoff.md`；
- `../../../adr/ADR-012-portfolio-risk-and-grouped-execution-authorization.md`。

提案冻结以下边界：

```text
Portfolio
  -> reconciled account baseline
  -> post-watermark OMS fill overlay
  -> normalized margin/collateral facts

Portfolio Risk
  -> pure exposure projection
  -> durable Basket reservation/approval
  -> exact current action permit
  -> continuous directive and recovery evidence

OMS
  -> group/action/child truth and evidence validation

Runtime
  -> serialized coordination and immediate pre-I/O guard
```

关键修正是禁止无水位地把 `AccountSnapshot` 与 OMS 全量累计成交相加，
避免已反映成交被重复计算。若 execution coverage 不可证明，普通组合 action
必须 fail closed。

该段最初记录的是 2026-07-28 Proposal 状态；现已由第 19 节取代。

## 16. ADR-013 Proposal

Codex 已在代码基线
`fa0df9e2a015db258457d226c7ed9fa5c689b8eb`
上完成 ADR-013 当前代码审计，并形成：

- `84_codex_adr013_current_code_audit.md`；
- `85_codex_adr013_proposal_handoff.md`；
- `../../../adr/ADR-013-financial-ledger-and-pnl-attribution.md`。

提案将 Accounting 固化为独立领域：

```text
fill/account financial facts
  -> balanced per-asset immutable ledger
  -> source and balance reconciliation
  -> immutable ownership allocation
  -> derived valuation and PnL attribution
```

OMS 累计成交和均价不能替代逐笔财务事实；行情 `FundingRateUpdate` 不能
替代真实账户 Funding settlement；Portfolio 绝对余额只能用于对账，不能
解释资金移动原因。共享账户归属无法证明时必须保留 `UNALLOCATED`，不得猜测。

ADR-013 当前状态是 `Proposed`，尚未分配实现或验收任务，没有创建
`cex_quant.accounting` 源码。

## 17. ADR-014 Proposal

Codex 已在同一基线上完成 ADR-014 当前代码审计，并形成：

- `86_codex_adr014_current_code_audit.md`；
- `87_codex_adr014_proposal_handoff.md`；
- `../../../adr/ADR-014-carry-application-boundary.md`。

提案把 Funding Carry 放置在：

```text
cex_quant.applications.carry.funding_arbitrage
```

应用层拥有经济生命周期、`PARTIALLY_HEDGED/HEDGED` 解释、应用持仓归属和
经济恢复提案；它只消费平台不可变视图并输出通用 `BasketTargetIntent`。
Market Data、Portfolio、Risk、OMS、Accounting 和 Execution 的权威所有权
保持不变。生命周期、hedge assessment 和财务最终性使用正交状态，不混入
一个枚举。

ADR-014 当前状态是 `Proposed`，没有创建 Funding/Carry 应用源码，也没有
解除组合外部提交阻断。

## 18. 2026-07-29 Batch Review

统一审核入口：

`88_codex_20260729_batch_review_handoff.md`

审核顺序：

```text
ADR-012 Portfolio Risk
  -> ADR-013 Financial Ledger
  -> ADR-014 Carry Application Boundary
```

三份 ADR 均需独立返回 `ACCEPT`、`ACCEPT WITH REQUIRED CORRECTIONS` 或
`REVISE`。审核意见按“当前 ADR 设计错误 / 其他 ADR 或实现问题 / 长期优化”
分类。该审核包不授权代码实现、Testnet、生产或真实组合外部提交。

## 19. ADR-012 Acceptance and Offline Implementation

2026-07-29，Web GPT 确认 ADR-012 Proposal 可以开始，但 grouped external
execution 不得开放；项目所有者同意。审核中重复出现的 ADR-011
A-01/A-03/A-06 属于整改前状态，当前分支已由
`81_codex_adr011_remediation_acceptance.md` 和 CI 证据关闭，因此没有重开
ADR-011。

ADR-012 升级为 `Accepted`，并授权 T032-T035/A015 有界离线范围。实现提交：

`69297d52e764822a1bdd60a23a9b7fca8446a520`

已完成：

- execution-consistent baseline + post-watermark fill overlay；
- normalized margin/liquidation inputs；
- exact unit-labelled N-leg Risk projection；
- whole-Basket approval and durable reservation；
- per-action permit and authorization generation；
- continuous directive、restart invalidation、recovery authorization 和
  target confirmation；
- shared pre-I/O Portfolio Risk guard；
- BTC Spot/Perpetual 两腿与 Option spread + Delta hedge 三腿 A015 场景。

`OrderGroupRuntime.submit_prepared_child()` 继续硬阻断。A015 完成不授权
Funding Arbitrage、ADR-013 Accounting、Testnet、生产或真实 grouped
external execution。

当前 Web GPT 审核入口：

`91_codex_adr012_implementation_acceptance.md`

## 20. ADR-012 Conditional Implementation Review

Web GPT 保持 ADR-012 `Accepted`，对实现给出 `CONDITIONAL ACCEPTANCE`。
评审原文固化为：

`92_web_gpt_adr012_implementation_review.md`

Codex 对 A-01 至 A-07 的处理：

- A-01：建立明确的 Risk snapshot 时间与有效期证据；
- A-02：用 typed invalidation trigger 取代无类型 changed 标记；
- A-03：reservation 改为 explicit resource key/claim 与共享容量序列化；
- A-04：target confirmation 使用版本化数量容差；
- A-05：确认 Greeks 仍由 Feature/Risk Analytics 生成，Risk 只消费；
- A-06：确认 permit 必须先 durable consume，之后才允许未来外部 I/O；
- A-07：区分经济拒绝、stale、insufficient data 和 recovery required。

整改实现基线：

`b082af0618e180f98441af5dc6d49c906994a012`

复审入口：

`93_codex_adr012_remediation_response.md`

本次整改不实现 ADR-013/014，不打开 grouped external execution，也不授权
Testnet 或生产交易。

## 21. ADR-012 Final Implementation Acceptance

2026-07-29，Web GPT 完成聚焦复审并确认：

- A-01 至 A-07 全部接受并关闭；
- ADR-012 实现从 `CONDITIONAL ACCEPTANCE` 升级为 `ACCEPTED`；
- 无需重开 ADR；
- grouped external execution 继续阻断；
- Risk decision explainability、Risk model versioning 和 audit-oriented
  Risk evidence 作为非阻断长期事项。

最终评审记录：

`94_web_gpt_adr012_final_acceptance.md`

详细委员会复核：

`95_web_gpt_adr012_final_committee_review.md`

下一阶段进入 Carry Application 架构议题，不直接实现 Funding Arbitrage。
评审意见中所称“ADR-013 Carry”按仓库既有编号规范化为：

```text
ADR-013  Financial Ledger and PnL Attribution
ADR-014  Carry Application Boundary
```

该规范化不改变 Web GPT 的架构意图，也不重新编号已经被代码、ADR 和协作
记录引用的文件。Carry 议题入口为：

`../carry_application/10_web_gpt_input.md`

## 22. ADR-012 Formal Closure and Next-Gate Order

Web GPT 随后对 `94` 和 `95` 两份最终记录完成复核，并正式关闭 ADR-012
验收流程：

```text
Design                  ACCEPTED
Implementation          ACCEPTED
Remediation             CLOSED
Grouped external        BLOCKED
Testnet / Production    NOT AUTHORIZED
```

正式关闭记录：

`96_web_gpt_adr012_formal_closure.md`

委员会明确下一阶段顺序：

```text
ADR-013 Financial Ledger/PnL design and scope alignment
  -> ADR-014 Carry Application formal review
  -> only after both acceptance: bounded implementation planning
```

现有 ADR-014 草案作为设计输入保留，但正式评审等待 ADR-013 的
ownership/allocation/read-port 范围对齐。此顺序不授权 Funding 执行、grouped
external、Testnet 或生产。

## 23. ADR-014 Final Offline Acceptance

2026-07-30，ADR-013 公共接口对齐完成后，Web GPT 接受 ADR-014 设计并授权
T040-T044/A017 credential-free 离线实现。随后对实现交接、公共接口和 ADR
完成最终复核：

```text
ADR-014 Design                  ACCEPTED
ADR-014 Offline Implementation ACCEPTED
T040-T044 / A017               CLOSED
Grouped external               BLOCKED
Testnet / Production           NOT AUTHORIZED
```

最终记录：

`../carry_application/70_web_gpt_adr014_final_acceptance.md`

下一主线调整为 Execution Promotion、最小 Strategy/Application SDK 和
Replay/Paper Trading，不继续进行推测性的基础设施扩张。Carry journal 和
lifecycle 不得泛化为所有应用必须继承的统一状态。
