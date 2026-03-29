+++
title = "Projects"
+++

Our code and artefacts are available on [GitHub](https://github.com/VCA-EPFL). Here are some of our main projects that involve artifact code.

## Graphiti

Formally verified graph rewriting for dataflow circuits. Graphiti uses the Lean theorem prover to verify that out-of-order execution transformations in dataflow circuits preserve program semantics. Published at ASPLOS '26.

- [Source code (Lean)](https://github.com/VCA-EPFL/graphiti)

## FSA — SystolicAttention

A hardware architecture that fuses FlashAttention within a single systolic array, eliminating off-chip memory traffic for attention computation. The design is implemented in Chisel/Scala with an FPGA prototype.

- [Source code (Scala)](https://github.com/VCA-EPFL/FSA)
- [FPGA integration (Chipyard)](https://github.com/VCA-EPFL/chipyard-fsa)

## Lean Tooling

In the future we might develop and maintain libraries for the Lean theorem prover used across our verification projects:

- [leanses](https://github.com/VCA-EPFL/leanses) — Lean lens implementation with custom notation
