"""Shared state management for multi-agent workflows."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import copy
import json


@dataclass
class StateVersion:
    """Snapshot of state at a specific point."""
    version: int
    timestamp: datetime
    data: Dict[str, Any]
    agent_name: Optional[str] = None
    action: Optional[str] = None


class State:
    """Shared working memory for agent collaboration."""
    
    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._data: Dict[str, Any] = initial_data or {}
        self._history: List[StateVersion] = [
            StateVersion(
                version=0,
                timestamp=datetime.utcnow(),
                data=copy.deepcopy(self._data)
            )
        ]
        self._version_counter = 0
        self._locks: Dict[str, str] = {}  # key -> agent_name (for optimistic locking)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state."""
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any, agent_name: Optional[str] = None,
            action: Optional[str] = None) -> None:
        """Set value and create new version."""
        self._data[key] = value
        self._create_version(agent_name, action, {key: value})
    
    def delete(self, key: str, agent_name: Optional[str] = None) -> None:
        """Delete key from state."""
        if key in self._data:
            del self._data[key]
            self._create_version(agent_name, f"delete:{key}")
    
    def append(self, key: str, value: Any, agent_name: Optional[str] = None) -> None:
        """Append to list in state."""
        if key not in self._data:
            self._data[key] = []
        if not isinstance(self._data[key], list):
            raise ValueError(f"Cannot append to non-list value at key: {key}")
        self._data[key].append(value)
        self._create_version(agent_name, f"append:{key}", {key: self._data[key]})
    
    def extend(self, key: str, values: List[Any], agent_name: Optional[str] = None) -> None:
        """Extend list in state."""
        if key not in self._data:
            self._data[key] = []
        if not isinstance(self._data[key], list):
            raise ValueError(f"Cannot extend non-list value at key: {key}")
        self._data[key].extend(values)
        self._create_version(agent_name, f"extend:{key}", {key: self._data[key]})
    
    def update(self, key: str, updates: Dict[str, Any],
               agent_name: Optional[str] = None) -> None:
        """Update dict in state."""
        if key not in self._data:
            self._data[key] = {}
        if not isinstance(self._data[key], dict):
            raise ValueError(f"Cannot update non-dict value at key: {key}")
        self._data[key].update(updates)
        self._create_version(agent_name, f"update:{key}", {key: self._data[key]})
    
    def merge(self, data: Dict[str, Any], agent_name: Optional[str] = None) -> None:
        """Merge dictionary into state."""
        self._data.update(data)
        self._create_version(agent_name, "merge", data)
    
    def keys(self) -> List[str]:
        """Get all state keys."""
        return list(self._data.keys())
    
    def to_dict(self) -> Dict[str, Any]:
        """Get current state as dictionary."""
        return copy.deepcopy(self._data)
    
    def _create_version(self, agent_name: Optional[str], action: Optional[str],
                        changes: Optional[Dict[str, Any]] = None) -> None:
        """Create new version checkpoint."""
        self._version_counter += 1
        version = StateVersion(
            version=self._version_counter,
            timestamp=datetime.utcnow(),
            data=copy.deepcopy(self._data),
            agent_name=agent_name,
            action=action
        )
        self._history.append(version)
        
        # Limit history size
        if len(self._history) > 100:
            # Keep first version and last 99
            self._history = [self._history[0]] + self._history[-99:]
    
    def get_version(self, version: int) -> Optional[StateVersion]:
        """Get specific version."""
        for v in self._history:
            if v.version == version:
                return v
        return None
    
    def get_history(self) -> List[StateVersion]:
        """Get full version history."""
        return self._history.copy()
    
    def rollback(self, version: int) -> bool:
        """Rollback to specific version."""
        target = self.get_version(version)
        if target:
            self._data = copy.deepcopy(target.data)
            self._create_version(None, f"rollback_to_{version}")
            return True
        return False
    
    def diff(self, from_version: int, to_version: int) -> Dict[str, Any]:
        """Calculate diff between two versions."""
        from_data = self.get_version(from_version)
        to_data = self.get_version(to_version)
        
        if not from_data or not to_data:
            return {}
        
        diff = {}
        from_keys = set(from_data.data.keys())
        to_keys = set(to_data.data.keys())
        
        for key in to_keys - from_keys:
            diff[key] = {"op": "added", "value": to_data.data[key]}
        
        for key in from_keys - to_keys:
            diff[key] = {"op": "removed", "old_value": from_data.data[key]}
        
        for key in from_keys & to_keys:
            if from_data.data[key] != to_data.data[key]:
                diff[key] = {
                    "op": "modified",
                    "old_value": from_data.data[key],
                    "new_value": to_data.data[key]
                }
        
        return diff
    
    def lock(self, key: str, agent_name: str) -> bool:
        """Attempt to lock a key for exclusive access."""
        if key in self._locks:
            return False
        self._locks[key] = agent_name
        return True
    
    def unlock(self, key: str, agent_name: str) -> bool:
        """Unlock a key."""
        if key in self._locks and self._locks[key] == agent_name:
            del self._locks[key]
            return True
        return False
    
    def get_locks(self) -> Dict[str, str]:
        """Get current locks."""
        return self._locks.copy()
    
    def __contains__(self, key: str) -> bool:
        return key in self._data
    
    def __getitem__(self, key: str) -> Any:
        return self._data[key]
