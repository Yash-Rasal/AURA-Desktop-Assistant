"""Integration tests for FastAPI /chat and /flow endpoints."""
from unittest.mock import patch
import pytest
from httpx import AsyncClient, ASGITransport

from backend.api.main import app
from backend.memory.session import memory


@pytest.fixture(autouse=True)
def clean_memory():
    memory.clear()
    yield
    memory.clear()


@pytest.mark.asyncio
async def test_chat_starts_and_completes_email_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Start flow via /chat
        res1 = await client.post("/chat", json={"message": "write an email", "use_screen": False})
        assert res1.status_code == 200
        data1 = res1.json()
        assert "flow" in data1
        assert data1["flow"]["active"] is True
        assert "Who would you like" in data1["reply"]

        # 2. Enter recipient
        res2 = await client.post("/chat", json={"message": "test at domain dot com", "use_screen": False})
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["flow"]["active"] is True
        assert "subject" in data2["reply"].lower()

        # 3. Enter subject
        res3 = await client.post("/chat", json={"message": "Weekly Sync", "use_screen": False})
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["flow"]["active"] is True
        assert "body" in data3["reply"].lower()

        # 4. Enter body & done
        res4 = await client.post("/chat", json={"message": "All tasks on track.", "use_screen": False})
        assert res4.status_code == 200

        res5 = await client.post("/chat", json={"message": "done", "use_screen": False})
        assert res5.status_code == 200
        data5 = res5.json()
        assert data5["flow"]["active"] is True
        assert "ready" in data5["reply"].lower()

        # 5. Confirm draft opening
        with patch("webbrowser.open", return_value=True):
            res6 = await client.post("/chat", json={"message": "send", "use_screen": False})
            assert res6.status_code == 200
            data6 = res6.json()
            assert data6["flow"]["finished"] is True
            assert "draft is ready" in data6["reply"].lower()


@pytest.mark.asyncio
async def test_flow_endpoints_direct():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start via /flow/start
        res = await client.post("/flow/start", json={"flow_name": "email"})
        assert res.status_code == 200
        assert res.json()["flow"]["active"] is True

        # Check /flow/state
        state_res = await client.get("/flow/state")
        assert state_res.status_code == 200
        assert state_res.json()["active"] is True

        # Cancel via /flow/cancel
        cancel_res = await client.post("/flow/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["ok"] is True

        # Check /flow/state is now inactive
        state_res2 = await client.get("/flow/state")
        assert state_res2.status_code == 200
        assert state_res2.json()["active"] is False


@pytest.mark.asyncio
async def test_quick_command_still_works():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("backend.commands.dispatcher.launch_app", return_value={"ok": True, "app": "notepad", "reply": "Launched Notepad."}):
            res = await client.post("/chat", json={"message": "open notepad", "use_screen": False})
            assert res.status_code == 200
            data = res.json()
            assert "quick_command" in data
            assert data["quick_command"]["action"] == "open_app"
