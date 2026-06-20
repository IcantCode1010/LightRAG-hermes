import asyncio
import os
from pathlib import Path
import sys

import pytest

from hermes_ui.config import HermesUISettings
from hermes_ui.hermes_runner import (
    _run_subprocess,
    build_chat_command,
    build_ingest_prompt,
    build_snapshot_prompt,
    run_hermes_query,
)


def test_build_chat_command_sets_command_and_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("EXISTING_ENV", "kept")
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    command, env = build_chat_command("hello", settings)

    assert command == [
        "hermes",
        "chat",
        "--query",
        "hello",
        "--quiet",
        "--max-turns",
        "8",
    ]
    assert env["HERMES_HOME"] == str(tmp_path / "hermes")
    assert env["EXISTING_ENV"] == "kept"
    assert env is not os.environ


def test_build_ingest_prompt_names_tool_fields_and_safety_rules():
    prompt = build_ingest_prompt(
        document_key="doc-1",
        version_label="v1",
        title="Release notes",
        text="Important content",
    )

    assert "lightrag-hermes" in prompt
    assert "ingest_text_version" in prompt
    assert "document_key" in prompt
    assert "version_label" in prompt
    assert "title" in prompt
    assert "text" in prompt
    assert "doc-1" in prompt
    assert "v1" in prompt
    assert "Release notes" in prompt
    assert "Important content" in prompt
    lowered = prompt.lower()
    assert "never delete" in lowered
    assert "never clear" in lowered
    assert "never overwrite" in lowered
    assert "never replace" in lowered
    assert "existing docs" in lowered


def test_build_snapshot_prompt_names_tool_latest_versions_and_storage_safety():
    prompt = build_snapshot_prompt("snapshot-2026-06-20")

    assert "lightrag-hermes" in prompt
    assert "build_latest_snapshot" in prompt
    assert "snapshot-2026-06-20" in prompt
    lowered = prompt.lower()
    assert "latest archived versions only" in lowered
    assert "never clear" in lowered
    assert "never delete" in lowered
    assert "never rotate storage" in lowered


@pytest.mark.asyncio
async def test_run_hermes_query_returns_trimmed_stdout_on_success(tmp_path):
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")
    calls = []

    async def executor(command, env):
        calls.append((command, env))
        return 0, " answer\n", ""

    result = await run_hermes_query("question", settings, executor=executor)

    assert result == {"state": "ok", "text": "answer"}
    command, env = calls[0]
    assert command[:4] == ["hermes", "chat", "--query", "question"]
    assert env["HERMES_HOME"] == str(tmp_path / "hermes")


@pytest.mark.asyncio
async def test_run_hermes_query_returns_trimmed_stderr_on_error(tmp_path):
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    async def executor(command, env):
        return 2, " ignored stdout ", " failed\n"

    result = await run_hermes_query("question", settings, executor=executor)

    assert result == {"state": "error", "message": "failed"}


@pytest.mark.asyncio
async def test_run_hermes_query_falls_back_to_stdout_on_error(tmp_path):
    settings = HermesUISettings(hermes_home=tmp_path / "hermes")

    async def executor(command, env):
        return 2, " stdout failure\n", ""

    result = await run_hermes_query("question", settings, executor=executor)

    assert result == {"state": "error", "message": "stdout failure"}


@pytest.mark.asyncio
async def test_run_hermes_query_times_out_executor(tmp_path):
    settings = HermesUISettings(
        hermes_home=Path(tmp_path / "hermes"),
        hermes_timeout_seconds=0.01,
    )

    async def executor(command, env):
        await asyncio.sleep(60)
        return 0, "late", ""

    result = await run_hermes_query("question", settings, executor=executor)

    assert result == {"state": "error", "message": "Hermes request timed out"}


@pytest.mark.asyncio
async def test_internal_subprocess_runner_kills_timed_out_process():
    code, stdout, stderr = await _run_subprocess(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        os.environ.copy(),
        timeout_seconds=0.01,
    )

    assert code == 124
    assert stdout == ""
    assert stderr == "Hermes request timed out"
