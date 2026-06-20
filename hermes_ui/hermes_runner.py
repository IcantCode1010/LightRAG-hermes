import asyncio
import os
from collections.abc import Awaitable, Callable

from hermes_ui.config import HermesUISettings


HermesCommand = list[str]
HermesEnv = dict[str, str]
HermesExecutor = Callable[[HermesCommand, HermesEnv], Awaitable[tuple[int, str, str]]]


def build_chat_command(
    prompt: str, settings: HermesUISettings
) -> tuple[HermesCommand, HermesEnv]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(settings.hermes_home)
    return (
        [
            "hermes",
            "chat",
            "--query",
            prompt,
            "--quiet",
            "--max-turns",
            "8",
        ],
        env,
    )


def build_ingest_prompt(
    document_key: str,
    version_label: str,
    title: str,
    text: str,
) -> str:
    return f"""Use the lightrag-hermes MCP tool ingest_text_version.

Call the tool with exactly these field names:
document_key: {document_key}
version_label: {version_label}
title: {title}
text: {text}

Safety rules:
- Never delete existing docs.
- Never clear existing docs.
- Never overwrite existing docs.
- Never replace existing docs.
- Only ingest this text as a new archived version for the document key.
"""


def build_snapshot_prompt(snapshot_id: str) -> str:
    return f"""Use the lightrag-hermes MCP tool build_latest_snapshot.

Build snapshot_id: {snapshot_id}

Build from latest archived versions only. Never clear storage, never delete
storage, and never rotate storage.
"""


async def run_hermes_query(
    prompt: str,
    settings: HermesUISettings,
    executor: HermesExecutor | None = None,
) -> dict[str, str]:
    command, env = build_chat_command(prompt, settings)
    if executor is None:
        code, stdout, stderr = await _run_subprocess(
            command,
            env,
            settings.hermes_timeout_seconds,
        )
    else:
        try:
            code, stdout, stderr = await asyncio.wait_for(
                executor(command, env),
                timeout=settings.hermes_timeout_seconds,
            )
        except TimeoutError:
            code, stdout, stderr = 124, "", "Hermes request timed out"

    if code == 0:
        return {"state": "ok", "text": stdout.strip()}
    return {"state": "error", "message": (stderr or stdout).strip()}


async def _run_subprocess(
    command: HermesCommand,
    env: HermesEnv,
    timeout_seconds: float,
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        await process.communicate()
        return 124, "", "Hermes request timed out"
    return (
        process.returncode or 0,
        stdout_bytes.decode(errors="replace"),
        stderr_bytes.decode(errors="replace"),
    )
