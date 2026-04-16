# AI Release Reviewer Pilot

## Context

The platform engineering team wants to launch an internal AI release reviewer that analyzes pull requests before production deployment. The reviewer will ingest:

- GitHub diff metadata
- linked Jira ticket summaries
- deployment environment flags
- last known rollout outcome for the touched service

The system is meant to block obviously unsafe changes and require manual approval for ambiguous ones.

## Pilot Scope

- Pilot services: `payments-ledger`, `payouts-api`, `merchant-webhooks`
- Expected volume: 180 pull requests per weekday
- Target users: platform engineering and release managers
- Rollout window: four weeks

## Requirements

- P95 end-to-end review time below 12 seconds
- Manual override available in GitHub and Slack
- Every blocked release must include a human-readable rationale
- Output must separate deterministic rule failures from model-derived concerns
- Review trace must be stored for 30 days

## Constraints

- No raw cardholder data may leave the tenant boundary
- EU tenants require separate processing and storage paths
- Rollback from enforced blocking mode to advisory mode must take less than 5 minutes
- The current team has two platform engineers and one security engineer available for the pilot

## Open Questions

- The proposal mentions "code snippets" in prompts but does not define a redaction policy
- There is no stated offline eval set for false positives on safe infrastructure changes
- The current logging plan stores prompt and response payloads in the same analytics sink used for generic application telemetry
- No owner is named for after-hours incidents if the reviewer blocks a hotfix
