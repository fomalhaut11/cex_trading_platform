# CEX Quant Trading System Architecture

## Scope

This document defines the production CEX quantitative trading system.

Research platform is separated and only publishes approved artifacts.

## Core Runtime Flow

Exchange → Market Data Gateway → Normalizer → Validator → Market State
Engine → Online Feature Engine → Strategy Runtime → Risk Engine → OMS →
Execution Gateway → Exchange

## Design Principles

-   Python-first, Rust-ready
-   Event, State and Storage separation
-   Real-time trading path separated from research
-   Metadata-driven governance
-   Registered features only in production

## Runtime Domains

1.  Market Data Domain
2.  State Domain
3.  Information Domain
4.  Decision Domain
5.  Execution Domain
