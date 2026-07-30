# Trading Kernel v1 Freeze

Status: active compatibility freeze.

Effective date: 2026-07-30.

Planning baseline: `d1e24c0c89e8cf0a2addaf6e843b969c230da5e2`.

External execution authorization: none.

## Purpose

ADR-009 through ADR-014 have established and exercised the platform kernel:

```text
ADR-009  coherent decision evidence
ADR-010  generic N-leg economic intent
ADR-011  durable grouped execution control
ADR-012  portfolio risk authorization
ADR-013  financial ledger and PnL attribution
ADR-014  first application boundary
```

The project now changes priority from speculative kernel expansion to closing
the first research, simulation, Testnet and Accounting loop. Kernel public
contracts are therefore compatibility-frozen as `Kernel v1`.

ADR-013 remains approved in principle with its offline implementation complete
under project-owner authority. Its implemented public interfaces are included
in this compatibility freeze, while its final Web GPT acceptance remains a
separate documentation gate.

## Frozen Ownership

| Domain | Owns | Must not own |
|---|---|---|
| Snapshot | source coherence, freshness and publication identity | market, application or execution state |
| Strategy | generic single-leg and Basket economic intent | orders, permits or venue I/O |
| OMS | order/group execution control and execution facts | application success, hedge or PnL |
| Portfolio Risk | projection, reservations, approval and permits | execution sequencing or application lifecycle |
| Portfolio | account, balance, margin and effective position truth | strategy policy or ledger history |
| Accounting | financial facts, balanced ledger, reconciliation and PnL views | expected Funding or strategy decisions |
| Application | economic policy and family-specific state | platform authority or venue I/O |
| Execution | venue protocol mapping and external side effects | canonical order or portfolio truth |
| Runtime | ordered composition of existing authority boundaries | new domain truth |

## Frozen Public Semantics

The following semantics cannot change merely to simplify one application:

- every exposure-changing decision references exact coherent evidence;
- Basket intents contain absolute economic targets, not order instructions;
- Risk approval and one-action execution permission are distinct;
- durable action/permit consumption and child submission state precede
  external I/O;
- UNKNOWN is not failure and cannot be blindly retried;
- OMS fills do not replace Portfolio effective positions;
- expected Funding and marks do not replace authenticated Accounting facts;
- application hedge/lifecycle state does not enter OMS or Portfolio Risk;
- venue-native payloads do not cross adapter boundaries;
- restart replay must preserve identity and fail closed on conflict.

## Allowed Changes

During the freeze, kernel changes require a concrete defect or measured need.
Allowed work:

- correctness, security, durability and recovery fixes;
- backward-compatible validation tightening for an identified unsafe case;
- performance improvements with unchanged public behavior;
- observability and evidence additions that do not create new authority;
- new adapters implementing existing public protocols;
- compatibility shims and migrations required by a proven integration defect;
- documentation and test improvements.

## Prohibited Changes

Without a real scenario, recorded evidence and explicit change approval, do
not:

- add Funding fields or branches to OMS;
- add CTA fields or branches to Portfolio Risk;
- add Market Making quote state to Portfolio;
- add application lifecycle to generic Basket or Order Group contracts;
- let Accounting infer settlement from market rates;
- create one universal `ApplicationState` or application journal;
- make Carry position/lifecycle mandatory for other application families;
- move existing packages solely to match a speculative target directory;
- introduce ADR-015 merely to add unexercised kernel capability.

## Application Independence

Applications share public protocols, not mutable state models:

```text
applications/carry/          Carry position and lifecycle
applications/cta/            CTA-specific state
applications/market_making/  quote session and inventory state
```

Carry is the first application-level validation, not a base class for all
future applications.

## Change-Control Trigger

A frozen contract may be reconsidered only when all of the following exist:

1. a reproducible strategy/runtime scenario;
2. evidence that the issue cannot be solved behind the current interface;
3. affected ownership and replay compatibility analysis;
4. migration and rollback plan;
5. regression/acceptance cases proving the defect and proposed behavior;
6. explicit project-owner approval for a breaking change.

The preferred response is an adapter, composition or application-layer change.
An ADR amendment is a last resort, not the default development mechanism.

## Physical Package Stability

`cex_quant.runtime` is the current composition root. The project may describe
a conceptual platform layer, but it will not move existing packages into
`cex_quant.platform.runtime` during the freeze. A future `cex_quant.platform`
package may provide a stable user-facing facade without relocating domain
implementations.

## Exit

The compatibility freeze remains active through the fast-track live gates:

- A018 offline Execution Promotion;
- A019 separately authorized Testnet acceptance;
- T050 Live Operations/Shadow readiness;
- A020 live-readiness acceptance;
- A021 separately authorized controlled micro-live acceptance.

T047 Application Runtime/SDK Lite, T048 Replay and T049 Paper Exchange remain
inside the freeze policy but are deferred until after the MVP.

Real integration evidence may produce narrowly scoped amendments. The freeze
does not imply that production readiness or external execution is complete.
