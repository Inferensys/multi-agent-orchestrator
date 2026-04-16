# Demo Guide

This demo is easiest to inspect in this order:

1. `input/release-review-brief.md`
   The board brief. Read this first so the outputs have context.

2. `output/execution-plan.json`
   How the planner split the work across architecture, security, operations, and evals.

3. `output/01-step-1.md` to `output/04-step-4.md`
   The parallel specialist passes. Each file is intentionally separate because the whole point is to avoid one blended answer too early.

4. `output/decision-memo.md`
   The board-facing memo that someone could circulate internally.

5. `output/review.json`
   The machine-readable release recommendation and missing threads.

6. `output/execution-events.json`
   Stage timing and completion order.

## What To Look For

- the architecture note keeps deterministic rules outside the model
- the security note treats telemetry and redaction as first-class blockers
- the operations note turns vague “production readiness” language into budgets and rollback behavior
- the eval note turns approval into measurable gates
- the final memo compresses those into one position without losing the blockers

## Regenerating The Demo

```bash
uv run python scripts/run_live_demo.py
```
