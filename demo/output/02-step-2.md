# Security Gates for AI Release Reviewer Pilot

Agent: `security`

## Summary Bullets

- Pilot approval is conditional on strict prompt/data redaction, tenant isolation guarantees, and removal of raw prompts/responses from generic telemetry.
- Raw cardholder data exposure and cross-tenant leakage are explicit blockers until proven impossible via instrumentation.
- Manual override paths (GitHub/Slack) currently represent the highest authz and abuse risk and require tightening before rollout.
- Vendor LLM usage must be constrained to EU/non-EU processing paths with contractual and technical enforcement.

## Notes

## Decision
**Conditional approval only**. The pilot may proceed **only if all REQUIRED controls below are implemented before any production change-management integration**. Items marked **BLOCKER** must be closed; otherwise, the pilot must not touch production.

---

## Security Control Matrix (Pilot Preconditions)

### 1. Data Classes & Prompt Inputs
| Area | Risk | Required Control | Status | Notes |
|---|---|---|---|---|
| GitHub diffs | Leakage of secrets, PCI data, credentials into prompts | **BLOCKER**: Pre-prompt static scanning to classify data (code, config, secrets, PII, PCI). Reject or redact before prompt assembly. | Required | Use regex + entropy-based secret detection; treat matches as deny-by-default. |
| Code snippets in prompts | Overexposure of sensitive logic or data | Define **snippet budget** (e.g., ≤200 LOC, context-window slicing) + structural redaction (comments, string literals, config blocks). | Required | No full-file prompts. |
| Jira summaries | Prompt injection / data poisoning | Strip markup, links, and user-generated instructions; enforce allowlist of fields. | Required | Jira text is untrusted input. |
| Rollout outcomes | Cross-tenant leakage | Tag with tenant_id and service_id; validate at ingest. | Required | Hard-fail on missing tags. |

**Measurement required:** log counts of redacted vs rejected snippets; prove zero raw secret tokens entering prompt builder.

---

### 2. Redaction Policy (Code & Text)
**Mandatory policy before pilot:**
- Remove or mask:
  - Secrets (API keys, tokens, certs, private keys)
  - Cardholder data (PAN, CVV, expiry) **→ BLOCKER if detection not provable**
  - Environment variables and config files by default
- Transformations:
  - String literals → `"<REDACTED_STRING>"`
  - Numeric literals > 6 digits → `<REDACTED_NUM>`
  - Comments removed unless explicitly allowlisted
- Maintain a **redaction map** stored separately for audit (never sent to LLM)

**BLOCKER:** No prompts may include raw payment-processing code paths without documented redaction coverage.

---

### 3. Tenant Isolation & EU Data Separation
| Area | Risk | Required Control |
|---|---|---|
| Tenant isolation | Cross-tenant data leakage | Enforce tenant_id at API boundary + per-tenant encryption keys; add runtime assertions. |
| EU processing | Regulatory breach | **BLOCKER**: EU tenant data must route to EU-only LLM endpoints, storage, and tracing. |
| Storage | Data mixing | Separate physical storage buckets/indexes for EU vs non-EU traces. |

**Measurement required:** automated test that attempts cross-tenant prompt assembly and must fail.

---

### 4. Authz Boundaries (GitHub / Slack / Overrides)
| Surface | Risk | Required Control |
|---|---|---|
| GitHub checks | Privilege escalation | Restrict reviewer status changes to GitHub App with least-privilege scopes. |
| Manual override | Abuse / bypass | Overrides require dual-control: (a) authorized role + (b) justification captured immutably. |
| Slack commands | Spoofing | Verify request signatures; restrict to private channels; map Slack user → corporate identity. |
| After-hours hotfix | Undefined ownership | **BLOCKER**: Name on-call owner + escalation path before pilot. |

---

### 5. Prompt Injection & Model Manipulation
- Treat **all inputs as untrusted**, including code comments and Jira text.
- Enforce system prompt immutability; no concatenation with user text.
- Add post-model validation layer: model output cannot directly block releases without deterministic rule confirmation.
- Maintain allowlist of output actions (block / warn / pass only).

**Measurement required:** red-team at least 10 prompt-injection attempts on pilot services.

---

### 6. Logging, Tracing & Retention
| Area | Risk | Required Control |
|---|---|---|
| Prompt/response logging | Sensitive data exfiltration | **BLOCKER**: Remove from generic telemetry sinks immediately. |
| Review traces | Over-retention | Store redacted traces only; 30-day TTL enforced by storage policy. |
| Debug logs | Accidental leakage | Structured logs with field-level allowlist; no free-text dumps. |

---

### 7. Secrets & Token Handling
- LLM API keys stored in HSM-backed secret manager.
- Per-environment keys (dev/stage/prod); no shared tokens.
- GitHub/Slack tokens scoped minimally; rotate every 30 days.
- **No secrets ever injected into prompts** (assert and alarm if detected).

---

### 8. Vendor Dependency Exposure (LLM Provider)
| Risk | Required Control |
|---|---|
| Data reuse by vendor | Contractual opt-out of training on prompts/responses. |
| Regional processing | EU-only endpoints for EU tenants. |
| Outage / latency | Fallback to advisory mode within <5 minutes (config flag, not redeploy). |
| Lock-in | Abstract provider behind interface; no provider-specific prompt features in pilot. |

---

## Explicit Pilot Blockers
The pilot **must not proceed** if any of the following cannot be ruled out:
1. Raw cardholder data entering prompts or traces.
2. Cross-tenant or EU↔non-EU data mixing in processing or storage.
3. Prompt/response payloads flowing into generic analytics or telemetry sinks.
4. Uncontrolled manual overrides without auditable identity and justification.

---

## Final Recommendation
Approve the pilot **only after** the above blockers are closed and instrumentation proves compliance. Given team size (2 platform + 1 security), de-scope features if needed (e.g., Slack overrides) rather than weakening controls.
