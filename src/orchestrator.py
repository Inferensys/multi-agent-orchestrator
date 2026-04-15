"""Core orchestration engine for multi-agent execution."""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum, auto
from datetime import datetime
import asyncio
import time

from .agent import Agent, AgentRegistry
from .message import MessageBus, Message, MessageAction
from .task import Task, TaskStatus, TaskResult, TaskQueue, TaskPriority
from .state import State


class ExecutionStrategy(Enum):
    """Task distribution strategies."""
    SEQUENTIAL = auto()      # One at a time
    PARALLEL = auto()        # All at once
    HIERARCHICAL = auto()    # Coordinator delegates
    PIPELINE = auto()        # Output feeds to next agent
    CONSENSUS = auto()       # Multiple agents, vote on result


@dataclass
class ExecutionConfig:
    """Configuration for task execution."""
    strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL
    max_parallel: int = 5
    timeout_seconds: float = 300.0
    retry_attempts: int = 2
    retry_delay_seconds: float = 1.0
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5


class Orchestrator:
    """Central coordinator for multi-agent task execution."""
    
    def __init__(self, config: Optional[ExecutionConfig] = None):
        self.config = config or ExecutionConfig()
        self.registry = AgentRegistry()
        self.bus = MessageBus()
        self.task_queue = TaskQueue()
        self._states: Dict[str, State] = {}
        self._execution_logs: Dict[str, List[Dict]] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._failure_counts: Dict[str, int] = {}
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the orchestrator."""
        self.registry.register(agent)
        # Subscribe agent to message bus
        self.bus.subscribe(agent.name, self._create_message_handler(agent))
    
    def register_agents(self, agents: List[Agent]) -> None:
        """Register multiple agents."""
        for agent in agents:
            self.register_agent(agent)
    
    def _create_message_handler(self, agent: Agent) -> Callable:
        """Create message handler for an agent."""
        async def handler(message: Message):
            await self._handle_agent_message(agent, message)
        return handler
    
    async def _handle_agent_message(self, agent: Agent, message: Message):
        """Process message from agent."""
        state = self._states.get(message.correlation_id)
        if state is None:
            return
        
        self._log_event(message.correlation_id, {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "message",
            "sender": message.sender,
            "recipient": message.recipient,
            "action": message.action,
        })
        
        # Handle different message actions
        if message.action == MessageAction.COMPLETE.value:
            await self._handle_task_complete(message, state)
        elif message.action == MessageAction.DELEGATE.value:
            await self._handle_task_delegate(message, state)
        elif message.action == MessageAction.REQUEST_INFO.value:
            await self._handle_info_request(message, state)
        elif message.action == MessageAction.ESCALATE.value:
            await self._handle_escalation(message, state)
    
    async def _handle_task_complete(self, message: Message, state: State):
        """Handle task completion."""
        task_id = message.correlation_id
        task = self.task_queue.get(task_id)
        if task:
            task.complete(TaskResult(
                success=True,
                output=message.payload.get("result"),
                metadata=message.payload.get("metadata", {})
            ))
    
    async def _handle_task_delegate(self, message: Message, state: State):
        """Handle subtask delegation."""
        target_agent = message.payload.get("target_agent")
        subtask_data = message.payload.get("subtask", {})
        
        subtask = Task(
            description=subtask_data.get("description", ""),
            requirements=subtask_data.get("requirements", {}),
            parent_task_id=message.correlation_id,
            context_id=message.correlation_id
        )
        subtask.assigned_agents = [target_agent]
        
        await self._assign_and_execute(subtask, state)
    
    async def _handle_info_request(self, message: Message, state: State):
        """Handle request for information."""
        # Fulfill request from state if available
        requested_key = message.payload.get("key")
        if requested_key and requested_key in state:
            reply = message.reply(
                action=MessageAction.INFORM.value,
                payload={"key": requested_key, "value": state.get(requested_key)}
            )
            await self.bus.publish(reply)
    
    async def _handle_escalation(self, message: Message, state: State):
        """Handle escalation to human/controller."""
        self._log_event(message.correlation_id, {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "escalation",
            "reason": message.payload.get("reason"),
            "context": message.payload
        })
    
    def _log_event(self, task_id: str, event: Dict):
        """Log execution event."""
        if task_id not in self._execution_logs:
            self._execution_logs[task_id] = []
        self._execution_logs[task_id].append(event)
    
    def execute(self, task: Task, strategy: Optional[ExecutionStrategy] = None) -> Task:
        """Execute a task with specified strategy."""
        strategy = strategy or self.config.strategy
        
        # Create state for this task
        state = State()
        self._states[task.id] = state
        
        # Queue task
        self.task_queue.enqueue(task)
        
        # Run in async context
        return asyncio.run(self._execute_task(task, state, strategy))
    
    async def _execute_task(self, task: Task, state: State, strategy: ExecutionStrategy) -> Task:
        """Execute task with chosen strategy."""
        task.start()
        
        try:
            if strategy == ExecutionStrategy.SEQUENTIAL:
                await self._execute_sequential(task, state)
            elif strategy == ExecutionStrategy.PARALLEL:
                await self._execute_parallel(task, state)
            elif strategy == ExecutionStrategy.HIERARCHICAL:
                await self._execute_hierarchical(task, state)
            elif strategy == ExecutionStrategy.CONSENSUS:
                await self._execute_consensus(task, state)
            else:
                await self._execute_sequential(task, state)
            
        except Exception as e:
            task.fail(str(e))
        
        return task
    
    async def _assign_and_execute(self, task: Task, state: State):
        """Assign task to agent and execute."""
        # Find suitable agent if not assigned
        if not task.assigned_agents:
            capable = self.registry.find_by_capability(task.requirements.get("action"))
            if capable:
                task.assigned_agents = [capable[0].name]
        
        if not task.assigned_agents:
            raise ValueError(f"No agent available for task: {task.description}")
        
        agent_name = task.assigned_agents[0]
        agent = self.registry.get(agent_name)
        
        if not agent:
            raise ValueError(f"Agent not found: {agent_name}")
        
        # Check circuit breaker
        if self.config.circuit_breaker_enabled:
            failures = self._failure_counts.get(agent_name, 0)
            if failures >= self.config.failure_threshold:
                raise Exception(f"Circuit breaker open for agent: {agent_name}")
        
        # Execute with retry
        for attempt in range(self.config.retry_attempts + 1):
            try:
                result = await agent.execute(task, state)
                self._failure_counts[agent_name] = 0  # Reset on success
                return result
            except Exception as e:
                self._failure_counts[agent_name] = self._failure_counts.get(agent_name, 0) + 1
                if attempt < self.config.retry_attempts:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2 ** attempt))
                else:
                    raise
    
    async def _execute_sequential(self, task: Task, state: State):
        """Execute subtasks sequentially."""
        if not task.subtasks:
            # Single task execution
            await self._assign_and_execute(task, state)
            return
        
        for subtask in task.subtasks:
            subtask.status = TaskStatus.RUNNING
            sub_task_obj = Task(
                description=subtask.description,
                id=subtask.id,
                requirements=task.requirements,
                assigned_agents=[subtask.assigned_to] if subtask.assigned_to else []
            )
            await self._assign_and_execute(sub_task_obj, state)
            subtask.status = TaskStatus.COMPLETED
    
    async def _execute_parallel(self, task: Task, state: State):
        """Execute subtasks in parallel with limit."""
        if not task.subtasks:
            await self._assign_and_execute(task, state)
            return
        
        semaphore = asyncio.Semaphore(self.config.max_parallel)
        
        async def execute_with_limit(subtask):
            async with semaphore:
                sub_task_obj = Task(
                    description=subtask.description,
                    id=subtask.id,
                    assigned_agents=[subtask.assigned_to] if subtask.assigned_to else []
                )
                await self._assign_and_execute(sub_task_obj, state)
                subtask.status = TaskStatus.COMPLETED
        
        await asyncio.gather(*[execute_with_limit(st) for st in task.subtasks])
    
    async def _execute_hierarchical(self, task: Task, state: State):
        """Coordinator agent decomposes and delegates."""
        # Delegate to coordinator (first assigned agent or first available)
        await self._assign_and_execute(task, state)
        # Coordinator handles subtask creation via messages
    
    async def _execute_consensus(self, task: Task, state: State):
        """Multiple agents solve, vote on best result."""
        action = task.requirements.get("action", "solve")
        capable_agents = self.registry.find_by_capability(action)
        
        if len(capable_agents) < 2:
            # Fall back to single execution
            await self._assign_and_execute(task, state)
            return
        
        # Execute with multiple agents
        results = []
        for agent in capable_agents[:3]:  # Max 3 agents
            sub_task = Task(
                description=task.description,
                assigned_agents=[agent.name]
            )
            try:
                result = await self._assign_and_execute(sub_task, state)
                results.append((agent.name, result))
            except Exception:
                pass  # Skip failed agents
        
        # Simple voting - could be more sophisticated
        if results:
            # Use first successful result (could implement actual voting logic)
            task.complete(TaskResult(
                success=True,
                output=results[0][1],
                metadata={"consensus_votes": len(results), "agents_used": [r[0] for r in results]}
            ))
    
    def get_execution_logs(self, task_id: str) -> List[Dict]:
        """Get execution logs for a task."""
        return self._execution_logs.get(task_id, [])
    
    def get_communication_graph(self, task_id: str) -> Dict:
        """Get graph of agent communication for visualization."""
        logs = self._execution_logs.get(task_id, [])
        nodes = set()
        edges = []
        
        for log in logs:
            if log.get("type") == "message":
                sender = log.get("sender")
                recipient = log.get("recipient")
                nodes.add(sender)
                nodes.add(recipient)
                edges.append({
                    "from": sender,
                    "to": recipient,
                    "action": log.get("action")
                })
        
        return {
            "nodes": [{"id": n, "label": n} for n in nodes],
            "edges": edges
        }
    
    def get_agent_metrics(self) -> Dict[str, Dict]:
        """Get performance metrics for all agents."""
        metrics = {}
        for agent in self.registry.list_agents():
            name = agent["name"]
            metrics[name] = agent["metrics"]
        return metrics
