# Azure Foundry Notes

The checked-in demo is designed for Azure OpenAI deployments that are already common in this workspace:

- planner: `gpt-5.4`
- specialists: `gpt-5.2-chat`
- synthesizer: `gpt-5.4`
- reviewer: `gpt-5.4`

Environment:

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export AZURE_OPENAI_API_KEY="<key>"
export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
export MULTI_AGENT_PLANNER_DEPLOYMENT="gpt-5.4"
export MULTI_AGENT_SPECIALIST_DEPLOYMENT="gpt-5.2-chat"
export MULTI_AGENT_SYNTHESIZER_DEPLOYMENT="gpt-5.4"
export MULTI_AGENT_REVIEWER_DEPLOYMENT="gpt-5.4"
```

Run:

```bash
uv run python scripts/run_live_demo.py
```

Model split rationale:

- keep planning and final adjudication on the heavier deployment
- keep parallel specialist passes on the cheaper chat deployment
- keep rollout control, fallback, and validation in code
