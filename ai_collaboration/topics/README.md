# Topic Bundles

每个子目录代表一个独立讨论主题。一次性主题使用
`YYYY-MM-DD_short-kebab-topic`；长期迭代的领域主题可以使用稳定 ASCII snake_case，
例如 `funding_arbitrage`。

推荐文件顺序：

```text
00_context.md
10_web_gpt_input.md
20_codex_response.md
30_web_gpt_review.md
90_resolution.md
```

创建主题时，从 `../templates/` 复制所需模板并更新 `../INDEX.md`。不要在这里保存凭证，
也不要把未复核的 AI 结论直接视为项目设计。
