"""Core FlowEngine and Flow lifecycle management."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

try:
    from config import settings
    from flows.control_words import ControlWord, detect_control_word
    from flows.state import FlowState
except ImportError:
    from backend.config import settings
    from backend.flows.control_words import ControlWord, detect_control_word
    from backend.flows.state import FlowState

logger = logging.getLogger("flows.engine")


@dataclass
class FlowStep:
    """Defines a single conversational step / slot collection."""
    slot_name: str
    prompt: str
    focus_field: str
    skippable: bool = False
    multiline: bool = False
    # validator: returns (is_valid, parsed_value, error_message)
    validator: Optional[Callable[[str, Dict[str, Any]], Tuple[bool, Any, Optional[str]]]] = None


@dataclass
class FlowResponse:
    """Standardized response returned to /chat and WebSocket clients for flow interactions."""
    reply_text: str
    focus_field: Optional[str] = None
    step_label: Optional[str] = None
    expects_voice_followup: bool = True
    ui_card: Optional[Dict[str, Any]] = None
    flow_active: bool = True
    finished: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply": self.reply_text,
            "flow": {
                "active": self.flow_active,
                "step_label": self.step_label,
                "focus_field": self.focus_field,
                "expects_voice_followup": self.expects_voice_followup,
                "ui_card": self.ui_card,
                "finished": self.finished,
            },
        }


class BaseFlow:
    """Base class for guided multi-turn conversational flows."""
    name: str = "base"
    title: str = "Base Flow"
    steps: List[FlowStep] = []

    def get_step(self, index: int) -> Optional[FlowStep]:
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def format_step_label(self, step_index: int) -> str:
        step = self.get_step(step_index)
        field_title = step.slot_name.capitalize() if step else "Review"
        total = len(self.steps)
        current = min(step_index + 1, total)
        return f"{self.title}: {field_title} ({current}/{total})"

    def format_confirm_prompt(self, slots: Dict[str, Any]) -> str:
        return "Are you ready to proceed? Say 'yes' or 'confirm', or 'back' to make changes."

    async def execute(self, slots: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Execute the flow's final action (opening draft, creating item, etc.)."""
        raise NotImplementedError


# Global registry of available flows
_FLOW_REGISTRY: Dict[str, Type[BaseFlow]] = {}


def register_flow(cls: Type[BaseFlow]) -> Type[BaseFlow]:
    """Decorator to register a flow class by its name."""
    _FLOW_REGISTRY[cls.name] = cls
    return cls


class FlowEngine:
    """Manages active conversational flows, step transitions, control words, and timeouts."""

    @classmethod
    def get_flow(cls, name: str) -> Optional[BaseFlow]:
        flow_cls = _FLOW_REGISTRY.get(name)
        if flow_cls:
            return flow_cls()
        return None

    @classmethod
    def start(
        cls,
        flow_name: str,
        session: Any,
        initial_slots: Optional[Dict[str, Any]] = None,
    ) -> FlowResponse:
        """Initialize and start a flow, returning the first prompt."""
        flow = cls.get_flow(flow_name)
        if not flow:
            return FlowResponse(
                reply_text=f"Flow '{flow_name}' not found.",
                flow_active=False,
                finished=True,
            )

        state = FlowState(
            flow_name=flow_name,
            step_index=0,
            slots=initial_slots or {},
        )

        # Advance past any steps already filled by initial_slots
        while state.step_index < len(flow.steps):
            cur_step = flow.steps[state.step_index]
            if cur_step.slot_name in state.slots and state.slots[cur_step.slot_name]:
                state.step_index += 1
            else:
                break

        session.set_active_flow(state)

        # If all steps are already filled, go straight to confirmation
        if state.step_index >= len(flow.steps):
            state.status = "awaiting_confirm"
            return cls._build_confirm_response(flow, state)

        current_step = flow.steps[state.step_index]
        return FlowResponse(
            reply_text=current_step.prompt,
            focus_field=current_step.focus_field,
            step_label=flow.format_step_label(state.step_index),
            expects_voice_followup=True,
            ui_card=cls._build_ui_card(flow, state),
            flow_active=True,
            finished=False,
        )

    @classmethod
    async def handle(cls, user_text: str, session: Any) -> FlowResponse:
        """Process user input against the currently active flow."""
        state: Optional[FlowState] = getattr(session, "active_flow", None)
        if not state:
            return FlowResponse(
                reply_text="No active flow found.",
                flow_active=False,
                finished=True,
            )

        flow = cls.get_flow(state.flow_name)
        if not flow:
            session.clear_active_flow()
            return FlowResponse(
                reply_text="Active flow definition is missing.",
                flow_active=False,
                finished=True,
            )

        # 1. Idle timeout check
        timeout = getattr(settings, "flow_idle_timeout_seconds", 90)
        if state.is_expired(timeout):
            session.clear_active_flow()
            return FlowResponse(
                reply_text="The session timed out due to inactivity. Let me know when you'd like to start over.",
                flow_active=False,
                finished=True,
            )

        state.touch()

        # 2. Control word detection
        cw = detect_control_word(user_text)

        # CANCEL works everywhere
        if cw == ControlWord.CANCEL:
            session.clear_active_flow()
            return FlowResponse(
                reply_text="Flow cancelled. What would you like to do next?",
                flow_active=False,
                finished=True,
                ui_card={"type": "flow_cancelled", "flow_name": state.flow_name},
            )

        # REPEAT works everywhere
        if cw == ControlWord.REPEAT:
            if state.status == "awaiting_confirm":
                return cls._build_confirm_response(flow, state)
            cur_step = flow.get_step(state.step_index)
            prompt = cur_step.prompt if cur_step else "Please continue."
            return FlowResponse(
                reply_text=f"I said: {prompt}",
                focus_field=cur_step.focus_field if cur_step else None,
                step_label=flow.format_step_label(state.step_index),
                ui_card=cls._build_ui_card(flow, state),
                flow_active=True,
            )

        # BACK works everywhere
        if cw == ControlWord.BACK:
            if state.pop_history():
                if state.status == "awaiting_confirm":
                    # If we were in confirm and popped back, we re-enter the last step
                    state.status = "active"
                cur_step = flow.get_step(state.step_index)
                prompt = cur_step.prompt if cur_step else "Please enter value."
                return FlowResponse(
                    reply_text=f"Going back. {prompt}",
                    focus_field=cur_step.focus_field if cur_step else None,
                    step_label=flow.format_step_label(state.step_index),
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )
            else:
                cur_step = flow.get_step(state.step_index)
                prompt = cur_step.prompt if cur_step else "Please enter value."
                return FlowResponse(
                    reply_text=f"Already at the first step. {prompt}",
                    focus_field=cur_step.focus_field if cur_step else None,
                    step_label=flow.format_step_label(state.step_index),
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )

        # 3. Confirmation state handling
        if state.status == "awaiting_confirm":
            if cw in (ControlWord.YES, ControlWord.SEND, ControlWord.DONE):
                # Execute final action
                ok, reply, card_data = await flow.execute(state.slots)
                session.clear_active_flow()
                return FlowResponse(
                    reply_text=reply,
                    step_label=f"{flow.title}: Complete",
                    ui_card=card_data,
                    flow_active=False,
                    finished=True,
                    expects_voice_followup=False,
                )
            elif cw == ControlWord.NO:
                return FlowResponse(
                    reply_text="Draft not opened. Say 'back' to edit, or 'cancel' to discard.",
                    step_label=f"{flow.title}: Review",
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )
            else:
                # User may have spoken an edit instruction like "change subject to X"
                # If unrecognized confirm, prompt again politely
                return FlowResponse(
                    reply_text="Ready to open the draft? Say 'yes' or 'send', or 'back' to make edits.",
                    step_label=f"{flow.title}: Review",
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )

        # 4. Standard Step Handling
        cur_step = flow.get_step(state.step_index)
        if not cur_step:
            state.status = "awaiting_confirm"
            return cls._build_confirm_response(flow, state)

        # SKIP handling
        if cw == ControlWord.SKIP:
            if cur_step.skippable:
                state.save_history()
                state.slots[cur_step.slot_name] = ""
                state.step_index += 1
                return cls._advance_or_confirm(flow, state)
            else:
                return FlowResponse(
                    reply_text=f"This step is required. {cur_step.prompt}",
                    focus_field=cur_step.focus_field,
                    step_label=flow.format_step_label(state.step_index),
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )

        # Multiline body step handling
        if cur_step.multiline:
            if cw == ControlWord.DONE:
                # Finished entering body
                if not state.slots.get(cur_step.slot_name):
                    state.slots[cur_step.slot_name] = ""
                state.save_history()
                state.step_index += 1
                return cls._advance_or_confirm(flow, state)
            else:
                # Append text to multiline slot
                existing = state.slots.get(cur_step.slot_name, "")
                cleaned_text = user_text.strip()
                if existing:
                    new_val = f"{existing}\n{cleaned_text}"
                else:
                    new_val = cleaned_text
                state.slots[cur_step.slot_name] = new_val
                return FlowResponse(
                    reply_text="Added to the message. Say 'done' when you're finished, or keep speaking to add more.",
                    focus_field=cur_step.focus_field,
                    step_label=flow.format_step_label(state.step_index),
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )

        # Single-line slot validation & parsing
        if cur_step.validator:
            is_valid, parsed_value, hint = cur_step.validator(user_text, state.slots)
            if not is_valid:
                retry_msg = hint or f"I didn't quite get that. {cur_step.prompt}"
                if state.awaiting_retry:
                    retry_msg += " (You can also type it or say it letter by letter)."
                state.awaiting_retry = True
                return FlowResponse(
                    reply_text=retry_msg,
                    focus_field=cur_step.focus_field,
                    step_label=flow.format_step_label(state.step_index),
                    ui_card=cls._build_ui_card(flow, state),
                    flow_active=True,
                )
            value = parsed_value
        else:
            value = user_text.strip()

        # Input accepted for this slot
        state.save_history()
        state.slots[cur_step.slot_name] = value
        state.awaiting_retry = False
        state.step_index += 1

        return cls._advance_or_confirm(flow, state)

    @classmethod
    def _advance_or_confirm(cls, flow: BaseFlow, state: FlowState) -> FlowResponse:
        """Advance to next step or show confirmation review."""
        if state.step_index >= len(flow.steps):
            state.status = "awaiting_confirm"
            return cls._build_confirm_response(flow, state)

        next_step = flow.steps[state.step_index]
        return FlowResponse(
            reply_text=next_step.prompt,
            focus_field=next_step.focus_field,
            step_label=flow.format_step_label(state.step_index),
            expects_voice_followup=True,
            ui_card=cls._build_ui_card(flow, state),
            flow_active=True,
            finished=False,
        )

    @classmethod
    def _build_confirm_response(cls, flow: BaseFlow, state: FlowState) -> FlowResponse:
        """Generate confirmation prompt and card."""
        prompt = flow.format_confirm_prompt(state.slots)
        return FlowResponse(
            reply_text=prompt,
            focus_field=None,
            step_label=f"{flow.title}: Review",
            expects_voice_followup=True,
            ui_card=cls._build_ui_card(flow, state),
            flow_active=True,
            finished=False,
        )

    @classmethod
    def _build_ui_card(cls, flow: BaseFlow, state: FlowState) -> Dict[str, Any]:
        """Generate UI card payload for Electron frontend rendering."""
        actions = []
        if state.status == "awaiting_confirm":
            actions.append({"label": "Open Draft", "cmd": "send", "primary": True})
            actions.append({"label": "Back", "cmd": "back"})
            actions.append({"label": "Cancel", "cmd": "cancel", "danger": True})
        else:
            cur_step = flow.get_step(state.step_index)
            if cur_step and cur_step.multiline:
                actions.append({"label": "Done Writing", "cmd": "done", "primary": True})
            if cur_step and cur_step.skippable:
                actions.append({"label": "Skip", "cmd": "skip"})
            if state.step_index > 0:
                actions.append({"label": "Back", "cmd": "back"})
            actions.append({"label": "Cancel", "cmd": "cancel", "danger": True})

        return {
            "type": "flow_card",
            "flow_name": state.flow_name,
            "title": flow.title,
            "step_label": flow.format_step_label(state.step_index) if state.status != "awaiting_confirm" else f"{flow.title}: Review",
            "slots": state.slots,
            "status": state.status,
            "actions": actions,
        }
