import json

import pytest
from typer.testing import CliRunner

import flocks.cli.commands.export as export_cmd
import flocks.cli.commands.import_ as import_cmd
import flocks.mcp.server as mcp_server
from flocks.session.message import MessageWithParts, TextPart, UserMessageInfo
from flocks.session.session import SessionInfo, SessionTime

if not hasattr(mcp_server, "get_manager"):
    mcp_server.get_manager = lambda: None

from flocks.server.client import SessionClient

runner = CliRunner()


async def _noop_storage_init() -> None:
    return None


def _build_session(project_id: str = "proj_source") -> SessionInfo:
    return SessionInfo(
        id="ses_export_test",
        projectID=project_id,
        directory="/tmp/flocks-project",
        title="Export Session",
        time=SessionTime(created=1, updated=2),
    )


def _build_message_with_parts(session_id: str) -> MessageWithParts:
    message = UserMessageInfo(
        id="msg_export_test",
        sessionID=session_id,
        role="user",
        time={"created": 1},
        agent="rex",
        model={"providerID": "anthropic", "modelID": "claude-sonnet"},
    )
    part = TextPart(
        id="part_export_test",
        sessionID=session_id,
        messageID=message.id,
        text="hello export",
    )
    return MessageWithParts(info=message, parts=[part])


def test_export_and_import_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOCKS_ROOT", str(tmp_path))
    monkeypatch.setattr(export_cmd.Storage, "init", _noop_storage_init)
    monkeypatch.setattr(import_cmd.Storage, "init", _noop_storage_init)

    session = _build_session()
    message = _build_message_with_parts(session.id)
    output_path = tmp_path / "session-export.json"

    async def fake_get_by_id(session_id: str):
        assert session_id == session.id
        return session

    async def fake_list_with_parts(session_id: str, include_archived: bool = False):
        assert session_id == session.id
        assert include_archived is False
        return [message]

    stored_entries: list[tuple[str, dict, str | None]] = []

    async def fake_set(key: str, value: dict, category: str | None = None):
        stored_entries.append((key, value, category))

    monkeypatch.setattr(export_cmd.Session, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(export_cmd.Message, "list_with_parts", fake_list_with_parts)
    monkeypatch.setattr(import_cmd.Storage, "set", fake_set)

    export_result = runner.invoke(
        export_cmd.export_app,
        ["-o", str(output_path), "--no-pretty", session.id],
    )

    assert export_result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["info"]["id"] == session.id
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["info"]["id"] == message.info.id
    assert payload["messages"][0]["parts"][0]["id"] == "part_export_test"
    assert payload["messages"][0]["parts"][0]["text"] == "hello export"

    import_result = runner.invoke(
        import_cmd.import_app,
        ["-p", "proj_imported", str(output_path)],
    )

    assert import_result.exit_code == 0

    stored = {key: (value, category) for key, value, category in stored_entries}
    assert stored["session:proj_imported:ses_export_test"][0]["projectID"] == "proj_imported"
    assert stored["message:ses_export_test:msg_export_test"][0]["id"] == "msg_export_test"
    assert stored["part:msg_export_test:part_export_test"][0]["text"] == "hello export"


def test_export_help_does_not_show_project_option() -> None:
    result = runner.invoke(export_cmd.export_app, ["--help"])

    assert result.exit_code == 0
    assert "--project" not in result.stdout


@pytest.mark.asyncio
async def test_session_client_messages_returns_info_and_parts(monkeypatch) -> None:
    session = _build_session()
    message = _build_message_with_parts(session.id)

    async def fake_list_with_parts(session_id: str, include_archived: bool = False):
        assert session_id == session.id
        assert include_archived is False
        return [message]

    monkeypatch.setattr("flocks.server.client.Message.list_with_parts", fake_list_with_parts)

    client = SessionClient(base_url="http://127.0.0.1:8000")
    result = await client.messages(session.id, "/tmp/flocks-project")

    assert len(result) == 1
    assert result[0]["info"]["id"] == message.info.id
    assert result[0]["parts"][0]["id"] == "part_export_test"
    assert result[0]["parts"][0]["text"] == "hello export"
