"""Guided conversational flow system public API and trigger routing."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Union

try:
    from config import settings
    from flows.context_followups import resolve_followup, save_context
    from flows.engine import FlowEngine, FlowResponse
    from flows.normalizers import is_valid_email, normalize_spoken_email
    from flows.state import ContextState, FlowState
    from flows import email_flow  # noqa: F401
except ImportError:
    from backend.config import settings
    from backend.flows.context_followups import resolve_followup, save_context
    from backend.flows.engine import FlowEngine, FlowResponse
    from backend.flows.normalizers import is_valid_email, normalize_spoken_email
    from backend.flows.state import ContextState, FlowState
    from backend.flows import email_flow  # noqa: F401

logger = logging.getLogger("flows")

# Email trigger patterns (explicitly excludes 'open email')
_EMAIL_TRIGGER = re.compile(
    r"^(?:write|compose|draft|create|send)\s+(?:an?\s+)?(?:email|mail)(?:\s+to\s+(.+))?$",
    re.IGNORECASE,
)


def start_flow_from_text(text: str, session: Any) -> Optional[FlowResponse]:
    """
    Check if the user input is a trigger phrase to begin a guided flow.
    Supports pre-filling initial slots (e.g. 'write an email to john@gmail.com').
    """
    clean = text.strip()
    match = _EMAIL_TRIGGER.match(clean)
    if match:
        initial_slots: Dict[str, Any] = {}
        recipient_raw = match.group(1)
        if recipient_raw:
            norm = normalize_spoken_email(recipient_raw)
            if is_valid_email(norm):
                initial_slots["to"] = norm

        return FlowEngine.start("email", session, initial_slots=initial_slots)

    return None


async def handle_flow_or_followup(
    text: str,
    session: Any,
) -> Optional[Union[FlowResponse, Dict[str, Any]]]:
    """
    Main entrypoint called by /chat and voice event pipelines:
    1. If a flow is already active in session -> pass text to FlowEngine.handle()
    2. If text triggers a new flow -> start it via start_flow_from_text()
    3. If text is a context-aware follow-up -> resolve via resolve_followup()
    4. Otherwise -> return None to fall through to quick commands / LLM
    """
    if not getattr(settings, "flows_enabled", True):
        return None

    try:
        # 1. Active flow takes top priority (both active slot-filling and confirmation review)
        active_flow = getattr(session, "active_flow", None)
        if active_flow and getattr(active_flow, "status", None) in ("active", "awaiting_confirm"):
            return await FlowEngine.handle(text, session)

        # 2. Check flow trigger phrases
        flow_start_res = start_flow_from_text(text, session)
        if flow_start_res:
            return flow_start_res

        # 3. Check desktop/browser context follow-ups
        context = getattr(session, "context", None)
        if context:
            followup_res = await resolve_followup(text, context)
            if followup_res:
                return followup_res

    except Exception as e:
        logger.exception("Error in handle_flow_or_followup: %s", e)

    return None


__all__ = [
    "handle_flow_or_followup",
    "start_flow_from_text",
    "save_context",
    "FlowEngine",
    "FlowResponse",
    "FlowState",
    "ContextState",
]
