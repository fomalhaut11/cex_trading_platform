---
id: AI-20260727-004
title: Web GPT Review of Funding Arbitrage Architecture
origin: web-gpt
status: REVIEWED
created: 2026-07-27
code_baseline: 97d10e33f8d69c2535a542bee9f095aec1c312b9
reviewed_response_commit: e4eab0e928e3bb8da0fdc608931876eddb0fcb78
supersedes: none
related:
  - 10_web_gpt_input.md
  - 20_codex_response.md
  - 90_resolution.md
external_share: allowed
sensitivity: public-project
---

# Web GPT Review: Funding Arbitrage Architecture

## Verdict

**ACCEPT WITH CONDITIONS**

当前 CEX 架构具备承载 Funding Arbitrage application 的基础能力，但不应直接进入策略编码。

资金费套利首先暴露的是交易基础设施缺口，而不是策略公式缺口：

1. 跨市场状态一致性；
2. 组合级风险管理；
3. 多腿订单生命周期；
4. 资金、成本与收益核算。

因此，Funding Arbitrage 应作为第一个 Carry Application，推动核心能力升级，而不是作为
普通的 `strategy/funding.py` 开发。

## 1. Event Bus 与一致性快照

同意 Codex 的判断：当前同步、确定性调用不是缺陷。对于 Funding Arbitrage，核心决策不是：

```text
Tick -> Strategy -> Order
```

而是：

```text
Spot State
Perpetual State
Account State
Risk State
      |
      v
Arbitrage Decision
```

当前阶段应修正此前偏向 Event Bus 的设计倾向，优先建立逻辑一致的 Portfolio/Carry
Snapshot。

建议快照至少包含：

```text
CarryMarketSnapshot
  timestamp / source timestamps / quality
  spot
    bid
    ask
    depth
  perpetual
    bid
    ask
    mark_price
    funding_rate
  account
    balance
    margin
    positions
```

策略只能消费通过完整性、时效性和一致性检查的快照。

说明：高频撮合、做市或多策略竞争将来可能需要更完整的事件分发能力，但这不构成当前
Funding Arbitrage 引入通用 Event Bus 的理由。

## 2. Basket Intent 是首要抽象

现有链路：

```text
Intent -> Risk -> Order
```

适用于单资产目标，但 Funding Arbitrage 表达的是一个 Trading Objective：

```text
OPEN CARRY
  +-- BUY Spot
  +-- SELL Perpetual
```

它不能被解释为两个互不相关的订单。应引入类似：

```text
BasketIntent
  purpose
  legs
    Spot target leg
    Perpetual target leg
```

Basket Intent 必须保持 venue-neutral，不包含 Binance payload、签名参数或执行适配器调用。

## 3. Parent-Child OMS

同意 OMS 需要从单订单生命周期扩展为：

```text
BasketIntent
      |
Parent Order Group
      |
  +---+---+
  |       |
Child A Child B
```

父对象必须持久记录：

- parent/basket identity；
- child identities；
- 每腿计划量与实际成交量；
- 风控批准；
- submit/unknown/partial/terminal 状态；
- 重启恢复和对账状态；
- legging exposure 和补偿动作。

审查中特别强调 `PARTIALLY_HEDGED`，因为真实市场无法保证跨 Spot 与 Perpetual 原子成交。

示例执行生命周期：

```text
CREATED
  -> RISK_ACCEPTED
  -> EXECUTING
  -> PARTIALLY_HEDGED
  -> HEDGED
  -> ACTIVE
  -> CLOSED
```

其中 `PARTIALLY_HEDGED` 是必须被正式表达的状态，因为它代表真实的腿风险。

## 4. Portfolio Risk

同意当前独立 Risk 边界是正确基础，但现有能力仍是 Instrument Risk。Funding Arbitrage
要求 Portfolio Risk。

### Delta Risk

必须计算组合净 Delta，而不是分别观察 Spot 和 Perpetual 名义头寸：

```text
net delta = spot delta + perpetual contract delta
```

### Basis Risk

必须监控：

```text
basis = perpetual price - spot price
```

策略可能对单边价格近似中性，但仍暴露于基差扩张、收敛路径和流动性差异。

### Legging Risk

系统必须明确识别：

```text
Spot filled + Perpetual failed = unhedged BTC exposure
```

并使用最大未对冲敞口、持续时间和恢复策略进行控制。

### Margin and Liquidation Risk

必须接入并建模：

- wallet balance；
- isolated/cross margin mode；
- initial and maintenance margin；
- liquidation price or liquidation distance；
- collateral quality and availability。

这些状态缺失或过期时，新增 Carry 仓位必须 fail closed。

## 5. Financial Ledger 与 PnL Attribution

订单成交不等于策略收益。Funding Arbitrage 的收益至少需要拆分为：

```text
Net PnL
  = funding cash flow
  + basis/mark change
  - trading commissions
  - other explicit costs
```

应新增：

### Funding Ledger

记录每次 funding settlement 的时间、instrument、asset、amount、venue reference 和所属
Carry Position。

### Fee Ledger

记录 Spot fee、Perpetual fee、funding settlement 以及确实发生的 withdrawal 等成本或
现金流。

### Strategy PnL Attribution

至少能够按以下维度复核：

```text
Carry application
  gross PnL
  funding
  basis / mark
  commissions
  other costs
  net PnL
```

没有真实 funding cash flow、费用和基差归因时，expected APR 只是模型估计，不是可验证收益。

## 6. Application Boundary

同意不使用：

```text
strategy/funding.py
```

建议的应用层方向：

```text
applications/
  carry/
    funding_arbitrage/
    basis_arbitrage/
    calendar_spread/
  market_making/
  statistical_arbitrage/
  directional/
```

`strategy` 继续保存通用运行时和 venue-neutral intent 契约；`applications` 负责组合构建和
应用聚合。Carry application 不能绕过 Feature、Risk、OMS 或 Execution 边界。

## 7. Required ADR Order

在实现前，按以下顺序完成并逐项审查：

1. Portfolio Snapshot Model；
2. Basket Intent Architecture；
3. Parent-Child Order Model；
4. Portfolio Risk Extension；
5. Financial Ledger Model；
6. Carry Application Boundary。

顺序很重要：后续 OMS、Risk 和 Accounting 契约必须基于已经确定的状态与意图语义。

## 8. Conditions of Acceptance

本审查接受 Codex 的总体差距判断，但附带以下条件：

- 不直接开发 `funding_arbitrage.py`；
- 先完成六项 ADR；
- Basket 所有 legs 必须在首个 submit 前完成组合级预检；
- `PARTIALLY_HEDGED`、unknown state 和 restart recovery 必须是正式状态；
- Portfolio/Carry Snapshot 必须有每个来源的时间、质量和最大允许 skew；
- Account、margin、funding cash flow、fees 和 PnL attribution 必须进入正式设计；
- 每个 ADR 完成后返回架构审查，不把六项 ADR 一次性视为自动通过；
- ADR 和离线测试通过不自动授权 Testnet、生产或实盘。

## Final Recommendation

下一阶段应为：

```text
Architecture Upgrade
  -> ADR Review
  -> Core Capability
  -> Funding Arbitrage MVP
```

Funding Arbitrage 是第一个“压力测试应用”。它用于验证 State、OMS、Risk 和 Accounting
抽象能否共同承载真实组合策略。
