# Multi-Agent Orchestrator

Reference implementation for **agent-to-agent communication**, **distributed task delegation**, and **workflow orchestration** across multiple AI agents.

Built for teams moving from single-agent demos to production multi-agent systems where agents specialize, collaborate, and handle failures gracefully.

## The Problem

Single agents hit limits:
- Context windows overflow on complex tasks
- No specialization—one agent tries to do everything
- No redundancy—agent fails, task fails
- No parallelism—sequential execution is slow

Multi-agent systems without orchestration hit different limits:
- Agents step on each other's work
- Message passing is ad-hoc spaghetti
- Debugging distributed reasoning is impossible
- No observability into agent conversations

This library addresses both.

## Core Concepts

```
Agent Registry        Task Router         Execution Engine
     ↓                     ↓                      ↓
 ┌─────────┐         ┌──────────┐          ┌─────────┐
 │ Analyst │←───────→│ Research │←────────→│ Browser │
 │   Agent │         │  Agent   │          │  Agent  │
 └─────────┘         └──────────┘          └─────────┘
       ↑                    ↑                    ↑
       └────────────────────┴────────────────────┘
                      Shared State
```

**Agent**: Encapsulated capability with defined inputs, outputs, and message handlers

**Task**: Unit of work with requirements, constraints, and success criteria

**Orchestrator**: Routes tasks, manages dependencies, tracks execution

**Protocol**: Message format for agent-to-agent communication (A2A compatible)

**State**: Shared working memory visible to participating agents

## Quick Start

```bash
pip install multi-agent-orchestrator
```

```python
from multi_agent_orchestrator import Orchestrator, Agent, Task

# Define specialized agents
researcher = Agent(
    name="researcher",
    capabilities=["web_search", "data_extraction"],
    model="gpt-4o"
)

analyst = Agent(
    name="analyst", 
    capabilities=["analysis", "summarization"],
    model="gpt-4o"
)

writer = Agent(
    name="writer",
    capabilities=["writing", "editing"],
    model="claude-3-5-sonnet"
)

# Configure orchestrator
orchestrator = Orchestrator()
orchestrator.register_agents([researcher, analyst, writer])

# Submit task with dependencies
task = Task(
    id="report-001",
    description="Write competitive analysis of serverless platforms",
    requirements={
        "sources": ["aws", "gcp", "azure"],
        "sections": ["pricing", "cold_start", "concurrency"]
    }
)

# Execute with orchestration
result = orchestrator.execute(task, strategy="parallel")
```

## Execution Strategies

### Sequential
```python
orchestrator.execute(task, strategy="sequential")
# Each subtask waits for previous to complete
```

### Parallel
```python
orchestrator.execute(task, strategy="parallel", max_parallel=3)
# Independent subtasks run concurrently
```

### Hierarchical
```python
orchestrator.execute(task, strategy="hierarchical", coordinator="planner")
# Coordinator agent decomposes and delegates
```

### Consensus
```python
orchestrator.execute(task, strategy="consensus", voter_count=3)
# Multiple agents solve, vote on best result
```

## Agent Definition

```python
from multi_agent_orchestrator import Agent, Message

class DataAnalyst(Agent):
    def __init__(self):
        super().__init__(
            name="data_analyst",
            description="Analyzes datasets and generates insights"
        )
    
    async def handle_message(self, message: Message, state: dict) -> Message:
        """Process incoming task messages."""
        if message.action == "analyze":
            dataset = state.get(message.payload["dataset_key"])
            insights = await self.analyze(dataset, message.payload["questions"])
            
            return Message(
                sender=self.name,
                recipient=message.sender,  # Reply to sender
                action="analysis_complete",
                payload={"insights": insights}
            )
    
    async def analyze(self, dataset, questions):
        # Implementation
        pass
```

## Inter-Agent Protocol

Agents communicate via structured messages:

```python
@dataclass
class Message:
    id: str                    # Unique message ID
    correlation_id: str        # Links to parent task
    sender: str               # Agent name
    recipient: str            # Target agent or broadcast
    action: str               # Action type
    payload: dict             # Action parameters
    priority: int = 0         # 0=low, 5=critical
    ttl: int = 10             # Max hops before drop
    timestamp: datetime       # Creation time
```

Protocol actions:
- `delegate`: Pass subtask to another agent
- `request_info`: Ask for data/clarification
- `propose`: Suggest partial solution
- `review`: Request review of work
- `complete`: Mark task done
- `escalate`: Raise to human/controller

## State Management

Shared state accessible to all agents in a task context:

```python
# Initialize with seed state
state = State({
    "customer_id": "cust_123",
    "ticket_history": [...],
    "policy_docs": [...]
})

# Agents read/write during execution
state.get("search_results")
state.set("analysis", {...})
state.append("messages", new_message)
```

State is versioned. Inspect any point in task execution:

```python
history = state.get_history()
# [{version: 0, data: {...}}, {version: 1, data: {...}}]
```

## Failure Handling

```python
orchestrator.execute(
    task,
    retry_policy={
        "max_retries": 3,
        "backoff": "exponential",
        "retry_on": ["timeout", "rate_limit"]
    },
    fallback_agent="human_escalation",
    circuit_breaker={
        "failure_threshold": 5,
        "timeout_seconds": 60
    }
)
```

When an agent fails:
1. Retry with same agent (if transient error)
2. Failover to backup agent (if available)
3. Redistribute task to peer agents
4. Escalate to human
5. Mark task failed with full trace

## Observability

```python
# Structured logs of all agent interactions
logs = orchestrator.get_execution_logs(task_id)

# Graph of agent communication
graph = orchestrator.get_communication_graph(task_id)

# Performance metrics
metrics = orchestrator.get_agent_metrics()
# {
#   "agent_name": {
#     "tasks_completed": 150,
#     "avg_latency_ms": 1200,
#     "error_rate": 0.02
#   }
# }
```

## Real-World Pattern: Customer Support Workflow

```python
# Multi-agent support resolution
orchestrator = Orchestrator()

# Define agents
triage = Agent("triage", capabilities=["classify", "route"])
resolver = Agent("resolver", capabilities=["diagnose", "resolve"])
escalation = Agent("escalation", capabilities=["handoff", "summarize"])

# Workflow definition
workflow = Workflow()
    .start(triage)
    .branch(
        condition=lambda state: state["priority"] == "high",
        then=escalation,
        else=resolver
    )
    .on_failure(resolver, escalation)

# Execute
ticket = Task(description="API returning 500 errors", ...)
result = orchestrator.execute_workflow(workflow, ticket)
```

## Runtimes

**Local**: All agents in single process
```python
orchestrator = LocalOrchestrator()
```

**Distributed**: Agents as separate services
```python
orchestrator = DistributedOrchestrator(
    message_bus="redis://localhost:6379",
    registry="consul://localhost:8500"
)
```

**Hybrid**: Mix of local and remote agents
```python
orchestrator = HybridOrchestrator()
orchestrator.register_local(analyst)
orchestrator.register_remote("writer", endpoint="http://writer.internal:8080")
```

## Configuration

```yaml
# orchestrator.yaml
agents:
  - name: researcher
    model: gpt-4o
    capabilities:
      - web_search
      - data_extraction
    max_tokens: 4000
    
  - name: analyst
    model: claude-3-5-sonnet
    capabilities:
      - synthesis
      - report_writing
    max_tokens: 4000

execution:
  default_strategy: parallel
  timeout_seconds: 300
  max_parallel_agents: 5

observability:
  enabled: true
  log_level: INFO
  trace_all_messages: true
```

## Performance Considerations

- State is kept in-memory for latency; checkpoint to persistent store every N messages
- Message serialization uses MessagePack for efficiency
- Agent model calls are batched when possible
- Connection pooling for distributed message bus

## Requirements

- Python 3.10+
- Pydantic 2.x for validation
- AnyIO for async runtime
- (Optional) Redis for distributed mode
- (Optional) Prometheus for metrics

## License

MIT
