"""Basic tests for s01_agent_loop.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(override=True)

from agents.s01_agent_loop import run_bash, agent_loop


# --- run_bash ---

def test_runs_echo():
    assert run_bash("echo hello") == "hello"

def test_blocks_dangerous_command():
    assert "blocked" in run_bash("rm -rf /").lower()

def test_blocks_sudo():
    assert "blocked" in run_bash("sudo ls").lower()

def test_no_output_returns_placeholder():
    assert run_bash("true") == "(no output)"


# --- agent_loop (real API) ---

def _get_final_text(messages):
    last = messages[-1]
    if last["role"] != "assistant":
        return ""
    for block in last["content"]:
        if hasattr(block, "text"):
            return block.text
    return ""


def _used_bash(messages):
    for msg in messages:
        if msg["role"] == "assistant":
            for block in msg["content"]:
                if hasattr(block, "type") and block.type == "tool_use":
                    return True
    return False


def test_say_hi():
    messages = [{"role": "user", "content": "say hi"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[say hi] → {reply}")
    assert messages[-1]["role"] == "assistant"


def test_list_files_in_repo():
    messages = [{"role": "user", "content": "list all python files in the agents/ folder"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[list files] → {reply}")
    assert _used_bash(messages), "expected agent to use bash"
    assert "s01" in reply


def test_count_lines():
    messages = [{"role": "user", "content": "how many lines does agents/s01_agent_loop.py have?"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[count lines] → {reply}")
    assert _used_bash(messages), "expected agent to use bash"
    assert any(c.isdigit() for c in reply)


def test_simple_math_with_python():
    messages = [{"role": "user", "content": "use python to calculate 123 * 456"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[math] → {reply}")
    assert _used_bash(messages), "expected agent to use bash"
    assert "56088" in reply.replace(",", "")
