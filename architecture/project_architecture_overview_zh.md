# CEX Quant 当前项目架构与模块总览

文档状态：当前实现说明

基线日期：2026-07-28

适用代码：`src/cex_quant/`

生产授权：无

## 1. 文档目的

本文面向项目维护者、架构审查者和无法直接访问本地代码的外部 AI，
说明当前项目已经实现的架构、模块边界、公开接口、运行链路、状态所有权、
测试证据和后续扩展计划。

本文严格区分三类内容：

1. **已实现**：源码和测试中已经存在的能力；
2. **待外部验收**：离线实现已完成，但仍依赖 Testnet、目标主机或部署环境；
3. **规划中**：只存在于开发计划或 Proposed ADR，尚未进入公开代码接口。

因此，本文不能被理解为生产上线许可，也不能把 Proposed ADR 描述为已完成能力。

## 2. 项目定位

CEX Quant 是面向中心化交易所的生产导向量化交易运行时。当前实现采用：

- Python-first、Rust-ready；
- 模块化单体 `trading-core`；
- 不可变、强类型的领域契约；
- 单写者状态模型；
- 同步、确定性的核心状态转换；
- asyncio 处理网络 I/O；
- 有界旁路承载记录、监控和运维工作；
- fail-closed 风控、恢复和操作控制。

当前系统不是一个只包含“策略脚本”的交易机器人。它首先建设交易事实、
状态、风控、订单生命周期、恢复和运维基础，再由具体应用策略复用这些能力。

## 3. 当前总体拓扑

```text
                         ┌──────── Recorder / Replay
                         │
Exchange                 │
   │                     │
   v                     │
Market Data Adapter      │
   │ raw venue payload   │
   v                     │
Normalizer ─> Validator ─┴─> Market State
                                  │ immutable views
                                  v
                            Feature Engine
                                  │
                                  v
                           Strategy Runtime
                                  │ venue-neutral intent
                                  v
                              Risk Engine
                                  │ approved intent
                                  v
                                  OMS
                                  │ canonical order command
                                  v
                         Execution Gateway
                                  │ venue request
                                  v
                               Exchange

Private order stream / REST query ─> Reconciliation ─> OMS
Account updates                  ─> Portfolio State
Health / clock / operator state  ─> Runtime and mandatory risk gates
```

核心约束：

- Strategy 只能输出与交易所无关的交易意图；
- Risk 是强制边界，不能绕过；
- OMS 是订单状态的唯一写者；
- Execution 负责协议适配，但不拥有规范订单状态；
- Binance 原始对象不得逃逸出适配器包；
- 阻塞存储 I/O 不得进入交易热路径。

## 4. 进程与并发模型

第一阶段将以下模块保留在一个 `trading-core` 进程中：

```text
market_data + market_state + features + strategy + risk + oms + execution
```

这样做的目的是保持状态转换顺序显式、同步且可重放。网络连接和异步请求使用
asyncio；关键领域状态仍由串行调用更新。

Recorder、监控、运维 API 和外部存储可以成为独立服务，但必须通过有界通道
通信。只有当性能测量、语言运行时或故障域要求成立时，领域模块才应拆成服务。

项目没有为了资金费套利而引入通用热路径 Event Bus。跨市场决策的规划方向是
建立有时间、质量和一致性规则的类型化决策快照，而不是仅把多个异步事件推给策略。

## 5. 源码目录

```text
src/cex_quant/
├── core/             # 标识符、时间、定点数、事件元数据
├── instruments/      # Spot、Perpetual、Future、Option 规范合约
├── market_data/      # 规范行情事实、校验和市场状态
│   └── adapters/     # 交易所行情适配器；当前首先实现 Binance
├── features/         # 注册式在线特征、期权定价、IV、Greeks、曲面
├── strategy/         # 策略生命周期和交易意图
├── risk/             # 确定性、fail-closed 的交易前风控
├── oms/              # 订单契约、状态机、日志和恢复协调
├── execution/        # 执行网关和 Binance 下单/查询/撤单适配
├── portfolio/        # 余额、持仓和账户快照
├── recorder/         # 规范事件的追加记录和确定性重放
├── observability/    # 时钟与组合健康状态
├── snapshots/        # 通用跨来源决策快照契约与一致性评估
└── runtime/          # 组合根、运行管线、监管和部署适配
```

辅助目录：

```text
architecture/         # 当前架构规则
adr/                  # 架构决策记录
interfaces/           # 稳定数据和边界契约
development/          # 计划、进度、测试和实现设计
operations/           # 部署、回滚、恢复和事故手册
tests/                # 单元、集成、场景和验收测试
ai_collaboration/     # Web GPT 与 Codex 的讨论交换区，不是架构权威
```

## 6. 已实现模块

### 6.1 `core`

职责：

- 跨领域稳定基础类型；
- 强类型业务标识符；
- UTC Unix 纳秒和单调纳秒；
- 精确定点数；
- 事件来源、时间精度和 schema 元数据。

主要公开接口：

```text
EventMetadata, EventSource, EventTimeSource
UnixNanos, MonotonicNanos, DurationNanos
FixedPoint, Price, Quantity, Money, Rate
AccountId, Instrument-related IDs, StrategyId, IntentId,
ClientOrderId, VenueOrderId, EventId, CorrelationId
```

该包不依赖业务领域，也不进行 I/O。

### 6.2 `instruments`

职责：

- 表示规范化交易品种；
- 隔离交易所 symbol 和原始元数据；
- 对现货和合约提供一致身份与规格。

已支持的领域品种：

- Spot；
- Perpetual；
- dated Future；
- Option。

主要公开接口：

```text
Instrument, InstrumentId, InstrumentKind, InstrumentStatus
SpotSpecification, PerpetualSpecification, FutureSpecification
OptionSpecification, OptionSide, ExerciseStyle, SettlementType
```

这里的“支持 Option”是指规范领域模型与期权数学，不代表 Binance Options
网络适配器已经完成。

### 6.3 `market_data`

职责：

- 将外部消息归一化为规范行情事实；
- 对事实进行结构化校验；
- 维护单写者 L1、部分深度和重建订单簿状态；
- 对序列重复、缺口、越序、交叉盘口和重同步给出显式结果。

主要行情事件：

```text
MarketTrade, AggregateTrade, BestBidAsk
OrderBookDelta, PartialBookFrame
KlineUpdate
MarkPriceUpdate, IndexPriceUpdate, FundingRateUpdate
OpenInterestUpdate
VenueOptionAnalyticsUpdate
```

主要状态接口：

```text
L1State / L1View
PartialBookState / PartialBookView
ReconstructedOrderBook / OrderBookView
StateUpdateResult, UpdateDisposition, MarketStateStatus
```

Binance 子模块已实现：

- Spot、USD-M、COIN-M 的产品识别；
- `exchangeInfo` 到规范 Instrument 的映射；
- trade、aggregate trade、book ticker、diff-depth、partial-depth；
- mark/index/funding 和 kline 归一化；
- combined stream 会话、连接生命周期、重连策略；
- WebSocket transport。

原始 Binance payload 只能存在于适配器边界内。

### 6.4 `features`

职责：

- 注册、校验和执行生产在线特征；
- 保存特征版本、来源、质量和时间；
- 向策略发布不可变 `FeatureSnapshot`；
- 提供期权定价和派生分析。

主要公开接口：

```text
FeatureRegistry, FeatureDefinition, FeatureContext
OnlineFeatureEngine, FeatureUpdateReport
FeatureValue, FeatureSnapshot, FeatureMetadata, FeatureQuality
```

期权能力包括：

```text
Black-Scholes / Black-76 定价
Implied Volatility 求解
OptionGreeks
VolatilitySurfacePoint / VolatilitySurfaceSnapshot
```

边界约定：

- 可观察的期权报价属于 Market Data；
- IV、Greeks、smile、term structure 和 volatility surface 属于 Features；
- 交易所提供的 analytics 只作为带 venue provenance 的输入，不自动成为内部权威值。

### 6.5 `strategy`

职责：

- 管理策略启动、运行、失败和停止生命周期；
- 接收规范市场事件、状态和特征；
- 产生与交易所无关的决策意图；
- 限制策略可操作的 scope。

主要公开接口：

```text
Strategy, StrategyRuntime, StrategyContext, StrategyInput
StrategyDecision, StrategyStatus, StrategyPhase
PositionTargetIntent, DecisionIntent
```

当前公开意图是单品种 `PositionTargetIntent`。策略不能构造 Binance 请求、
不能直接调用 Execution，也不能绕过 Risk 和 OMS。

项目目前提供策略运行基础，未把某个具体盈利策略声明为生产完成。

### 6.6 `risk`

职责：

- 对每个策略意图执行强制交易前检查；
- 在数据陈旧、时钟异常、健康未知或限制缺失时 fail closed；
- 用精确定点值检查仓位、变化量和名义价值；
- 返回结构化允许或拒绝结果。

主要公开接口：

```text
RiskEngine, RiskContext, RiskLimits
RiskDecision, RiskDecisionStatus, RiskRejectReason
```

当前实现是单品种交易前风控。组合级 Delta、basis、legging、margin 和
liquidation 风险属于后续多腿扩展，尚未实现。

### 6.7 `oms`

职责：

- 拥有规范订单的唯一真实状态；
- 验证风险批准后的请求；
- 执行合法状态转换；
- 幂等处理交易所回报；
- 记录 checksummed 追加日志；
- 在重启后重放并通过 REST/私有流协调未知状态。

主要公开接口：

```text
ApprovedOrderIntent, OrderRequest, OrderEvent, OrderView
OrderSide, OrderType, TimeInForce, OrderStatus
OrderStateMachine
JsonLinesOmsJournal
OrderReconciliationSnapshot / ReconciliationResult
```

当前 OMS 管理单个订单生命周期。Parent/Child Order Group 仍是规划能力。

### 6.8 `execution`

职责：

- 把规范 OMS 命令转换为交易所协议；
- 提交、查询和撤销订单；
- 处理签名、凭证读取、HTTP/WebSocket transport；
- 将交易所响应归一化为规范执行事实；
- 对“请求可能已发送但结果未知”给出显式错误。

主要公开接口：

```text
ExecutionGateway, OrderReconciliationGateway
SubmitResult, CancelResult, QueryOrder, CancelOrder
AuthenticatedBinanceExecutionAdapter
EnvironmentBinanceCredentialProvider
AsyncioBinanceHttpTransport
PrivateOrderStreamSupervisor
```

Binance 已实现 Spot、USD-M 和 COIN-M 的下单、查询、撤单映射及私有订单流
基础。凭证在每次请求时通过 provider 获取，不应出现在源码、日志、fixture
或 recorder 中。

### 6.9 `portfolio`

职责：

- 保存规范化的账户、余额和持仓事实；
- 通过单写者 `AccountState` 更新；
- 向 Risk 和 Strategy 发布不可变账户快照；
- 保证 scope、排序、幂等和冲突行为明确。

主要公开接口：

```text
Balance, Position, PositionAccounting
AccountUpdate, AccountSnapshot, AccountState
```

当前模块保存交易所归一化值，但不负责复杂估值、Greeks、保证金模型、
强平价格计算或策略 PnL 归因。

### 6.10 `recorder`

职责：

- 追加记录规范事件；
- 限制单条记录大小；
- 使用格式版本和 checksum 检查完整性；
- 按原顺序确定性重放。

主要公开接口：

```text
EventRecorder, EventReader, ReplaySink
JsonLinesRecorder, JsonLinesReader
encode_event, decode_event, replay
```

JSONL 适配器是同步存储实现。Runtime 必须通过有界 `RecorderHandoff`
把它移出热路径。

### 6.11 `observability`

职责：

- 采集本机和交易所时钟证据；
- 检测 offset、RTT、样本年龄和单调时钟回退；
- 聚合组件健康状态；
- 为 Risk、Runtime 和运维接口提供结构化报告。

主要公开接口：

```text
ClockHealthMonitor, ClockHealthThresholds
VenueClockSample, HealthCheck, HealthReport, HealthStatus
aggregate_health
```

### 6.12 `snapshots`

职责：

- 将独立状态所有者发布的不可变 view 包装为 `SourceObservation`；
- 按来源分别检查 event age、arrival age、future skew 和 schema；
- 按 coherence group 检查跨来源时间偏差；
- 只在所有强制门禁通过时产生 `READY`；
- 保留源状态所有权，不制造 Universal Snapshot。

主要公开接口：

```text
SourceObservation
SourceFreshnessRule, CoherenceGroup, SnapshotPolicy
SnapshotAssessment, SnapshotIssue, SnapshotReadiness
DecisionSnapshotMetadata, DecisionSnapshotPublication
assess_snapshot
```

Runtime 中的单写者 `SnapshotCoordinator` 只保留每个已配置来源的最新值和
有界 ID 冲突缓存。重启后从空状态和 `NOT_READY` 开始；旧快照只能作为证据。

### 6.13 `runtime`

职责：

- 作为唯一组合根连接所有领域端口；
- 强制执行 Validator → State → Feature → Strategy → Risk → OMS → Execution；
- 管理 recorder handoff、异步执行桥和应用生命周期；
- 管理 Binance 环境、时钟探测、私有流和启动 reconciliation；
- 提供操作员停机、reduce-only、安全恢复、认证和审计边界；
- 生成运行健康与就绪状态。

主要公开接口：

```text
TradingPipeline, TradingApplication, TradingDeploymentRuntime
CanonicalOmsApplicationService, AsyncExecutionPortBridge
RecorderHandoff
StartupOrderReconciliationCoordinator
PrivateStreamApplication
BinanceEnvironmentConfig, BinanceClockProbeService
OperatorController, OperatorRiskGate
AuthenticatedOperatorCommandService, OperatorCommandEndpoint
RuntimeHealthService
```

运维 endpoint 是协议无关的边界，本身不拥有公网 listener。实际 TLS/mTLS
终止、受保护身份转发和远程审计保留仍属于目标部署环境。

## 7. 模块依赖规则

`A -> B` 表示 A 可以依赖 B 的公开契约：

```text
instruments -> core
market_data -> instruments, core
features -> canonical market facts/state views, instruments, core
strategy -> features, instruments, core
risk -> strategy intent + portfolio/feature views + core
oms -> approved canonical intent + instruments + core
execution -> OMS public contracts + instruments + core
portfolio -> instruments + core
runtime -> all required domain ports
```

禁止关系：

- 任何领域包依赖 `runtime`；
- Strategy 依赖交易所适配器；
- Execution 直接修改 OMS 状态；
- Portfolio 复制并成为市场状态的第二写者；
- 交易所原始字典穿过领域边界；
- 可变状态对象跨模块共享。

公开 API 由各包 `__init__.py` 的职责说明和显式 `__all__` 管理。导入顶层
`cex_quant` 不执行配置、注册或 I/O。

## 8. 状态所有权

| 状态 | 唯一写者 | 主要读取者 |
|---|---|---|
| Market State | 对应 Market State Engine | Features、Strategy、Recorder |
| Feature State | Online Feature Engine | Strategy、Monitoring |
| Strategy State | 对应 Strategy 实例 | Strategy Runtime |
| Risk State | Risk Engine | Operations、Monitoring |
| Order State | OMS | Risk、Portfolio、Operations |
| Account/Position State | Portfolio/Account Engine | Risk、Strategy |
| Connector Health | 对应 Connector | Runtime、Monitoring |
| Operator Authority | Operator Controller + durable journal | Risk gate、Operations |

数据库记录、JSONL 日志和 replay 文件是历史证据与恢复输入，不是运行中的
第二份实时权威状态。

## 9. 一次交易决策的运行链路

```text
1. Adapter 接收外部消息
2. Normalizer 生成规范行情事件
3. Validator 检查事件
4. 单写者 Market State 原子更新
5. 注册式 Feature Engine 更新信息状态
6. Strategy Runtime 产生 PositionTargetIntent
7. Risk 根据上下文批准或拒绝
8. Runtime 只把已批准且身份一致的意图交给 OMS
9. OMS 先持久化所需生命周期事实
10. Execution Adapter 构造并发送 Binance 请求
11. REST/私有流结果回到 OMS
12. 未知状态必须先查询和 reconciliation，不能盲目重复提交
```

任一强制关卡失败时，不得把新订单送往 Execution。操作员状态默认 HALTED；
只有认证、授权和持久化成功的控制命令才能改变交易权限。

## 10. 时间、数值和数据契约

### 时间

- 对外可比较时间：UTC Unix nanoseconds；
- 本进程持续时间和超时：monotonic nanoseconds；
- 不用 wall clock 计算本地 elapsed duration；
- venue time、receive time、processing time 不得混为一个字段；
- 时钟健康不满足要求时，Risk fail closed。

### 数值

- 价格、数量、金额和费率使用 `raw + scale` 的精确定点表示；
- 不用二进制 float 表示订单价格、数量或账户金额；
- 模型和特征内部可使用 float，但必须带特征版本、质量和来源；
- 交易所过滤器和精度规则在适配器/Instrument 映射边界处理。

### 契约

- 公共 dataclass 倾向 `frozen=True`、`slots=True`、keyword-only；
- ID 类型不能用可互换的普通字符串代替；
- 有界 collection 优先使用确定性 tuple；
- schema 和持久化格式需要显式版本；
- 错误使用稳定代码与清洗后的 reason，不携带秘密。

## 11. 产品和交易所覆盖

| 能力 | 当前状态 |
|---|---|
| Spot 领域模型 | 已实现 |
| Perpetual 领域模型 | 已实现 |
| Dated Future 领域模型 | 已实现 |
| Option 领域模型 | 已实现 |
| Option IV / Greeks / surface | 已实现为 Feature |
| Binance Spot 行情/执行基础 | 已实现，待外部 Testnet 验收 |
| Binance USD-M 行情/执行基础 | 已实现，待外部 Testnet 验收 |
| Binance COIN-M 行情/执行基础 | 已实现，待外部 Testnet 验收 |
| Binance Options 网络适配 | 未实现，按进入范围时补充 |
| 实盘资金交易 | 未授权 |

## 12. 恢复和故障语义

已实现的主要安全语义：

- 订单和操作员命令使用 checksummed、追加式、可重放日志；
- 日志损坏、外部修改或持久化失败会锁定安全状态；
- `SUBMITTING` 或发送后超时不会被当作未下单；
- 未知订单先通过 REST 和私有流 reconciliation；
- 私有流启动采用 stream-first 和有界缓冲，避免 REST 快照窗口丢失更新；
- 断线、续租和重连有界，关闭时清理任务和资源；
- recorder overflow、worker failure 和 storage failure 不被静默忽略；
- 重启后依靠日志和交易所权威事实恢复，不复用旧进程的内存许可。

## 13. 当前测试和质量证据

截至本基线，项目包含 86 个 Python 源码文件和 61 个 Python 测试文件。
最近记录的完整验证结果：

| 检查 | 结果 |
|---|---|
| 源码编译 | 通过 |
| 完整回归 | 379 passed |
| Acceptance 场景 | 31 passed |
| Ruff | 通过 |
| strict MyPy | 86 个源码文件通过 |
| Branch coverage | 86.34%，高于 85% CI 门禁 |
| Python | 3.11 和 3.14 通过 |
| 高置信度秘密扫描 | 通过 |

离线场景覆盖：

- 订单簿 gap/resync 和 100,000-event 基线；
- recorder/replay 确定性；
- option bounds、IV 和 Greeks；
- Strategy → Risk → OMS → Execution 强制顺序；
- OMS 日志、未知状态、重启和 reconciliation；
- Binance 请求映射、签名和凭证轮换；
- 私有流启动竞态和资源清理；
- 时钟、健康、operator halt、reduce-only；
- mTLS 身份输入、HMAC 命令、重放保护和外部审计失败。

这些结果证明离线确定性基础，不等同于目标主机性能、Testnet 或生产验收。

## 14. 仍需完成的外部门禁

### 14.1 Binance Testnet

需要用户通过 `BinanceCredentialProvider` 提供 Testnet 凭证，并验证：

- 签名 account 请求和服务器时间；
- 相同 client order ID 的 submit、query、cancel；
- duplicate、timeout-after-send 和 unknown-state 恢复；
- REST 与 user-data stream reconciliation；
- 日志、异常和记录中不出现秘密。

### 14.2 目标主机性能

需要在选定主机和存储配置下测量：

- normal、peak、burst；
- p50、p95、p99 延迟；
- 12–24 小时 soak；
- backpressure 和 recorder durability 成本；
- 内存斜率、线程和进程健康。

### 14.3 部署和运行

还需要：

- 持久、获批准的主机时间源；
- 真实 TLS/mTLS 终止和受保护身份转发；
- 远程审计服务和保留策略；
- secrets 注入、存储和轮换流程；
- 受监管进程重启和故障测试；
- 在目标主机演练部署、回滚、恢复和事故手册；
- 确定并配置 Git 分支保护策略。

## 15. 多腿组合交易：规划，不是当前实现

同时订阅两个或多个品种行情，只解决“看见多个市场”的问题。一个可恢复的
组合交易平台还需要：

- 对多个来源建立有 freshness、skew、quality 的决策快照；
- 在任何子订单提交前，对完整组合做一次风险审批；
- 记录 parent/child 执行组和部分成交事实；
- 在重启后恢复执行组并处理腿风险；
- 记录 funding、commission 等现金流并完成 PnL 归因。

规划中的通用拓扑是：

```text
Per-instrument States + Features + Accounts + Health
                         │
                         v
              Typed Application Snapshot
                         │
                         v
               Application Strategy
                         │ BasketTargetIntent
                         v
                  Portfolio Risk
                         │
                         v
               OMS Parent Order Group
                         │ child orders
                         v
             Existing Execution Gateways
                         │
                         v
                     Exchanges

Fills + funding + fees ─> Financial Ledger ─> Attribution
```

这是通用、受上限约束的 N-leg 能力，不会分别开发 `TwoLegOms`、
`ThreeLegOms`。Funding Arbitrage 是第一个两腿验证应用；后续还需要一个
离线三腿场景证明核心没有硬编码成两腿。

后续 ADR 计划新增但尚不存在于源码的包包括：

```text
strategy/basket.py
risk/portfolio.py
oms/order_group.py
accounting/
applications/carry/
runtime/basket_pipeline.py
```

ADR 状态：

| ADR | 主题 | 当前状态 |
|---|---|---|
| ADR-009 | Portfolio Decision Snapshot | Accepted；T025/T026/A012 已完成离线实现 |
| ADR-010 | Basket Intent | Proposed，待架构审查 |
| ADR-011 | Parent-Child Order | 尚未起草/接受 |
| ADR-012 | Portfolio Risk | 尚未起草/接受 |
| ADR-013 | Financial Ledger | 尚未起草/接受 |
| ADR-014 | Carry Application Boundary | 尚未起草/接受 |

在 ADR 被接受、任务编号和兼容性测试建立前，不修改现有公开契约。
现有单品种管线会持续作为回归基线。

## 16. 文档权威层级

遇到冲突时，应按问题类型查找对应权威来源：

| 问题 | 权威文档 |
|---|---|
| 已接受架构决策 | `adr/` 中状态为 Accepted 的 ADR |
| 当前模块依赖和状态所有权 | `architecture/` |
| 稳定数据结构和接口 | `interfaces/` 与包 `__init__.py` |
| 当前进度和验证结果 | `development/progress.md` |
| 外部验收缺口 | `development/remaining_external_gates.md` |
| 多腿开发计划 | `development/multi_leg_portfolio_trading_plan.md` |
| 部署和事故操作 | `operations/` |
| AI 讨论原文 | `ai_collaboration/`，仅作输入和审查证据 |

AI 讨论只有在结论被提升到 ADR、Architecture、Interface、Development 或
Operations 文档后，才会改变工程基线。

## 17. 当前结论

当前项目已经完成一个具备规范行情、状态、特征、单品种策略意图、强制风控、
单订单 OMS、Binance 执行适配、账户状态、记录重放、恢复和操作控制的
确定性交易基础。

它仍处于 **Phase 4：Production readiness and external acceptance**。
外部 Testnet、目标主机性能和真实部署控制尚未验收，因此不能称为生产上线完成。

多腿组合交易是下一轮架构升级。它会在保留当前单品种基础和执行适配器的前提下，
增加类型化决策快照、Basket Intent、组合风控、OMS Order Group、财务账本和
Carry 应用层；截至本文基线，这些能力仍是计划，不是已实现代码。
