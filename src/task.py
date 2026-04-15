"""Task definition and lifecycle management."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import uuid


class TaskStatus(Enum):
    """Task lifecycle states."""
    PENDING = auto()
    SCHEDULED = auto()
    RUNNING = auto()
    WAITING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskResult:
    """Result of task execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    tokens_used: int = 0


@dataclass
class SubTask:
    """Component of a larger task."""
    id: str
    description: str
    assigned_to: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None


@dataclass
class Task:
    """Work unit assigned to one or more agents."""
    
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requirements: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    
    # Execution tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_agents: List[str] = field(default_factory=list)
    subtasks: List[SubTask] = field(default_factory=list)
    
    # Context
    context_id: Optional[str] = None  # Links to shared state
    parent_task_id: Optional[str] = None  # For task hierarchies
    
    # Results
    result: Optional[TaskResult] = None
    error: Optional[str] = None
    
    def to_message(self):
        """Convert task to initial delegation message."""
        from .message import Message, MessageAction
        return Message(
            sender="orchestrator",
            recipient=self.assigned_agents[0] if self.assigned_agents else "*",
            action=MessageAction.DELEGATE.value,
            payload={
                "task_id": self.id,
                "description": self.description,
                "requirements": self.requirements,
                "constraints": self.constraints,
            },
            correlation_id=self.id
        )
    
    def start(self):
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def complete(self, result: TaskResult):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.utcnow()
    
    def fail(self, error: str):
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.utcnow()
    
    def add_subtask(self, description: str, assigned_to: Optional[str] = None,
                    dependencies: Optional[List[str]] = None) -> SubTask:
        """Add subtask to this task."""
        subtask = SubTask(
            id=f"{self.id}-{len(self.subtasks)}",
            description=description,
            assigned_to=assigned_to,
            dependencies=dependencies or []
        )
        self.subtasks.append(subtask)
        return subtask
    
    def get_ready_subtasks(self) -> List[SubTask]:
        """Get subtasks ready to execute (dependencies met)."""
        completed_ids = {s.id for s in self.subtasks 
                        if s.status == TaskStatus.COMPLETED}
        return [
            s for s in self.subtasks
            if s.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in s.dependencies)
        ]
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration if completed."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class TaskQueue:
    """Priority queue for task scheduling."""
    
    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._pending: List[str] = []
    
    def enqueue(self, task: Task) -> None:
        """Add task to queue."""
        self._tasks[task.id] = task
        self._pending.append(task.id)
        self._pending.sort(key=lambda tid: self._tasks[tid].priority.value, reverse=True)
    
    def dequeue(self) -> Optional[Task]:
        """Get highest priority pending task."""
        while self._pending:
            task_id = self._pending.pop(0)
            if task_id in self._tasks:
                return self._tasks[task_id]
        return None
    
    def get(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    def remove(self, task_id: str) -> Optional[Task]:
        """Remove task from queue."""
        if task_id in self._pending:
            self._pending.remove(task_id)
        return self._tasks.pop(task_id, None)
    
    def list_by_status(self, status: TaskStatus) -> List[Task]:
        """List tasks filtered by status."""
        return [t for t in self._tasks.values() if t.status == status]
