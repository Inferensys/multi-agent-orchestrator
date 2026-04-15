"""Inter-agent messaging protocol."""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageAction(Enum):
    """Standard message action types."""
    DELEGATE = "delegate"
    REQUEST_INFO = "request_info"
    PROPOSE = "propose"
    REVIEW = "review"
    COMPLETE = "complete"
    ESCALATE = "escalate"
    ACKNOWLEDGE = "acknowledge"
    REJECT = "reject"
    QUERY = "query"
    INFORM = "inform"


@dataclass
class Message:
    """Message passed between agents."""
    
    sender: str
    recipient: str
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: int = 10  # Max hops before drop
    timestamp: datetime = field(default_factory=datetime.utcnow)
    parent_id: Optional[str] = None  # For message threading
    
    def __post_init__(self):
        """Set correlation ID from parent if not provided."""
        if self.correlation_id is None:
            self.correlation_id = self.id
    
    def reply(self, action: str, payload: Dict[str, Any]) -> "Message":
        """Create reply message."""
        return Message(
            sender=self.recipient,  # Reply sender is original recipient
            recipient=self.sender,
            action=action,
            payload=payload,
            correlation_id=self.correlation_id,
            parent_id=self.id
        )
    
    def forward(self, new_recipient: str) -> "Message":
        """Forward message to another agent (decrement TTL)."""
        return Message(
            sender=self.sender,
            recipient=new_recipient,
            action=self.action,
            payload=self.payload,
            correlation_id=self.correlation_id,
            ttl=self.ttl - 1,
            parent_id=self.parent_id
        )
    
    def is_broadcast(self) -> bool:
        """Check if message is broadcast (recipient is '*')."""
        return self.recipient == "*"
    
    def is_expired(self) -> bool:
        """Check if message TTL has expired."""
        return self.ttl <= 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "correlation_id": self.correlation_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "action": self.action,
            "payload": self.payload,
            "priority": self.priority.value,
            "ttl": self.ttl,
            "timestamp": self.timestamp.isoformat(),
            "parent_id": self.parent_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            correlation_id=data.get("correlation_id"),
            sender=data["sender"],
            recipient=data["recipient"],
            action=data["action"],
            payload=data.get("payload", {}),
            priority=MessagePriority(data.get("priority", 1)),
            ttl=data.get("ttl", 10),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            parent_id=data.get("parent_id"),
        )


class MessageBus:
    """In-memory message bus for agent communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, list] = {}
        self._history: list = []
        self._max_history = 10000
    
    def subscribe(self, agent_name: str, callback) -> None:
        """Subscribe agent to receive messages."""
        if agent_name not in self._subscribers:
            self._subscribers[agent_name] = []
        self._subscribers[agent_name].append(callback)
    
    def unsubscribe(self, agent_name: str, callback) -> None:
        """Unsubscribe agent from messages."""
        if agent_name in self._subscribers:
            self._subscribers[agent_name] = [
                cb for cb in self._subscribers[agent_name] if cb != callback
            ]
    
    async def publish(self, message: Message) -> None:
        """Publish message to recipient(s)."""
        # Store in history
        self._history.append(message.to_dict())
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        # Expired messages are dropped
        if message.is_expired():
            return
        
        if message.is_broadcast():
            # Send to all subscribers
            for callbacks in self._subscribers.values():
                for callback in callbacks:
                    await callback(message)
        else:
            # Send to specific recipient
            callbacks = self._subscribers.get(message.recipient, [])
            for callback in callbacks:
                await callback(message)
    
    def get_history(self, correlation_id: Optional[str] = None) -> list:
        """Get message history, optionally filtered by correlation."""
        if correlation_id:
            return [m for m in self._history if m.get("correlation_id") == correlation_id]
        return self._history.copy()
