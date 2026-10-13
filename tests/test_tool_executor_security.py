import asyncio

import pytest

from backend.app.agents import tool_executor


def run_async(coro):
    return asyncio.run(coro)


def test_unauthorized_tool_function_is_never_called(monkeypatch):
    calls = []

    def dangerous_function(db, **kwargs):
        calls.append("executed")
        return {"changed": True}

    monkeypatch.setattr(
        tool_executor,
        "get_tool",
        lambda name: {
            "function": dangerous_function,
            "read_only": False,
            "requires_authorization": True,
        },
    )

    monkeypatch.setattr(
        tool_executor.authorization_policy,
        "can_execute",
        lambda **kwargs: False,
    )

    result = run_async(
        tool_executor.execute_tool(
            db=None,
            tool_name="fake_mutation",
            parameters={},
            authorized=False,
        )
    )

    assert result["success"] is False
    assert calls == []


def test_unregistered_tool_raises_tool_execution_error(monkeypatch):
    def reject_unknown_tool(name):
        raise ValueError(f"Tool '{name}' is not registered.")

    monkeypatch.setattr(
        tool_executor,
        "get_tool",
        reject_unknown_tool,
    )

    with pytest.raises(
        tool_executor.ToolExecutionError,
        match="not registered",
    ):
        run_async(
            tool_executor.execute_tool(
                db=None,
                tool_name="unknown_tool",
                parameters={},
                authorized=False,
            )
        )


def test_authorized_tool_executes_and_returns_result(monkeypatch):
    calls = []

    def safe_test_function(db, value):
        calls.append(value)
        return {"received": value}

    monkeypatch.setattr(
        tool_executor,
        "get_tool",
        lambda name: {
            "function": safe_test_function,
            "read_only": False,
            "requires_authorization": True,
        },
    )

    monkeypatch.setattr(
        tool_executor.authorization_policy,
        "can_execute",
        lambda **kwargs: True,
    )

    result = run_async(
        tool_executor.execute_tool(
            db=None,
            tool_name="fake_mutation",
            parameters={"value": "test"},
            authorized=True,
        )
    )

    assert result["success"] is True
    assert result["tool"] == "fake_mutation"
    assert result["result"] == {"received": "test"}
    assert calls == ["test"]
