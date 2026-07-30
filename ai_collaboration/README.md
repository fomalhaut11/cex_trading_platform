# AI Collaboration Exchange

这个目录是网页版 GPT、Codex 与项目正式文档之间的交换层。它解决的是讨论成果的传递、
复核和追溯，不是新的架构权威源。

下一位 LLM 应先阅读仓库根目录的 `START_HERE.md`，再按其中的推荐顺序读取
当前任务所需的权威文档。

## 为什么需要单独的交换层

网页版 GPT 不能访问开发机文件，因此每个需要外部阅读的文档必须：

- 单独上传后仍能理解；
- 不依赖本地绝对路径；
- 标明对应的 Git 提交；
- 在正文中包含判断所需的事实，不能只给文件名；
- 不包含 API key、secret、cookie、私钥或未脱敏日志。

项目的最终权威信息仍分别位于：

- 架构和所有权：`architecture/`；
- 正式设计决策：`adr/`；
- 接口契约：`interfaces/`；
- 开发状态和测试证据：`development/`；
- 部署与事故处理：`operations/`；
- 可执行实现：`src/` 与 `tests/`。

AI 讨论只有在完成复核并被明确“晋升”到上述目录后，才成为项目基线。

## 推荐目录结构

```text
ai_collaboration/
  README.md
  INDEX.md
  templates/
    exchange_document.md
    review_response.md
    resolution.md
  topics/
    YYYY-MM-DD_short-topic/ or stable_domain_topic/
      00_context.md
      10_web_gpt_input.md
      20_codex_response.md
      30_web_gpt_review.md
      90_resolution.md
```

文件按实际需要创建，不要求每个主题一开始就有全部五个文件。数字前缀固定阅读顺序，
同一参与者不要覆盖另一参与者的原始输入。

## 状态模型

每份交换文档使用以下状态之一：

```text
DRAFT -> READY_FOR_REVIEW -> REVIEWED -> ACCEPTED -> PROMOTED
                                  \-> REJECTED
                                  \-> SUPERSEDED
```

- `DRAFT`：仍在编写；
- `READY_FOR_REVIEW`：内容完整，可以传给另一 AI；
- `REVIEWED`：已有审查意见，尚未形成项目决议；
- `ACCEPTED`：项目负责人接受结论，但正式文档可能尚未更新；
- `PROMOTED`：结论已写入权威文档或代码，并记录目标提交；
- `REJECTED`：明确不采用；
- `SUPERSEDED`：被更新的交换文档取代。

`ACCEPTED` 不等于“代码已完成”，`PROMOTED` 也不自动等于“生产验收通过”。

## 每个主题的工作流

1. 在 `topics/YYYY-MM-DD_short-topic/` 创建 `00_context.md`，写明问题、范围、代码基线和
   已知约束。预计长期迭代的领域主题可以使用稳定目录名，例如 `funding_arbitrage/`。
2. 将网页版 GPT 的讨论成果整理进 `10_web_gpt_input.md`。不要只粘贴没有上下文的结论。
3. Codex 核对仓库、测试和正式文档，在 `20_codex_response.md` 中逐项回应。
4. 如需二次验收，将自包含材料交给网页版 GPT，并把回复放入 `30_web_gpt_review.md`。
5. 在 `90_resolution.md` 记录采用、拒绝、修改和待办事项。
6. 接受的内容更新到正式目录；在 resolution 和 `INDEX.md` 中记录目标文件及 Git commit。

## 主题生命周期

```text
Discussion
    |
    v
Proposal
    |
    v
Code Verification
    |
    v
Architecture Decision
    |
    v
Implementation
    |
    v
Validation
    |
    v
Production Record
```

文档和正式成果的对应关系：

```text
10_web_gpt_input
    -> 20_codex_response
    -> 30_web_gpt_review
    -> 90_resolution
    -> ADR / architecture / interfaces
    -> code + tests
    -> acceptance evidence
    -> production record
```

任何阶段都可以退回修改。`90_resolution` 未形成明确决议前，不应把讨论自动转成代码任务；
离线验证、Testnet、生产审查和实盘授权仍是彼此独立的门禁。

## 互通链接规则

- 仓库内使用相对 Markdown 链接，避免开发机盘符；
- 对外移交时附带固定 commit 的 GitHub URL，避免 `main` 后续变化造成歧义；
- 如果网页 GPT 无法访问 GitHub，应上传完整 Markdown，而不是只发送 URL；
- 链接是溯源信息，不替代自包含正文；
- 一个事实只在正式文档中维护，AI 交换文档引用它并记录当时基线，避免双份权威内容漂移。

固定链接示例：

```text
https://github.com/fomalhaut11/cex_trading_platform/blob/<commit>/<path>
```

## 文件元数据

所有交换文档开头应包含：

```yaml
---
id: AI-YYYYMMDD-NNN
title: Short title
origin: web-gpt | codex | joint
status: DRAFT
created: YYYY-MM-DD
code_baseline: full-git-sha
supersedes: none
related:
  - relative/path.md
external_share: allowed
sensitivity: public-project | internal | restricted
---
```

如果 `external_share` 不是 `allowed`，不得把内容交给网页版 GPT。任何凭证都禁止进入该
目录，即使文件计划稍后删除。

## 内容边界

适合进入本目录：

- AI 提出的架构方案；
- 对现有实现的审查报告；
- 争议点和备选方案；
- 模块开发交接；
- 测试验收反馈；
- 对正式文档的拟议修改。

不适合进入本目录：

- API key、secret 或登录材料；
- 大段未筛选运行日志；
- 可由测试自动生成的临时输出；
- 已经成为正式基线、却在这里维护第二份可变副本的规范；
- 没有来源和基线的 AI 断言。

## 命名约定

- 一次性主题目录：`YYYY-MM-DD_short-kebab-topic`；
- 长期领域主题目录：稳定的 ASCII snake_case，例如 `funding_arbitrage`；
- 文档 ID：`AI-YYYYMMDD-NNN`；
- 文件名使用小写 ASCII 和下划线；
- 标题和正文可以使用中文；
- 日期使用 UTC 或项目约定时区的 ISO 8601 日期，并在涉及时间点时写明时区。
