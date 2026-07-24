# Initial Tasks

| ID | Task | Status | Depends on |
|---|---|---|---|
| T001 | Project skeleton | Complete | - |
| T002 | Core and instrument schema definitions | Complete | T001 |
| T003 | Binance connector and venue normalizers | Complete | T002, T004 |
| T004 | Market event normalization and validation contracts | Complete | T002 |
| T005 | Market state engine | Complete | T004 |
| T006 | Recorder | Complete | T002 |
| T007A | Online feature engine contracts and deterministic runtime | Complete | T005 |
| T007B | Core option feature calculators and surface contracts | Complete | T007A |
| T008 | Strategy runtime | Complete | T007B |
| T009 | Risk engine | Complete | T008 |
| T010 | OMS | Complete | T009 |
| T011 | Execution gateway | Complete | T010 |
| T012 | Portfolio and account state | Complete | T010 |
| T013 | Runtime pipeline composition | Complete | T005-T012 |
| T014 | Authenticated Binance execution adapter | Complete | T011, T013 |
| T015 | Concrete runtime port adapters and application assembly | Complete | T013-T014 |
| T016 | Durable OMS journal, restart replay and reconciliation kernel | Complete | T010, T015 |
| T017 | Binance order query and private order-event normalization | Complete | T014, T016 |
| T018 | Private order-stream lifecycle and startup reconciliation | Complete | T017 |
| T019 | Binance environment configuration and private-stream application supervision | Complete | T018 |
| A001 | Offline foundation scenario acceptance | Complete | T001-T014 |
| A002A | Offline performance and bounded-memory baseline | Complete | T015 |
| A002B | Target-host soak and latency acceptance | External | A002A |
| A002C | Binance Testnet authenticated acceptance | External | T017 |
| A003 | Offline OMS restart and reconciliation acceptance | Complete | T016 |
| A004 | Offline Binance recovery-protocol acceptance | Complete | T017 |
| A005 | Offline private-stream startup race acceptance | Complete | T018 |
| A006 | Offline environment and private-stream supervision acceptance | Complete | T019 |

## Current Acceptance Baseline

- Public contracts are immutable and exported explicitly.
- No venue-native payload crosses an adapter boundary.
- Unit tests run offline and deterministic state tests support replay.
- Contract, ownership or schema changes update documentation in the same change.
