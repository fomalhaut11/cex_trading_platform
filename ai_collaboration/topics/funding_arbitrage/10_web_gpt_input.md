---
id: AI-20260727-002
title: Funding Arbitrage Engine Design
origin: web-gpt
status: READY_FOR_REVIEW
created: 2026-07-27
code_baseline: 97d10e33f8d69c2535a542bee9f095aec1c312b9
supersedes: none
related:
  - references/related_architecture.md
external_share: allowed
sensitivity: public-project
---

# Topic: Funding Arbitrage Engine Design

## Purpose

本主题不是要求直接编写 `funding.py`，而是把 Funding Arbitrage 作为第一个真实 application
strategy，用来检查当前交易基础设施是否具备承载组合级、多腿策略的能力。

## Background

CEX trading platform is being developed with:

- Python-first architecture；
- event-driven domain inputs and deterministic internal processing；
- state-based portfolio model；
- OMS / Execution separation；
- mandatory independent Risk boundary；
- canonical Spot and Perpetual instruments。

上述描述是本次待核对的背景，不应在未检查代码前视为已经全部满足。

## Primary Question

How should perpetual funding arbitrage be integrated into the current architecture?

更具体地说：

> 当前交易系统是否具备承载第一个真实、多市场、组合级策略的能力？

## Proposed Direction from Web GPT

Funding arbitrage should not be implemented as an isolated
`strategy/funding.py`.

推荐抽象：

```text
Trading System
      |
Strategy Engine
      |
Carry Arbitrage Engine
      |
  +---+---+
  |       |
Spot    Perpetual
Adapter Adapter
```

Carry Arbitrage 应作为 application strategy / portfolio-construction example，
用于验证 State、Event、OMS、Risk、Accounting 和 PnL attribution，而不是在策略内部直接
调用交易所适配器。

## Expected Market and Portfolio Inputs

策略需要同时关联：

```text
BTC Spot Tick
BTC Perpetual Tick
Funding Update
Account Update
Position Update
```

并形成一个时间和质量可审计的决策视图：

```text
CarryMarketVector {
  spot_price,
  perpetual_price,
  funding_rate,
  spot_position,
  perpetual_position,
  margin,
  as_of / freshness / quality
}
```

需要核对当前系统是使用类似 `MarketStateUpdatedEvent` /
`PortfolioStateChangedEvent` 的事件，还是通过其他确定性快照机制完成关联。

## Required Strategy-Level State

单独的 venue `Order`、`Trade`、`Position` 不足以表达一笔套利交易。建议存在类似：

```text
FundingArbPosition #001
pair: BTCUSDT spot / BTCUSDT perpetual

Spot leg:
  +10 BTC

Perpetual leg:
  -10 BTC

status:
  HEDGED

expected_apr:
  18%
```

需要判断该状态应归属 Portfolio、Strategy，还是独立的 application aggregate，并避免与
交易所权威持仓形成两个可变真相。

## Required Multi-Leg Execution Semantics

策略语义不是单腿 `BUY BTC`，而是：

```text
OPEN CARRY
  |
  +-- BUY Spot BTC
  |
  +-- SELL Perpetual BTC
```

需要判断 OMS 是否已经支持以下概念，或是否需要扩展：

```text
Parent / Composite Intent
  |
  +-- Spot child order
  |
  +-- Perpetual child order
```

真实交易所通常不能保证跨现货和永续的原子成交，因此还要明确 partial fill、第二腿失败、
超时、unknown execution state、补腿、减仓和重启恢复语义。

## Required Risk Semantics

策略应只表达“希望建立某个 carry portfolio”，由 Risk 独立判断允许或拒绝。

至少需要监控：

- net delta exposure；
- basis risk；
- funding reversal；
- liquidation and margin risk；
- stale or inconsistent market/account state；
- legging exposure and hedge timeout；
- concentration、notional 和账户可用余额。

策略不能自行批准风险，也不能直接构造 venue order。

## Questions for Codex

1. Does the current code architecture support this abstraction?
2. Is there an event bus or another deterministic mechanism for correlated
   multi-market inputs?
3. Where should the Carry Engine live?
4. Is the existing State model sufficient?
5. Does OMS support composite / parent-child orders?
6. Is Risk truly independent, and is its current context sufficient?
7. Are Account, margin, funding cash flow and PnL attribution implemented?
8. Which modules and contracts need modification?
9. What should be decided in ADRs before implementation?
10. What tests would prove the first real strategy is safe enough for Testnet?

## Requested Output

Codex should produce `20_codex_response.md` containing:

- evidence-based current capability assessment；
- explicit YES / PARTIAL / NO matrix；
- recommended module placement；
- required contracts and ownership；
- failure and recovery semantics；
- phased implementation plan；
- tests and acceptance gates；
- matters that must return to Web GPT for architecture review。

Do not implement the strategy in this topic stage.

## Security Check

- [x] No credentials, cookies, private keys or secret-bearing logs.
- [x] No dependency on a local absolute path.
- [x] Code baseline is a full commit SHA.
- [x] This document remains understandable when uploaded alone.
