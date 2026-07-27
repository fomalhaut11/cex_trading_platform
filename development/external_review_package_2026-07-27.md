# CEX Trading Platform — 外部验收资料包

文档日期：2026-07-27

代码仓库：`fomalhaut11/cex_trading_platform`

审查基线：`main` 分支，提交 `674949992a69e84468f10fb7dfd699ca03e44a2d`

当前阶段：Phase 4 — Production Readiness and External Acceptance

## 1. 本文用途与审查边界

本文是为**无法访问开发机、本地目录或先前对话**的外部审查者准备的自包含验收资料。
审查者只阅读本文，也应能判断：

1. 原始架构约束是什么；
2. 当前实现完成了什么；
3. 实现与设计的契合程度；
4. 测试和 CI 提供了什么证据；
5. 哪些事项仍未完成；
6. 当前成果是否可以进入生产或实盘。

本文不会把“存在某个本地文件”当作充分证据。文件名仅用于溯源；关键约束、实现语义、
测试数字和限制均在正文中展开。

本文也明确区分三类结论：

- **已实现且完成离线验证**：代码和自动化测试已覆盖；
- **部分完成或依赖部署环境**：仓库内边界已实现，但还需目标环境集成或人工验收；
- **计划项**：领域模型或扩展点存在，但具体交易所接入尚未实现。

重要限制：本文足以做设计一致性和阶段成果审查，但不能替代逐行源码安全审计。若审查者
需要验证每个陈述对应的具体实现，应再读取上述 Git 提交或仓库归档。

## 2. 执行摘要

当前成果不是单纯的代码骨架。确定性交易核心、主要领域契约、Binance 现货和合约接入、
期权特征计算、策略—风控—OMS—执行链路、持久化恢复、私有流监督、运行健康、操作控制
及其离线测试均已实现。

按项目任务台账的口径：

- 实现任务：**25/25 完成**。任务编号为 T001–T024，其中 T007 拆分为 T007A 和 T007B，
  因此实际是 25 个实现任务，不能误写为 24 个；
- 离线验收项：**11/11 完成**；
- 外部验收项：**0/2 完成**，分别是目标主机压力/浸泡测试和 Binance Testnet 鉴权验收；
- 回归测试：**357 项通过**；
- 场景验收：**29 项通过**；
- 分支覆盖率：**86.19%**，通过 85% 的 CI 门槛；
- Python 3.11 与 3.14 回归矩阵通过；
- Ruff、严格 MyPy（81 个源文件）、密钥模式扫描通过；
- 当前基线提交的 GitHub Actions 运行 `30186108955` 成功。

结论：

- **离线工程基线：通过。**
- **核心架构契合度：高，主要设计约束已经落实。**
- **生产就绪：未通过。**
- **实盘授权：不成立。**

未通过生产门禁不是因为现有回归报错，而是两项外部验收及若干部署侧控制尚未取得证据。

## 3. 原始设计基线

### 3.1 核心运行链

目标运行链固定为：

```text
Exchange
  -> Market Data Gateway
  -> Normalizer
  -> Validator
  -> Market State Engine
  -> Online Feature Engine
  -> Strategy Runtime
  -> Risk Engine
  -> OMS
  -> Execution Gateway
  -> Exchange
```

关键不变量：

- 风控是强制步骤，不允许策略绕过；
- 策略只产生交易所无关的意图；
- 只有执行适配器可以构造交易所请求；
- 实时交易路径与研究系统分离；
- 核心状态采用单写者模型；
- 公共领域对象不可变且强类型；
- 热路径不得同步等待持久化；
- 辅助通道必须有界，满载时必须有明确策略；
- 交易所原始 payload 不得泄漏到核心领域。

### 3.2 事件、状态与存储分离

项目将以下概念分开：

- Event：已发生且不可变的事实；
- State：由事件确定性演化出来的当前视图；
- Storage：事件或快照的耐久化载体。

事件不能被当成可变状态容器；存储故障也不能无界阻塞市场数据和交易决策热路径。恢复时，
系统使用持久化日志、快照或交易所查询重新建立状态，并对不确定订单采取保守处理。

### 3.3 产品覆盖与期权归属

统一产品模型覆盖：

- Spot；
- Perpetual；
- Dated Future；
- Option。

期权的买卖报价、成交和盘口属于市场数据；以下内容属于注册化 Feature，而不是原始行情：

- implied volatility；
- delta、gamma、vega、theta、rho；
- smile；
- term structure；
- volatility surface。

交易所提供的 Greeks 或波动率只能作为带明确 venue provenance 的辅助值保存，不能冒充
内部权威特征。

### 3.4 时间与数值

- 跨边界时间使用 UTC Unix nanoseconds；
- 时长和超时使用 monotonic nanoseconds；
- 价格、数量和金额使用 `raw + scale` 的定点表达；
- 只有特征计算允许浮点数，并必须携带质量或有效性语义；
- schema、feature 和算法版本均需显式表达。

选择纳秒单位是为了统一事件排序、跨模块契约和将来高精度数据源，而不代表 Windows 或
Python 实际时钟分辨率天然达到 1 ns。精度和分辨率不能混为一谈。

### 3.5 进程模型

首版使用模块化单体：

- 确定性交易流保留在一个 `trading-core` 进程中；
- recorder、monitoring、operations API 和 storage 可在测量证明需要时拆分；
- 跨进程或旁路通信必须使用有界通道；
- 操作入口的网络终止、mTLS 身份验证和反向代理属于部署边界，不进入交易核心。

## 4. 已完成的实现

### 4.1 Core 与 Instruments

已实现强类型标识、定点数值、纳秒时间、版本字段，以及 Spot、Perpetual、Future、Option
的统一领域对象。公共契约不携带 Binance 原始 JSON。

定点数的核心语义可概括为：

```text
value = raw × 10^(-scale)
```

订单、成交和持仓沿用该语义，避免在资金与数量域中直接使用二进制浮点。

### 4.2 Market Data 与 Market State

已完成 Binance Spot、USD-M Futures 和 COIN-M Futures 的产品元数据及市场事件归一化，
并实现：

- 归一化报价、成交和盘口事件；
- 数据验证与拒绝语义；
- L1、partial book、reconstructed book 三种视图；
- sequence gap 检测；
- snapshot/resync；
- 有界缓冲；
- 只读市场状态视图。

状态由单写者更新；消费者获取的是受控视图，而不是共享可变字典。

### 4.3 Recorder 与 Replay

已实现 JSONL 事件记录、校验和、确定性回放和损坏检测。Recorder 通过有界交接接收数据，
不在关键热路径上进行无界同步写盘。

### 4.4 Feature Engine 与期权

已实现注册表驱动的特征引擎，特征具有标识、版本、依赖、质量状态和确定性更新语义。

期权部分已实现：

- Black–Scholes；
- Black–76；
- implied volatility 求解；
- Greeks；
- smile / term / surface 所需的标准化契约；
- 缺失输入、过期输入、无解和数值异常的质量标记。

这满足“波动率曲面和 Greeks 属于 Feature”的设计决策。当前未实现 Binance Options
交易所专用行情/交易映射；这不影响统一期权领域和特征数学的完成状态，但属于后续接入项。

### 4.5 Strategy、Risk、Portfolio

策略运行时只消费受控状态和已注册特征，只输出 venue-neutral intent。

风控采用 fail-closed：

- 输入缺失、过期或状态不确定时拒绝；
- 拒绝结果有结构化原因；
- 风控通过后才允许进入 OMS；
- 风控没有由策略侧调用执行适配器的旁路。

Portfolio/Account State 已实现持仓、余额和订单相关的受控状态演化。

### 4.6 OMS 与 Execution

OMS 已实现订单生命周期、幂等标识、持久化 journal、重启回放和交易所 reconciliation。
执行边界已实现 Binance 签名 REST 的 submit/query/cancel 映射。

关键失败语义：

- 网络超时后不能武断认定下单失败；
- 结果未知的订单进入 unknown/reconcile 路径；
- 重试依赖稳定的 client order id 和查询结果；
- 恢复时本地 journal 与交易所权威状态对账；
- 无法证明安全时停止继续发单，而不是猜测。

### 4.7 私有流、监督与时钟

已实现 Binance 私有订单事件归一化、启动时 reconciliation、私有 WebSocket 生命周期、
HTTP/WS 传输边界、环境选择、重连监督、健康状态聚合和 server-time 探测。

离线代码可以检测：

- listen-key/私有流失效；
- WS 断线与重连；
- 时钟偏差超阈值；
- 组件不健康；
- 恢复前所需的对账状态。

但生产主机上的持续可信时间源尚未验收，见第 8 节。

### 4.8 凭证、操作控制与审计

已实现：

- 从环境/注入边界加载凭证；
- 不在领域对象或日志中传播密钥；
- 凭证轮换语义；
- 持久化 halt/recovery 状态；
- 操作命令 HMAC 认证；
- nonce / timestamp / replay 防护；
- 严格 JSON envelope；
- 有界并发与速率限制；
- 操作结果审计端口；
- 审计写入失败时的保守失败；
- 协议中立的 operator endpoint adapter；
- 部署装配、回滚、恢复和事故处理 runbook。

仓库内 endpoint adapter 不直接拥有公网监听器。真实 TLS/mTLS 终止、可信身份头注入、远程
审计留存由部署层负责。这与“操作 API 可作为旁路服务”的方向兼容，但在生产验收前必须
证明这些部署控制确实存在，不能只依赖应用层 HMAC。

## 5. 关键接口语义摘要

以下摘要让审查者无需打开源码也能评估模块边界。

### 5.1 市场事件

标准事件至少表达：

```text
event identity
instrument identity
venue
exchange timestamp (UTC ns)
receive timestamp (UTC ns)
sequence / ordering metadata
schema version
typed payload
quality / validation outcome
```

Normalizer 负责把 venue payload 转为标准事件；Validator 负责判断事件是否可进入 State。

### 5.2 Feature

Feature 输出至少表达：

```text
feature identity and version
instrument / scope
as-of time
input provenance
value
quality state
algorithm version
```

无质量标记的 venue analytics 不能替代注册特征。

### 5.3 Order Intent 与风险决策

策略输出的是抽象意图，不包含签名参数或 Binance 请求字段。风险引擎返回显式 approve 或
reject；只有 approve 才能创建 OMS 命令。缺失上下文不是“默认通过”。

### 5.4 OMS 恢复

恢复顺序的语义为：

```text
load durable local history
  -> reconstruct OMS state
  -> query authoritative venue state
  -> reconcile differences
  -> mark unknown/conflicting orders conservatively
  -> enable submission only after health gates pass
```

### 5.5 Operator Command

操作命令使用经过认证的 envelope，包含版本、命令、时间、nonce、身份和认证材料。
解析、认证、授权、限流、执行、审计各有明确失败结果。审计不可用时，重要控制命令不会被
静默当作成功。

## 6. 设计契合度矩阵

下表是本报告定义的 20 项核对口径，不是为了制造一个模糊的“完成百分比”。

| # | 设计要求 | 当前状态 | 结论与限制 |
|---:|---|---|---|
| 1 | 模块化领域边界 | 完全契合 | Core、MD、State、Feature、Strategy、Risk、OMS、Execution 分离 |
| 2 | 固定核心运行链 | 完全契合 | 运行时装配维持规定顺序 |
| 3 | 风控不可绕过 | 完全契合 | fail-closed，执行只能接收批准后的 OMS 命令 |
| 4 | Event/State/Storage 分离 | 完全契合 | 独立契约、状态演化、journal/replay |
| 5 | 不可变强类型公共契约 | 完全契合 | typed IDs、不可变领域对象、显式版本 |
| 6 | 定点价格/数量/金额 | 完全契合 | `raw + scale`，核心资金域不用 float |
| 7 | UTC ns 与 monotonic ns | 完全契合 | 对外时间和时长语义分离 |
| 8 | venue payload 不泄漏 | 完全契合 | 归一化层和执行适配器形成隔离边界 |
| 9 | 市场状态单写者 | 完全契合 | 更新权与只读消费视图分离 |
| 10 | 盘口多层视图和 gap 恢复 | 完全契合 | L1、partial、reconstructed、resync |
| 11 | 注册特征 | 完全契合 | registry、版本、依赖、质量和 provenance |
| 12 | IV/Greeks/曲面属于 Feature | 完全契合 | 期权报价与派生信息明确分层 |
| 13 | 有界热路径 | 完全契合 | recorder/side channel 有界，不设计无界阻塞写盘 |
| 14 | OMS 幂等、耐久和对账 | 完全契合 | journal、restart replay、unknown-state reconcile |
| 15 | 安全凭证传递 | 完全契合 | 环境/注入边界、轮换、日志脱敏契约 |
| 16 | 可认证操作和可审计恢复 | 完全契合 | HMAC、防重放、有界 endpoint、durable halt/audit |
| 17 | 模块化单体与旁路服务边界 | 部分/部署依赖 | 核心装配已完成；公网 listener、TLS/mTLS 终止在部署层 |
| 18 | 生产时间同步 | 部分/外部依赖 | 探测和健康门禁已实现；持续可信时间源未验收 |
| 19 | 目标主机性能及 Testnet | 外部未完成 | 离线基线通过；A002B、A002C 未通过 |
| 20 | Binance Options 专用适配器 | 计划项 | 统一模型与特征已完成，venue mapping 尚未实现 |

汇总：

- 完全契合：16 项；
- 部分完成或外部依赖：3 项；
- 计划项：1 项。

“16/20”不能解释成生产完成度 80%。其中多项是二元安全门禁；只要外部验收、时间同步或
部署身份边界未通过，系统就不应被批准用于实盘。

## 7. 自动化测试与 CI 证据

### 7.1 当前结果

| 检查 | 结果 |
|---|---:|
| Python 源文件 | 81 |
| Python 测试文件 | 58 |
| 回归测试 | 357 passed |
| 独立验收场景 | 29 passed |
| 分支覆盖率 | 86.19% |
| 覆盖率门槛 | 85% passed |
| Python 版本矩阵 | 3.11 passed；3.14 passed |
| Ruff | passed |
| strict MyPy | 81 source files passed |
| 高置信度密钥模式扫描 | passed |

“分支未覆盖”表示某些逻辑分支没有被测试执行，不等于测试报错。86.19% 是项目聚合分支
覆盖率，也不能证明每个安全关键分支都已覆盖。

### 7.2 29 个场景验收的覆盖主题

29 个场景按能力组覆盖：

- 核心交易管线：5；
- OMS 与 Binance 映射：3；
- 期权特征与时钟健康：6；
- Recorder/Replay/数据恢复：5；
- OMS 重启与 reconciliation：3；
- 私有流环境和监督：2；
- 具体传输与 server time：1；
- 运行健康与操作控制：1；
- 凭证轮换与操作恢复：1；
- 已认证操作部署：1；
- endpoint、审计和恢复：1。

合计：`5 + 3 + 6 + 5 + 3 + 2 + 1 + 1 + 1 + 1 + 1 = 29`。

### 7.3 CI 可追溯证据

- T024 实现提交：`ca4590541aae7736372bddf321167aac65f6fa61`；
- T024 实现 CI：GitHub Actions run `30186079369`，通过；
- 当前文档基线提交：`674949992a69e84468f10fb7dfd699ca03e44a2d`；
- 当前基线 CI：GitHub Actions run `30186108955`，通过；
- T023 实现提交：`52b6b9f`；
- T023 CI：GitHub Actions run `30157323695`，通过。

CI 使用只读 `contents` 权限，关键 actions 固定到不可变提交；执行 compile、Ruff、strict
MyPy、密钥模式扫描、pytest 分支覆盖率门禁，以及 Python 3.11/3.14 回归矩阵。

如审查者拥有 GitHub 访问权限，可用以下固定地址复核：

- 仓库：`https://github.com/fomalhaut11/cex_trading_platform`
- 当前提交：`https://github.com/fomalhaut11/cex_trading_platform/commit/674949992a69e84468f10fb7dfd699ca03e44a2d`
- 当前 CI：`https://github.com/fomalhaut11/cex_trading_platform/actions/runs/30186108955`

## 8. 未完成项与生产阻断项

### 8.1 A002B：目标主机性能和浸泡测试

尚需在真实目标主机执行：

- normal、peak、burst 负载；
- 端到端 p50/p95/p99；
- 12–24 小时 soak；
- 内存增长斜率；
- 有界队列水位和 backpressure；
- recorder/journal 耐久性；
- 慢盘、满盘、断网、进程终止等故障注入。

离线性能基线不能代替该项。

### 8.2 A002C：Binance Testnet 鉴权验收

尚需使用专用 Testnet 凭证验证：

- signed account query；
- submit；
- query；
- cancel；
- duplicate client-order-id；
- timeout 后 unknown state；
- restart reconciliation；
- 日志、报告和 Git 历史中无密钥泄漏。

凭证不得在聊天、Markdown、源码或 Git 中发送。应由用户在本机使用环境变量或被忽略的
本地启动器注入。

### 8.3 时间同步

新加坡 VPN 条件下，公开 Testnet HTTPS 可达。一次性测量曾得到：

- Spot：offset `-23.967 ms`，RTT `318.610 ms`；
- USD-M：offset `+32.652 ms`，RTT `436.006 ms`；
- COIN-M：offset `+44.133 ms`，RTT `472.832 ms`。

这些测量只证明当时 HTTP 探测健康，不是持续时间同步证据。当前 Windows Time 虽设为自动，
但 VPN Fake-IP 环境阻断 UDP/123，因此仍需批准的持续时间源或受控校准方案。

### 8.4 部署与运维

仍需在目标环境证明：

- 真实 TLS/mTLS 终止；
- 可信 operator identity 转发；
- 网络边界和最小权限；
- 远程、不可随应用进程一起丢失的审计留存；
- secret storage、注入、轮换和吊销流程；
- supervisor 的进程重启和健康汇报；
- runbook 的目标主机演练与人工签字；
- GitHub branch protection / required checks；
- rollback 和 incident response 的实际演习。

### 8.5 明确不宣称的内容

当前项目不宣称：

- 已生产就绪；
- 已获实盘授权；
- 已完成 12–24 小时目标机 soak；
- 已用真实或 Testnet 私钥完成端到端交易；
- 已完成 Binance Options venue adapter；
- 86.19% 覆盖率等于所有安全场景已证明；
- 本地密钥模式扫描等同于 GitHub Secret Protection；
- 一次 HTTP server-time 测量等同于可靠 NTP/PTP。

## 9. 风险与建议审查重点

建议外部审查者重点挑战以下问题：

1. operator endpoint 作为协议中立 adapter、外部 listener 作为部署组件的划分，是否充分满足
   “operations API 可独立故障隔离”的原始要求；
2. audit 写入失败时的 fail-closed 范围，是否涵盖所有有破坏性的操作；
3. unknown order 状态是否在任何异常路径上都能阻止重复发单；
4. 时钟健康降级是否真正阻止签名请求和交易，而不仅仅产生告警；
5. 有界队列满载策略是否按数据类型区分丢弃、阻塞、停止交易；
6. 期权表面质量标记是否能阻止策略消费陈旧或不完整曲面；
7. branch coverage 聚合值是否掩盖低覆盖的安全关键模块；
8. 目标主机部署是否能证明 mTLS 身份、密钥轮换和远程审计，而不是只存在 runbook。

## 10. 建议验收判定

基于本文证据，合理的阶段判定是：

| 审查对象 | 建议结论 |
|---|---|
| 架构决策是否已固化 | 通过 |
| 模块骨架是否完成 | 通过，而且已超过骨架阶段 |
| 确定性离线交易核心 | 通过 |
| Spot / Futures 基础接入 | 离线通过 |
| Options 领域与 Feature | 通过 |
| Binance Options 专用接入 | 未完成/非当前门禁 |
| 恢复、监督和操作控制 | 离线通过 |
| 自动化测试基线 | 通过 |
| 目标主机性能 | 未通过，等待 A002B |
| Binance Testnet 鉴权链路 | 未通过，等待 A002C |
| 生产/实盘 | 禁止批准 |

建议只有在 A002B、A002C、持续时间同步、部署身份/审计和 runbook 演练均取得可复核证据后，
才发起 Production Go/No-Go。

## 11. 有仓库访问权时的复核命令

此节不是阅读本文的前提，只为未来复核提供确定方法。

```powershell
git checkout 674949992a69e84468f10fb7dfd699ca03e44a2d
$python = "python"
& $python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
& $python -m unittest discover -s tests -v
& $python -m unittest discover -s tests/acceptance -v
& $python -m pytest --cov=src --cov-branch --cov-fail-under=85
& $python -m ruff check .
& $python -m mypy src
```

还应检查 CI workflow、任务台账、架构文档、ADR、接口 schema 和 operations runbook 是否与
本文所述一致。

## 12. 可直接交给网页版 GPT 的验收提示词

```text
你是独立的软件架构和量化交易系统审查者。你无法访问开发者本机，也不要假设你能打开
任何本地路径。请只根据本文提供的自包含证据完成审查。

请输出：
1. 对架构一致性的判断；
2. 对“已实现”“离线已验证”“外部未验证”三者边界是否清楚的判断；
3. 你认为可能被夸大的陈述；
4. 最重要的五个安全或可靠性风险；
5. 在目标机和 Binance Testnet 上必须补做的验收清单；
6. 最终阶段结论：通过、附条件通过或不通过；
7. 是否允许生产或实盘，并说明理由。

不要因为 357 个测试通过或 86.19% 分支覆盖率就推断生产就绪。特别审查订单未知状态、
风控不可绕过、时钟健康、凭证管理、操作认证、审计失败、目标主机 soak 和部署 mTLS。
若某项结论需要源码才能验证，请明确标为“本文证据不足”，不要虚构已经读取源码。
```

## 13. 最终声明

本报告的目的不是把未完成的外部门禁包装成“开发完成”，而是提供一条清晰边界：

- 仓库内的模块实现和离线证据已经形成稳定基线；
- 设计与实现的主要偏差已显式列出；
- Phase 4 仍在进行；
- 下一阶段工作是取得外部环境证据，而不是继续宣称更多离线完成度；
- 在外部门禁关闭以前，任何生产或实盘批准都应被拒绝。
