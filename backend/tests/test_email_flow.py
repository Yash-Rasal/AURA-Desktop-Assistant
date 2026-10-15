"""Unit tests for full email conversational flow, back, cancel, invalid inputs, and timeouts."""
from unittest.mock import patch
import pytest

from backend.flows import FlowEngine, start_flow_from_text
from backend.memory.session import SessionMemory


@pytest.fixture
def session():
    return SessionMemory()


@pytest.mark.asyncio
async def test_email_flow_happy_path(session):
    # 1. Trigger flow
    res = start_flow_from_text("write an email", session)
    assert res is not None
    assert session.active_flow is not None
    assert session.active_flow.status == "active"
    assert "Who would you like to send this email to" in res.reply_text

    # 2. Provide recipient
    res2 = await FlowEngine.handle("john dot doe at gmail dot com", session)
    assert session.active_flow.slots["to"] == "john.doe@gmail.com"
    assert "subject" in res2.reply_text.lower()

    # 3. Provide subject
    res3 = await FlowEngine.handle("Quarterly Review Meeting", session)
    assert session.active_flow.slots["subject"] == "Quarterly Review Meeting"
    assert "body" in res3.reply_text.lower()

    # 4. Provide body (multiline)
    res4 = await FlowEngine.handle("Let us meet at 10 AM on Monday.", session)
    assert "10 AM on Monday" in session.active_flow.slots["body"]
    assert "done" in res4.reply_text.lower()

    # 5. Finalize body with 'done'
    res5 = await FlowEngine.handle("done", session)
    assert session.active_flow.status == "awaiting_confirm"
    assert "ready" in res5.reply_text.lower()

    # 6. Confirm and execute draft opening (mock webbrowser)
    with patch("webbrowser.open", return_value=True) as mock_open:
        res6 = await FlowEngine.handle("send", session)
        assert mock_open.called
        assert res6.finished is True
        assert session.active_flow is None
        assert "draft is ready" in res6.reply_text.lower()


@pytest.mark.asyncio
async def test_email_flow_trigger_with_recipient(session):
    # Pre-filled recipient
    res = start_flow_from_text("compose email to alice@example.com", session)
    assert res is not None
    assert session.active_flow.slots.get("to") == "alice@example.com"
    assert "subject" in res.reply_text.lower()


@pytest.mark.asyncio
async def test_email_flow_invalid_recipient_retry(session):
    start_flow_from_text("write an email", session)

    # Invalid input
    res = await FlowEngine.handle("not an email address", session)
    assert session.active_flow.step_index == 0
    assert "doesn't look like a valid email" in res.reply_text

    # Valid input follows
    res2 = await FlowEngine.handle("valid.user at company dot com", session)
    assert session.active_flow.slots["to"] == "valid.user@company.com"
    assert "subject" in res2.reply_text.lower()


@pytest.mark.asyncio
async def test_email_flow_back_operation(session):
    start_flow_from_text("write an email", session)
    await FlowEngine.handle("alice at domain dot com", session)
    assert session.active_flow.step_index == 1

    # Say "go back"
    res = await FlowEngine.handle("go back", session)
    assert session.active_flow.step_index == 0
    assert "Going back" in res.reply_text


@pytest.mark.asyncio
async def test_email_flow_cancel_operation(session):
    start_flow_from_text("write an email", session)
    assert session.active_flow is not None

    res = await FlowEngine.handle("cancel", session)
    assert res.finished is True
    assert session.active_flow is None
    assert "cancelled" in res.reply_text.lower()


@pytest.mark.asyncio
async def test_email_flow_timeout_expiry(session):
    start_flow_from_text("write an email", session)
    # Simulate 100 seconds idle
    session.active_flow.last_activity -= 100

    res = await FlowEngine.handle("some input", session)
    assert res.finished is True
    assert session.active_flow is None
    assert "timed out" in res.reply_text.lower()
