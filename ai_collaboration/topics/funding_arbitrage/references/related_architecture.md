# Funding Arbitrage — Related Architecture at Baseline

Code baseline: `97d10e33f8d69c2535a542bee9f095aec1c312b9`

This reference maps the review to existing project authorities. It is an index, not a replacement
for the self-contained findings in `20_codex_response.md`.

| Concern | Current authority or implementation | Relevant fact |
|---|---|---|
| Core flow | `architecture/system_architecture.md` | Risk is mandatory; strategy emits venue-neutral intents |
| Module dependencies | `architecture/module_topology.md` | Domain modules cannot depend on runtime; adapters contain venue payloads |
| State ownership | `architecture/state_ownership.md` | Market, feature, strategy, risk, order and account states have single writers |
| Strategy input/output | `src/cex_quant/strategy/model.py` | One event/snapshot input; one-instrument position target intent |
| Multi-scope runtime | `src/cex_quant/strategy/runtime.py` | Explicit accepted scopes exist; caller serializes inputs |
| Runtime order | `src/cex_quant/runtime/pipeline.py` | Each intent is risked, created and submitted sequentially |
| Feature ownership | `src/cex_quant/features/engine.py` | One online engine instance owns one explicit scope |
| Funding event | `src/cex_quant/market_data/events.py` | Canonical funding rate and next funding timestamp exist |
| Market state | `src/cex_quant/market_data/state/` | L1, partial and reconstructed books exist per instrument |
| Portfolio truth | `src/cex_quant/portfolio/` | One account/venue state; immutable balance and position snapshots |
| Risk | `src/cex_quant/risk/` | Independent fail-closed, one-instrument pre-trade evaluation |
| OMS | `src/cex_quant/oms/` | Individual order lifecycle and durable journal |
| OMS assembly | `src/cex_quant/runtime/adapters/oms.py` | One approved target creates one order request |
| Private stream | `src/cex_quant/execution/adapters/binance_private_stream.py` | Current processor normalizes order updates, not account state |
| Portfolio limitations | `development/portfolio_state_design.md` | Margin, MTM and liquidation calculation are explicitly out of scope |

Fixed GitHub root for this baseline:

```text
https://github.com/fomalhaut11/cex_trading_platform/tree/97d10e33f8d69c2535a542bee9f095aec1c312b9
```
