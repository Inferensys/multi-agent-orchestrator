# AI Release Reviewer Pilot — Approval Memo (Step 4)

Agent: `evals`

## Summary Bullets

- Recommendation: Approve four-week pilot in **advisory-only mode** with mandatory controls; do not allow enforced blocking yet.
- Primary risk is false positives on safe infra changes and hotfixes; offline evidence is currently missing.
- Security and data-handling gaps (prompt redaction, logging sink separation, EU path validation) must be closed before any blocking.
- Clear success/failure thresholds and rollback guardrails are defined; exceeding failure thresholds auto-disables the pilot.

## Notes

## 1. Approval Recommendation

**Decision:** ✅ **Approve pilot in advisory-only mode with conditions.**  
**Not approved for enforced blocking** until missing evidence and controls are satisfied.

**Rationale:**
- The system intent is sound, but there is **no offline evidence quantifying false positives**, especially for safe infrastructure and configuration-only changes.
- Security controls around **prompt redaction, logging segregation, and EU data paths** are underspecified.
- Operational ownership for hotfix blocking and after-hours incidents is not defined.

---
## 2. Acceptance Criteria (Pilot Scorecard)

### 2.1 Functional Acceptance (Must-Have for Pilot)
| Area | Criteria | Threshold |
|---|---|---|
| Latency | P95 end-to-end review time | ≤ 12s |
| Explainability | Every advisory/block includes human-readable rationale | 100% |
| Output Separation | Deterministic rule failures vs model-derived concerns | 100% |
| Override | Manual override via GitHub + Slack | Functional in prod |
| Traceability | Review trace stored | 30 days retention |

### 2.2 Quality Acceptance (Pilot Success Metrics)
| Metric | Target | Failure Threshold |
|---|---|---|
| False positive rate (safe changes) | ≤ 5% | >10% (pilot fail) |
| False negatives on known-dangerous patterns | ≤ 5% | >10% |
| Reviewer disagreement with human reviewers | ≤ 20% | >30% |
| Advisory usefulness (RM survey) | ≥ 4/5 avg | <3/5 |

*Safe changes explicitly include: dependency bumps, IaC refactors, config-only changes, feature-flag flips.*

---
## 3. Failure Taxonomy (Blocking vs Advisory)

### 3.1 Deterministic Rule Failures (Eligible for Blocking **after pilot**)
- Secrets detected in diff (keys, tokens, certs)
- PCI/PII access expansion without ticket linkage
- Direct prod config edits bypassing deployment tooling
- Rollback-disabled changes to payments or ledger write paths

### 3.2 Model-Derived Concerns (Advisory Only)
- Ambiguous data migration safety
- Incomplete test coverage signals
- Cross-service behavior changes inferred from diff
- Risk inferred from prior rollout outcomes

### 3.3 Pilot-Time Policy
- **No model-derived concern may block** during pilot.
- Deterministic rules run in **shadow-block mode** only (log + alert).

---
## 4. Offline Evaluation Plan (Required Before Blocking Approval)

### 4.1 Datasets (Missing Today)
- **Minimum 500 historical PRs** across the three pilot services.
- Label each PR with:
  - Safe vs unsafe
  - Infra-only vs application logic
  - Actual incident outcome (if any)

### 4.2 Required Measurements
- False positive rate on *safe infra/config changes*
- Precision/recall on known-bad patterns
- Rationale quality score (human-rated: clear / vague / misleading)

### 4.3 Evidence Gate
- Blocking approval requires:
  - ≤5% false positives on safe infra changes
  - ≥90% precision on deterministic rule triggers

---
## 5. Online Evaluation Plan (Four-Week Pilot)

### 5.1 Instrumentation
- Log per-PR:
  - Decision type (allow/advisory/shadow-block)
  - Trigger category (rule vs model)
  - Human override action
  - Time-to-merge impact

### 5.2 Weekly Review
- Weekly triage with platform + security:
  - Top 10 false positives
  - Any hotfix friction events
  - Latency regressions

### 5.3 Kill Switches
- Auto-disable reviewer if:
  - Advisory rate >40% of PRs
  - P95 latency >15s for 30 mins
  - Any confirmed data boundary violation

Rollback to advisory-only must remain <5 minutes (validated in week 1).

---
## 6. Rollout Guardrails (Pilot)

### 6.1 Security & Data Handling (Blocking Issues)
- **Prompt redaction policy** must be defined and enforced:
  - Strip secrets, cardholder data, auth headers
  - Max 20-line code snippet window
- **Logging segregation:**
  - Prompts/responses must not go to generic telemetry sink
  - Separate, access-controlled audit log
- **EU tenants:**
  - Verified separate processing + storage path
  - Evidence: data-flow diagram + test execution

### 6.2 Operational Controls
- Named **on-call owner** for reviewer-related blocks (incl. after-hours)
- Documented hotfix bypass procedure (≤2 clicks)
- Slack escalation channel monitored 24/5

---
## 7. Missing-Evidence Register (Must Be Closed)

| Gap | Risk | Required Evidence |
|---|---|---|
| No offline FP dataset | High | Labeled PR eval results |
| Undefined redaction | High | Redaction spec + tests |
| Logging sink commingled | Medium | Separate sink deployed |
| EU path unverified | High | Data residency validation |
| No hotfix owner | Medium | Named rotation + SOP |

---
## 8. Final Go / No-Go

**✅ Go for advisory-only pilot** with the guardrails above.  
**❌ No-go for enforced blocking** until:
- Offline false-positive evidence meets thresholds
- Security logging and redaction controls are verified
- EU data handling is validated

**Next decision gate:** End of week 4, with offline + online metrics review and explicit sign-off from Platform, Security, and Release Management.
