# Architecture

This repo does not model a free-form swarm.

It implements a fixed review graph:

1. planner creates an execution plan
2. specialists run in parallel against the same brief
3. synthesizer writes a single decision memo
4. reviewer grades the memo and flags missing threads

The important design choice is that graph control stays local:

- allowed specialist roles are defined in code
- concurrency limits are local
- fallback plan generation is local
- artifact ordering is local
- review output shape is validated locally

Only the content of each stage is delegated to the model.
