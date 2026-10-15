from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionMemory:
    messages: list[dict[str, Any]] = field(default_factory=list)
    recent_screenshots: list[dict[str, str]] = field(default_factory=list)
    max_messages: int = 40
    max_screenshots: int = 5
    active_flow: Any = None  # Optional[FlowState]
    context: Any = None      # Optional[ContextState]

    def set_active_flow(self, flow: Any) -> None:
        self.active_flow = flow

    def clear_active_flow(self) -> None:
        self.active_flow = None

    def set_context(self, context: Any) -> None:
        self.context = context

    def clear_context(self) -> None:
        self.context = None

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content, "ts": time.time()})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def add_screenshot(self, path: str, image_b64: str) -> None:
        self.recent_screenshots.append({"path": path, "b64": image_b64, "ts": time.time()})
        if len(self.recent_screenshots) > self.max_screenshots:
            self.recent_screenshots = self.recent_screenshots[-self.max_screenshots :]

    def chat_context(self) -> list[dict[str, str]]:
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def clear(self) -> None:
        self.messages.clear()
        self.recent_screenshots.clear()
        self.active_flow = None
        self.context = None

    def last_screenshot_b64(self) -> str | None:
        if not self.recent_screenshots:
            return None
        return self.recent_screenshots[-1]["b64"]


memory = SessionMemory()
