"""State definitions for guided multi-turn flows and desktop context tracking."""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FlowState:
    """Represents the mutable state of an in-progress conversational flow."""
    flow_name: str
    step_index: int = 0
    slots: Dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    status: str = "active"  # "active", "awaiting_confirm", "done", "cancelled"
    history: List[Dict[str, Any]] = field(default_factory=list)
    awaiting_retry: bool = False  # Set if user provided invalid input and must re-try slot

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()

    def is_expired(self, timeout_seconds: float = 90.0) -> bool:
        """Check if flow has gone idle past timeout."""
        return (time.time() - self.last_activity) > timeout_seconds

    def save_history(self) -> None:
        """Save a snapshot of step_index and slots to allow 'back' operation."""
        snapshot = {
            "step_index": self.step_index,
            "slots": copy.deepcopy(self.slots),
            "status": self.status,
            "awaiting_retry": self.awaiting_retry,
        }
        self.history.append(snapshot)

    def pop_history(self) -> bool:
        """Restore previous step state. Returns True if restored, False if empty."""
        if not self.history:
            return False
        prev = self.history.pop()
        self.step_index = prev["step_index"]
        self.slots = prev["slots"]
        self.status = prev["status"]
        self.awaiting_retry = prev.get("awaiting_retry", False)
        self.touch()
        return True


@dataclass
class ContextState:
    """Tracks recently opened applications, searches, or websites for follow-up actions."""
    app: str = ""
    last_action: str = ""  # e.g., "search", "open_app", "launch_website"
    last_query: str = ""
    last_url: str = ""
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: float = 120.0) -> bool:
        """Return True if context was recorded more than ttl_seconds ago."""
        return (time.time() - self.timestamp) > ttl_seconds
