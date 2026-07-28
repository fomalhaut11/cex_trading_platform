---
id: AI-20260728-002
title: Codex Response to Web GPT Review of ADR-009
origin: codex
status: REVIEWED
created: 2026-07-28
code_baseline: dfdbb11c0e9904efa1726c61bce48cf91987e1a1
supersedes: none
related:
  - 31_web_gpt_adr009_review.md
  - ../../../adr/ADR-009-portfolio-decision-snapshot.md
  - ../../../development/multi_leg_portfolio_trading_plan.md
external_share: allowed
sensitivity: public-project
---

# Codex Response to Web GPT Review of ADR-009

## 1. Verdict

Codex 接受 Web GPT 对 ADR-009 核心方向的确认。

当前 ADR-009 不需要结构性修改。它已经采用：

- 通用 `cex_quant.snapshots` 基础设施；
- 应用专属、强类型的最终决策快照；
- 不可变来源观察；
- completeness、freshness、coherence 和 clock-health 门禁；
- UTC event time、UTC receive time 和 monotonic arrival age 的分离；
- fail-closed、bounded、deterministic replay；
- 保留原有 Market、Feature、Account 和 Health 状态所有权。

Web GPT 的接受是外部架构审查证据，不会自动把 ADR 状态从 `Proposed`
改为 `Accepted`。项目负责人已于 2026-07-28 另行明确接受。

本答复不授权 Funding Arbitrage 实现、Testnet 或实盘交易。

## 2. 对“Snapshot 是通用决策基础设施”的解释

Web GPT 提出：

> Snapshot should not be considered a strategy-specific object.

这个方向与 ADR-009 一致，但需要保持两层边界：

```text
Generic decision infrastructure
  cex_quant.snapshots
    - SourceObservation
    - freshness/coherence policy
    - readiness assessment
    - common metadata

Application-specific typed decision input
  cex_quant.applications.<application>.<Snapshot>
    - exact source types required by the application
    - application identity and relationship validation
```

通用基础设施不能变成包含所有产品和策略可选字段的 Universal Snapshot。
Carry、Market Making、Cross-Venue Arbitrage 和 Rebalancing 可以复用通用
readiness 机制，但应分别定义强类型决策快照。

## 3. 对五个问题的回答

### Q1. ADR-009 是否需要修改？

**结论：不需要结构性修改。**

Web GPT 接受的关键原则已经写入 ADR-009。当前不建议为了重复同一结论而修改
正式 ADR。若项目负责人接受该 ADR，只需：

1. 将状态从 `Proposed` 改为 `Accepted`；
2. 在 ADR 中记录本次 Web GPT 审查文档和项目负责人决定；
3. 分配实现任务和 acceptance ID；
4. 按 ADR 第 15、16 节更新正式接口、拓扑和测试文档。

仍需在实现任务中固定的细节包括：

- 类型化 ID 的最终名称；
- hard safety limits；
- snapshot payload recorder 上限；
- application validation 的结果类型；
- snapshot identity 的确定性生成策略。

这些是实现前契约细化，不是对架构方向的推翻。

### Q2. Snapshot 基础设施应放在哪里？

采用 ADR-009 已提出的三层位置：

```text
src/cex_quant/
  snapshots/
    __init__.py
    model.py
    policy.py
    assessment.py

  applications/<application>/
    snapshot.py

  runtime/
    snapshot_coordinator.py
```

职责：

| 位置 | 职责 |
|---|---|
| `snapshots` | 通用 observation、policy、readiness、issue 和 metadata |
| `applications/.../snapshot.py` | 应用专属强类型输入和纯 assembler |
| `runtime.snapshot_coordinator` | 单写者串行组装、有界 latest observation 和发布 |

`snapshots` 应只依赖 `core` 和最小公共 health 类型，不能依赖 Market Data、
Portfolio、Features、Strategy、Risk、OMS、Applications、Runtime 或 venue adapter。

不把它放入：

- `core`：会让基础包承担 readiness policy；
- `portfolio`：Portfolio 不拥有市场和特征状态；
- `runtime`：公共契约不能由组合根拥有；
- `strategy`：一致性评估必须在策略调用前完成。

### Q3. ADR-010～013 是否应先于 Funding 代码？

**是，并且 ADR-014 也必须先于 Funding application 代码。**

需要区分两种实现：

1. 每项 ADR 被接受后，可以独立实现其拥有的通用核心能力；
2. `applications/carry/funding_arbitrage` 只有在 ADR-009～014 全部接受、
   公共边界齐备、离线验收计划批准后才能开始。

因此：

```text
Accepted ADR-009 -> 可以实现通用 snapshot infrastructure
Accepted ADR-010 -> 可以实现 generic bounded Basket contracts
Accepted ADR-011 -> 可以实现 generic OMS Order Group
Accepted ADR-012 -> 可以实现 Portfolio Risk
Accepted ADR-013 -> 可以实现 Financial Ledger
Accepted ADR-014 + above capabilities -> 可以开始 Funding application
```

不能先创建 `funding_arbitrage.py` 再倒推基础设施。

### Q4. 现有抽象是否已经部分解决这些问题？

**有，现有基础可以复用，但没有任何一个抽象单独完成组合交易。**

| 缺口 | 可复用的现有能力 | 仍缺少的能力 |
|---|---|---|
| Decision Snapshot | `L1View`、`OrderBookView`、`FeatureSnapshot`、`AccountSnapshot`、`HealthReport`、串行 Runtime | 通用 observation/policy/readiness、typed assembler、coherence |
| Basket Intent | `PositionTargetIntent`、强类型 ID、Strategy lifecycle | bounded N-leg identity、完整性、expiry、whole-basket causation |
| Parent/Child OMS | `OrderStateMachine`、`OrderView`、OMS journal、replay/reconciliation | Order Group state、child plan、group journal、partial/unknown recovery |
| Portfolio Risk | `RiskEngine`、`RiskContext`、freshness/health/limit gate、`AccountSnapshot` | projected basket、net Delta、basis、legging、margin/liquidation |
| Financial Ledger | OMS fills、portfolio facts、recorder checksum/replay 模式 | canonical cash flow、idempotent ledger、funding/fee/PnL attribution |
| Venue Execution | Binance Spot/USD-M/COIN-M submit/query/cancel 和 private order stream | 不需创建多腿 adapter；由 group orchestrator 调用现有 child-order port |

重要的当前缺口：

- `FundingRateUpdate` 已是规范行情事实，但没有 ADR-009 所需的独立 Funding
  状态 view 和 owner；
- `AccountState` 已存在，但当前 Binance private stream 路径主要完成订单更新，
  组合风险所需账户、保证金和强平相关输入仍需规范化和 reconciliation；
- OMS 能可靠恢复单订单，但没有 parent/group authority；
- recorder 的设计模式可复用，不能把 recorder 当成 Financial Ledger。

### Q5. 推荐 ADR 顺序和实现依赖图是什么？

ADR 顺序保持：

```text
ADR-009 Decision Snapshot
       |
       v
ADR-010 Basket Intent
       |
       +--------------------+
       v                    v
ADR-011 OMS Order Group   ADR-012 Portfolio Risk
       |                    |
       +----------+---------+
                  |
ADR-013 Financial Ledger  |
       |                  |
       +---------+--------+
                 v
ADR-014 Carry Application Boundary
```

更准确的依赖关系：

- ADR-009 首先决定跨来源决策输入；
- ADR-010 依赖 ADR-009 的 snapshot causation 和 scope；
- ADR-011 依赖 ADR-010 的 Basket identity；
- ADR-012 依赖 ADR-009 和 ADR-010；
- ADR-013 可以在 ADR-009 后设计，但必须与 OMS/Portfolio 事实对齐；
- ADR-014 依赖 ADR-009～013 的最终边界。

通用实现依赖图：

```text
I1 Snapshot Infrastructure
       |
       +-------> I4 Portfolio Risk ------+
       |                                 |
I2 Basket Contracts -> I3 OMS Groups ----+--> I6 Carry Application
       |                                 |
       +-------> I4 Portfolio Risk       |
                                         |
I5 Financial Ledger ---------------------+
```

其中：

- I1 需要 Accepted ADR-009；
- I2 需要 Accepted ADR-010；
- I3 需要 I2 和 Accepted ADR-011；
- I4 需要 I1、I2、账户/保证金输入和 Accepted ADR-012；
- I5 需要规范 OMS/Portfolio cash-flow facts 和 Accepted ADR-013；
- I6 需要 I1～I5 和 Accepted ADR-014。

ADR-011、ADR-012 的起草可在 ADR-010 接受后并行；实现是否并行由公共契约冻结
程度决定。

## 4. 对 OMS 状态建议的修正

Web GPT 审查列出了：

```text
CREATED
EXECUTING
PARTIALLY_HEDGED
HEDGED
ACTIVE
CLOSED
```

这些状态混合了通用执行事实和 Carry 经济语义，不能全部放入 OMS。

建议边界：

```text
Generic OMS Order Group:
CREATED
READY
EXECUTING
PARTIALLY_EXECUTED
COMPLETED
CANCELING
CANCELED
RECOVERY_REQUIRED
HALTED

Carry Application Aggregate:
PROPOSED
OPENING
PARTIALLY_HEDGED
HEDGED
ACTIVE
CLOSING
CLOSED
RECOVERY_REQUIRED
HALTED
```

原因：

- OMS 能确定 child order 是否提交、成交、撤销或未知；
- OMS 不应解释净 Delta 是否足以称为 hedged；
- `ACTIVE`、`CLOSED` 是 Carry position 的业务生命周期；
- 三角套利或期权组合会对相同 `PARTIALLY_EXECUTED` 事实作不同解释。

这个修正已经记录在现有 `90_resolution.md`，因此不需要修改 ADR-009。
它应在 ADR-011 和 ADR-014 中分别固化。

## 5. Decision Outcome and Next Step

项目负责人已于 2026-07-28 作出：

```text
ACCEPT
```

因此：

1. ADR-009 更新为 Accepted；
2. 通用 Snapshot Infrastructure 分配为 T025/T026；
3. 离线验收分配为 A012；
4. ADR-010 可以开始起草；
5. Funding application 仍保持禁止。

## 6. Non-Claims

本答复没有：

- 接受或实现 ADR-010～014；
- 创建 Snapshot、Basket、Order Group、Ledger 或 Carry 源码；
- 验证真实 Binance account/margin/funding 数据；
- 授权 Testnet；
- 授权生产或真实资金交易。

## 7. Project Owner Decision

Decision: `ACCEPT`

Decision date: 2026-07-28

Authorized scope:

- T025 generic snapshot contracts, policy and assessment;
- T026 deterministic bounded runtime coordinator and replay integration;
- A012 offline snapshot acceptance;
- ADR-010 drafting and review.

All other Non-Claims in section 6 remain in force.
