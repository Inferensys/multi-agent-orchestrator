# multi-agent-orchestrator

This repo is built around one workflow:

take a technical launch brief, run parallel review passes for architecture, security, operations, and evals, then produce a board memo plus a machine-readable recommendation.

The checked scenario in this repo is an internal review for an **AI release reviewer** that would inspect pull requests before production deployment.

## Open These First

- `demo/input/release-review-brief.md`
- `demo/output/decision-memo.md`
- `demo/output/review.json`
- `demo/output/execution-plan.json`

If those four files make sense, the code will make sense.

## The Scenario In This Repo

The brief asks a release board a concrete question:

should a platform team approve a four-week pilot for an AI reviewer that looks at GitHub PRs, Jira context, rollout history, and deployment metadata before production release?

The answer from the checked run is not “AI is great” or “multi-agent systems are powerful.” The answer is narrower:

- approve advisory-only pilot
- do not approve enforced blocking yet
- close redaction, telemetry, EU routing, eval, and hotfix ownership gaps first

This is the kind of review where a single free-form assistant tends to blur too many concerns together. The point of the orchestrator is to keep the outputs separated long enough to be useful.

## What The Run Produced

The live run generated:

- a review plan in `demo/output/execution-plan.json`
- four specialist artifacts in `demo/output/01-step-1.md` through `demo/output/04-step-4.md`
- a board memo in `demo/output/decision-memo.md`
- a scored review in `demo/output/review.json`
- an event trace in `demo/output/execution-events.json`

Rendered captures:

![Run summary](assets/run-summary-card.svg)
![Review result](assets/review-card.svg)

Summary from `demo/output/run-summary.json`:

```json
{
  "fallback_used": false,
  "steps": 4,
  "artifacts": 4,
  "total_tokens": 23446,
  "recommendation": "needs-work",
  "coverage_score": 90
}
```

The most important checked output is the board memo:

```md
**Approve a four-week pilot in advisory-only mode. Do not approve enforced blocking of production changes yet.**
```

The most important machine-readable output is the review:

```json
{
  "release_recommendation": "needs-work",
  "findings": [
    {
      "severity": "high",
      "title": "Prompt redaction and sensitive data handling remain undefined"
    }
  ]
}
```

## Why The Graph Is Fixed

This project does not expose a generic agent bus.

It runs a fixed board review:

1. planner writes the work split
2. specialists run in parallel
3. synthesizer writes one memo
4. reviewer scores whether the memo is actually board-ready

The following controls stay local:

- allowed specialist roles
- plan validation
- concurrency limit
- fallback plan when the planner output is invalid
- artifact ordering
- review schema

The model writes content. The application keeps control of the review process.

## Run The Exact Scenario

Install:

```bash
uv sync --extra dev
```

Set Azure variables:

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export AZURE_OPENAI_API_KEY="<key>"
export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
export MULTI_AGENT_PLANNER_DEPLOYMENT="gpt-5.4"
export MULTI_AGENT_SPECIALIST_DEPLOYMENT="gpt-5.2-chat"
export MULTI_AGENT_SYNTHESIZER_DEPLOYMENT="gpt-5.4"
export MULTI_AGENT_REVIEWER_DEPLOYMENT="gpt-5.4"
```

Run the checked brief:

```bash
uv run python scripts/run_live_demo.py
```

That will regenerate the files in `demo/output/`.

## Run It On Another Board Brief

```bash
uv run mao-run \
  --brief-file /path/to/brief.md \
  --goal "Decide whether this pilot should be approved and what controls are missing." \
  --out-dir /tmp/review-run
```

The input should be a real review brief, not a prompt toy. Good inputs usually include:

- target system and pilot scope
- hard requirements and SLOs
- known constraints
- open questions
- ownership gaps

## Python Entry Point

```python
from pathlib import Path

from multi_agent_orchestrator import Orchestrator, Settings

brief = Path("demo/input/release-review-brief.md").read_text()

run = Orchestrator(settings=Settings.from_env()).run(
    goal=(
        "Decide whether the platform team should approve a pilot rollout "
        "of the AI release reviewer and define the controls required first."
    ),
    brief_title="release review brief",
    brief_markdown=brief,
)

print(run.review.release_recommendation)
print(run.final_memo_markdown)
```

## Repo Map

- `src/multi_agent_orchestrator/orchestrator.py`
  Execution graph, fallback handling, artifact ordering.

- `src/multi_agent_orchestrator/client.py`
  Azure chat client and JSON-repair pass for structured stages.

- `src/multi_agent_orchestrator/prompts.py`
  Board-specific stage prompts and schemas.

- `demo/README.md`
  Inspection order for the checked run.

- `docs/release-review-playbook.md`
  What this review style is trying to protect.

- `docs/azure-foundry.md`
  Deployment split used for the live run.

## Verify

```bash
uv run pytest -q
uv run python -m compileall src scripts
```
