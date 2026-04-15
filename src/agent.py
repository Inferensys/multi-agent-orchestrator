"""Agent definition and capability management."""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import asyncio
import time


class AgentStatus(Enum):
    """Agent lifecycle states."""
    IDLE = auto()
    BUSY = auto()
    ERROR = auto()
    OFFLINE = auto()


@dataclass
class AgentCapabilities:
    """Capabilities an agent can provide."""
    actions: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    max_context_tokens: int = 8000
    
    def can_handle(self, action: str) -> bool:
        """Check if agent supports given action."""
        return action in self.actions


@dataclass
class AgentMetrics:
    """Runtime performance metrics."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0
    last_active: Optional[float] = None
    
    @property
    def avg_latency_ms(self) -> float:
        """Average task latency in milliseconds."""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 0.0
        return self.total_latency_ms / total
    
    @property
    def error_rate(self) -> float:
        """Error rate as percentage."""
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 0.0
        return self.error_count / total


class Agent:
    """Base class for all agents in the system."""
    
    def __init__(
        self,
        name: str,
        capabilities: Optional[AgentCapabilities] = None,
        description: str = "",
        model: Optional[str] = None,
        timeout_seconds: float = 60.0
    ):
        self.name = name
        self.capabilities = capabilities or AgentCapabilities()
        self.description = description
        self.model = model
        self.timeout_seconds = timeout_seconds
        
        self.status = AgentStatus.IDLE
        self.metrics = AgentMetrics()
        self._message_handlers: Dict[str, Callable] = {}
        self._current_task: Optional[str] = None
    
    def register_handler(self, action: str, handler: Callable) -> None:
        """Register a handler for a specific message action."""
        self._message_handlers[action] = handler
    
    async def handle_message(self, message, state) -> Any:
        """
        Process incoming message.
        
        Override in subclasses for custom behavior.
        """
        handler = self._message_handlers.get(message.action)
        if handler:
            return await handler(message, state)
        
        # Default: acknowledge receipt
        from .message import Message
        return Message(
            sender=self.name,
            recipient=message.sender,
            action="acknowledged",
            payload={"received_message_id": message.id}
        )
    
    async def execute(self, task, state) -> Any:
        """
        Execute a task with the agent.
        
        Wraps handle_message with metrics and error handling.
        """
        self.status = AgentStatus.BUSY
        self._current_task = task.id
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                self.handle_message(task.to_message(), state),
                timeout=self.timeout_seconds
            )
            
            self.metrics.tasks_completed += 1
            self.metrics.last_active = time.time()
            
            return result
            
        except asyncio.TimeoutError:
            self.metrics.tasks_failed += 1
            self.metrics.error_count += 1
            raise AgentTimeoutError(f"Agent {self.name} timed out on task {task.id}")
            
        except Exception as e:
            self.metrics.tasks_failed += 1
            self.metrics.error_count += 1
            raise AgentExecutionError(f"Agent {self.name} failed: {e}") from e
            
        finally:
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.total_latency_ms += latency_ms
            self.status = AgentStatus.IDLE
            self._current_task = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.name,
            "capabilities": {
                "actions": self.capabilities.actions,
                "domains": self.capabilities.domains,
                "tools": self.capabilities.tools,
            },
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "avg_latency_ms": self.metrics.avg_latency_ms,
                "error_rate": self.metrics.error_rate,
            }
        }


class AgentTimeoutError(Exception):
    """Raised when agent execution times out."""
    pass


class AgentExecutionError(Exception):
    """Raised when agent execution fails."""
    pass


class AgentRegistry:
    """Registry for discovering and managing agents."""
    
    def __init__(self):
        self._agents: Dict[str, Agent] = {}
    
    def register(self, agent: Agent) -> None:
        """Register an agent."""
        self._agents[agent.name] = agent
    
    def unregister(self, name: str) -> Optional[Agent]:
        """Remove agent from registry."""
        return self._agents.pop(name, None)
    
    def get(self, name: str) -> Optional[Agent]:
        """Get agent by name."""
        return self._agents.get(name)
    
    def find_by_capability(self, action: str) -> List[Agent]:
        """Find all agents that can handle given action."""
        return [
            agent for agent in self._agents.values()
            if agent.capabilities.can_handle(action)
        ]
    
    def find_by_domain(self, domain: str) -> List[Agent]:
        """Find all agents specializing in given domain."""
        return [
            agent for agent in self._agents.values()
            if domain in agent.capabilities.domains
        ]
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents with their status."""
        return [agent.to_dict() for agent in self._agents.values()]
    
    def get_health(self) -> Dict[str, Any]:
        """Get health status of all agents."""
        return {
            "total": len(self._agents),
            "online": sum(1 for a in self._agents.values() if a.status != AgentStatus.OFFLINE),
            "busy": sum(1 for a in self._agents.values() if a.status == AgentStatus.BUSY),
            "idle": sum(1 for a in self._agents.values() if a.status == AgentStatus.IDLE),
            "error": sum(1 for a in self._agents.values() if a.status == AgentStatus.ERROR),
        }
