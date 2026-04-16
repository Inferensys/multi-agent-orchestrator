# Decision

**Approve a four-week pilot in advisory-only mode. Do not approve enforced blocking of production changes yet.**

The AI release reviewer may analyze PRs for the three pilot services and post advisory output, provided the team implements the mandatory controls below before production change-management integration. Blocking behavior stays disabled until the board receives evidence that security boundaries hold, false positives are acceptably low, and there is named operational ownership for hotfix and after-hours incidents.

# Why This Design Holds

- **Correct boundary between rules and AI.** Deterministic controls remain outside the model for compliance, required artifacts, freeze windows, and known unsafe patterns. The model contributes only risk signals and rationale.
- **Separable outputs.** The design cleanly distinguishes `deterministic_failures` from `model_concerns`, which is required for auditability and operator trust.
- **Safe rollback path exists.** A runtime feature flag can switch blocking to advisory in under 5 minutes without redeploy.
- **Pilot scope is appropriately narrow.** Three services, synchronous flow, and minimal architecture fit the available staffing.
- **Fail-open behavior is appropriate for pilot.** Model timeouts, reviewer outages, and dependency failures default to advisory/pass rather than blocking releases.

# Risks That Block A Wider Rollout

The following are **hard blockers** for any move beyond advisory mode:

1. **No redaction policy for code snippets and prompt inputs**
   - The brief mentions code snippets but does not define what may be sent, what must be masked, or how secrets/PCI patterns are prevented from entering prompts.

2. **Unsafe logging design**
   - Prompt and response payloads cannot share the generic application telemetry sink. This is a direct data exposure risk.

3. **EU and tenant isolation not yet proven**
   - EU tenants require separate processing and storage paths. Cross-tenant or cross-region prompt assembly must be impossible by design and test.

4. **No offline evaluation set for false positives**
   - There is no evidence that the reviewer can avoid over-flagging safe infrastructure, config-only, and dependency changes.

5. **No named after-hours owner for hotfix blocking**
   - A release gate without a staffed incident path is not production-ready.

6. **Override path needs tighter control**
   - Manual override must be identity-bound, justified, auditable, and restricted to authorized roles.

# Instrumentation And Guardrails

These controls are **mandatory before the pilot touches production change management**, even in advisory mode where applicable.

## Architecture and decision controls
- Deterministic rules run before any model call.
- Model output cannot directly block releases.
- Response schema must keep deterministic failures and model concerns separate.
- Global feature flag must switch blocking to advisory in **<5 minutes**.
- Any dependency or reviewer failure defaults to advisory/pass.

## Data handling and security controls
- Implement pre-prompt scanning for secrets, PII, and PCI patterns.
- Define a prompt redaction policy:
  - no full-file prompts
  - max snippet budget
  - strip comments, config blocks, string literals, and long numeric literals by default
- Block any raw cardholder data from prompts or traces.
- Route EU tenant data through EU-only processing, storage, and tracing.
- Use a dedicated, access-controlled trace store with **30-day TTL**.
- Remove prompt/response payloads from generic telemetry immediately.
- Enforce least-privilege auth for GitHub and Slack integrations.
- Require override justification and immutable audit logging.

## Operational controls
- Week 1 must be advisory-only for all pilot services.
- Per-stage timeouts must enforce the **12s P95** budget; model call hard-timeout at 6s.
- Load test at **2x expected peak** before considering any blocking mode.
- Run a rollback drill before launch.
- Name an on-call owner and escalation path for reviewer-caused hotfix delays.
- Override action must complete in **<60 seconds**.

## Evaluation controls
- Build an offline set of at least **500 historical PRs** across the pilot services.
- Measure false positives specifically on:
  - infra-only changes
  - config-only changes
  - dependency bumps
  - feature-flag flips
- Blocking eligibility after pilot requires, at minimum:
  - **≤5% false positives** on safe infra/config changes
  - **≥90% precision** on deterministic rule triggers
  - **≤3% incorrect block rate**
  - two consecutive weeks meeting latency SLOs

# Next 2 Engineering Moves

1. **Close the data-safety gaps first**
   - Ship the redaction spec and tests.
   - Move traces to a dedicated audit store.
   - remove prompt/response payloads from generic telemetry.
   - validate tenant and EU path separation with automated tests.

2. **Stand up the evidence and operating model**
   - Create the 500-PR offline eval set and baseline false-positive rates.
   - Name the on-call owner, publish the hotfix override runbook, and execute a rollback drill before pilot start.

**Board position:** proceed with the pilot now, but only as an advisory reviewer under the controls above. Revisit blocking approval after week 4 with security validation, latency data, and false-positive evidence.
