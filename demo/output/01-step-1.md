# ADR: AI Release Reviewer Pilot – Architecture and Control Points

Agent: `architecture`

## Summary Bullets

- Approve a tightly-scoped pilot only if blocking is gated behind a deterministic policy engine with a 5-minute global kill-switch.
- Keep all deterministic rules (compliance, ownership, change windows) outside the model; the model provides advisory risk signals only.
- Minimize services: one stateless reviewer API, one deterministic policy service, existing GitHub/Jira integrations reused.
- Explicitly separate EU vs non-EU ingestion, storage, and model endpoints; no shared queues or analytics sinks.
- Hidden coupling risks exist with Jira workflow states, rollout-history freshness, and GitHub branch protection—must be instrumented.
- Do not log raw prompts/responses into generic telemetry; create a dedicated, access-controlled review trace store.

## Notes

## 1. System Context & End-to-End Flow

**Actors & Systems**
- GitHub (PRs, branch protection, checks API)
- Jira (ticket summaries, status)
- Deployment metadata source (env flags, service name)
- Rollout history store (last outcome per service/env)
- AI Release Reviewer (new)
- Deterministic Policy Engine (new or existing rules service)
- Slack (override + notifications)

**Happy Path (Blocking Enabled)**
1. PR opened / updated → GitHub webhook.
2. Reviewer Orchestrator fetches metadata (diff stats only, no raw secrets).
3. Deterministic Policy Engine runs first:
   - Missing Jira
   - Change window violations
   - Service ownership / approvals
   - Known forbidden patterns
4. If deterministic fail → **hard block** with rule ID + message (no model call).
5. If deterministic pass → Model Analysis Service called with redacted context.
6. Model returns risk signals + rationale.
7. Orchestrator maps signals to decision (block / manual approval / pass).
8. GitHub Check updated; Slack notification sent if blocked or manual review required.
9. Review trace persisted (30 days).

**Advisory Mode**
- Steps 1–6 same.
- Steps 7–8 always result in pass + advisory comment.

## 2. Service Boundaries & State Ownership

**Reviewer Orchestrator (Stateless)**
- Owns request orchestration and timeout enforcement.
- No durable state.

**Deterministic Policy Engine (State Owner for Rules)**
- Owns rule definitions, versions, and outcomes.
- Deterministic, testable, auditable.
- Must be deployable/disableable independently of model code.

**Model Analysis Service**
- Stateless inference only.
- No authority to block directly.
- Receives only redacted, pre-approved fields.

**Review Trace Store**
- Owns 30-day retention data.
- Separate from general telemetry.
- Partitioned by tenant and region (EU/non-EU).

**Hidden Coupling to Call Out**
- Jira workflow states: assumptions about “Ready for Release” must be explicit and versioned.
- Rollout history freshness: stale data can bias model; instrument data age.
- GitHub branch protection: reviewer check becomes a production gate—treat changes as change-management events themselves.

## 3. Deterministic vs Model-Based Boundary

**Must Remain Deterministic (Outside Model)**
- Compliance constraints (tenant isolation, EU routing).
- Required artifacts present (Jira link, approvals).
- Known unsafe flags (e.g., disabling auth, skipping migrations).
- Change window / freeze enforcement.

**Model Responsibilities (Advisory Signals Only)**
- Risk classification of diff complexity.
- Correlation with past rollout failures.
- Natural-language rationale for *why* something looks risky.

**Output Separation**
- Response schema:
  - `deterministic_failures[]`
  - `model_concerns[]`
- UI and APIs must never merge these lists.

## 4. Fallback, Override, and Fast Rollback Design

**5-Minute Rollback Requirement**
- Single config flag (e.g., in feature flag service) controlling blocking vs advisory.
- Flag checked at decision time, not deploy time.
- No redeploy required to switch modes.

**Failure Modes & Fallbacks**
- Model timeout/error → default to advisory + warning.
- Jira/GitHub API failure → deterministic fail only if required artifact cannot be verified; otherwise advisory.
- Reviewer service down → GitHub check auto-passes with banner.

**Manual Override**
- GitHub: authorized label (`override/release-reviewer`) bypasses block.
- Slack: slash command posts override event + reason.
- All overrides logged with actor + timestamp.

## 5. Tenant & EU Path Separation Assumptions

- Separate queues, model endpoints, and storage for EU tenants.
- No cross-region prompt caching.
- Deterministic policy code may be shared, but config and data are region-scoped.
- Measure and alert on any cross-region call attempts.

## 6. Minimal Pilot Design (Operational Simplicity)

**Keep It Small**
- One orchestrator service.
- Reuse existing rules engine if available; otherwise minimal new service.
- No asynchronous pipelines; synchronous request/response within 12s P95.

**What to Defer**
- Advanced prompt experimentation.
- Automated retraining.
- Cross-service learning.

## 7. Controls Required Before Production Touch

**Mandatory Before Approval**
- Redaction policy for diffs (define allowed fields, max lines).
- Named on-call owner for after-hours blocks.
- Dedicated review trace store (not generic telemetry).
- Instrumentation for:
  - Deterministic vs model block rates.
  - Override frequency.
  - Data freshness for rollout history.
- Offline eval set for at least one pilot service (measure false positives).

**Decision**
- **Conditional approval** for pilot *only* in advisory mode by default, with blocking enabled via feature flag after controls above are in place.
