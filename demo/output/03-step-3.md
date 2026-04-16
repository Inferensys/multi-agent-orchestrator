# AI Release Reviewer Pilot – Production Readiness Assessment (Step 3)

Agent: `operations`

## Summary Bullets

- Pilot is conditionally approvable only if explicit latency budgets, backpressure, and rollback controls are implemented before enabling blocking mode.
- Current design lacks evidence for meeting 12s P95 at peak; load test and queue instrumentation are mandatory pre-pilot gates.
- Observability and audit plans are insufficient for 30-day traceability and incident response; require dedicated sinks and redaction.
- Ownership gap for after-hours hotfix blocking must be closed with an on-call and override SLA.

## Notes

## Decision
**Status: Conditional Approval for Pilot (Advisory Mode First).**

Blocking mode **must not** be enabled until the controls and measurements below are implemented and validated. Advisory-only mode may proceed for week 1 to gather latency, false-positive, and volume data.

---

## 1. SLOs and Latency Budget

### Target SLOs (Pilot)
- **End-to-end review latency**: P95 ≤ **12s**, P99 ≤ 20s
- **Availability**: 99.5% during business hours
- **Incorrect block rate** (manual override within 24h): ≤ 3%

### Required Latency Budget (must be enforced and measured)
| Stage | Budget (P95) |
|---|---|
| GitHub webhook ingestion + auth | 1.0s |
| Data fetch (diffs, Jira, rollout metadata) | 3.0s |
| Prompt assembly + redaction | 1.0s |
| Model inference (per request) | 5.0s |
| Post-processing + rule evaluation | 1.0s |
| Write audit trace + respond | 1.0s |
| **Total** | **12.0s** |

**Gaps:**
- No evidence of model inference latency under concurrent load.
- No definition of timeout behavior per stage.

**Required before blocking mode:**
- Load test at **2× expected peak** (≈30 PRs/hour burst) with synthetic PRs.
- Enforce per-stage timeouts; model inference must hard-timeout at **6s** and fail open (advisory) rather than block.

---

## 2. Retries, Backpressure, and Failure Modes

### Retry Policy
- **External fetches (GitHub/Jira):** max 2 retries, exponential backoff, total ≤ 2s.
- **Model calls:** **no retries** in blocking path; retry only in advisory mode async path.

### Backpressure Controls
- Introduce a **bounded work queue** (size = 2× peak hourly volume).
- When queue is saturated:
  - Automatically downgrade to **advisory-only**.
  - Emit `reviewer.backpressure.engaged` metric.

### Failure Behavior (must be explicit)
| Failure | Behavior |
|---|---|
| Reviewer timeout | Allow PR, mark as `review_skipped_timeout` |
| Model error | Allow PR, advisory comment only |
| Rule engine error | Block **only** if deterministic safety rule fired; otherwise allow |

---

## 3. Observability, Audit, and Data Retention (30 Days)

### Required Telemetry (Dedicated, Not Shared)
- **Metrics** (tagged by service, tenant, region):
  - `review.latency.p50/p95/p99`
  - `review.queue.depth`
  - `review.blocked.count`
  - `review.manual_override.count`
  - `review.fail_open.count`
- **Structured logs** (JSON): decision, rule IDs, model score bands (not raw logits).
- **Traces**: end-to-end trace ID propagated to GitHub comment.

### Audit Storage
- Store review traces in a **separate, access-controlled audit sink**.
- Retention: **30 days**, immutable.
- **Do not co-mingle** prompt/response payloads with generic app telemetry.

### Redaction (Blocking Issue)
- Define and implement a **code snippet redaction policy**:
  - Strip secrets, credentials, card-like patterns.
  - Hash file paths + function names for model input when possible.
- EU tenants: enforce **region-locked processing and storage**, verified via deployment config and tests.

---

## 4. Rollout, Rollback, and Safety Mechanisms

### Rollout Plan
- Week 1: Advisory-only for all pilot services.
- Week 2: Blocking enabled for **payments-ledger only**, business hours.
- Week 3–4: Expand if SLOs met.

### Rollback Requirements (Hard Gate)
- Global config flag to switch **blocking → advisory** in < **5 minutes**.
- Rollback must not require redeploy.
- Rollback drill must be executed once before pilot start.

### Safe Defaults
- Any config or dependency failure defaults to **advisory**.

---

## 5. Manual Override Workflow

### GitHub
- `/release-override reason=<text>` comment by users in `platform-release-approvers`.
- Override action must:
  - Unblock PR immediately.
  - Log override reason + actor to audit sink.

### Slack
- `#release-ops` slash command: `/override <PR-link> <reason>`
- Bot validates caller permissions and posts confirmation back to PR.

### SLA
- Override must take effect in **<60 seconds**.

---

## 6. Incident Response and Ownership (Blocking Issue)

### Ownership Model
- **Named Service Owner Required** before blocking mode.
- After-hours coverage:
  - Primary: Platform Engineer on-call.
  - Secondary: Security Engineer.

### Incident Classes
| Scenario | Pager? |
|---|---|
| Hotfix blocked in prod incident | **Yes (P1)** |
| Reviewer outage causing delays | P2 |

### Runbooks (Required)
- Hotfix blocked incorrectly
- Reviewer latency regression
- Model degradation / spike in false positives

---

## 7. Handoff Criteria: Experiment → Service

Blocking mode may graduate to owned service only if:
- 2 consecutive weeks meeting latency SLOs.
- Incorrect block rate ≤ 3%.
- On-call rotation documented and accepted.
- Security sign-off on redaction + EU isolation.
- Offline eval set defined and reviewed for infra-only changes.

---

## Final Recommendation
Proceed with **advisory-only pilot immediately**. Enabling blocking mode without the above controls presents unacceptable operational and incident risk. Approval to block production changes is contingent on closing the identified gaps and demonstrating measured compliance.
