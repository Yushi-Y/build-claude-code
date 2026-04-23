"""Basic tests for s02_tool_use.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(override=True)

import pytest
from agents.s02_tool_use import (
    safe_path, run_bash, run_read, run_write, run_edit, agent_loop, WORKDIR
)


# --- safe_path ---

def test_safe_path_inside_workdir():
    p = safe_path("tests/test_s02.py")
    assert p.is_relative_to(WORKDIR)

def test_safe_path_blocks_escape():
    with pytest.raises(ValueError):
        safe_path("../../../etc/passwd")


# --- run_bash ---

def test_bash_runs():
    assert run_bash("echo hi") == "hi"

def test_bash_blocks_dangerous():
    assert "blocked" in run_bash("sudo ls").lower()


# --- run_read / run_write / run_edit ---

def test_write_then_read(tmp_path, monkeypatch):
    # use a file inside the repo so safe_path allows it
    msg = run_write("tests/_tmp_s02.txt", "hello world")
    assert "Wrote" in msg
    assert run_read("tests/_tmp_s02.txt") == "hello world"
    (WORKDIR / "tests/_tmp_s02.txt").unlink()

def test_edit_replaces_text():
    run_write("tests/_tmp_edit.txt", "foo bar")
    msg = run_edit("tests/_tmp_edit.txt", "foo", "baz")
    assert "Edited" in msg
    assert run_read("tests/_tmp_edit.txt") == "baz bar"
    (WORKDIR / "tests/_tmp_edit.txt").unlink()

def test_edit_missing_text_returns_error():
    run_write("tests/_tmp_miss.txt", "abc")
    msg = run_edit("tests/_tmp_miss.txt", "zzz", "qqq")
    assert "not found" in msg.lower()
    (WORKDIR / "tests/_tmp_miss.txt").unlink()


# --- agent_loop (real API) ---

def _get_final_text(messages):
    last = messages[-1]
    if last["role"] != "assistant":
        return ""
    for block in last["content"]:
        if hasattr(block, "text"):
            return block.text
    return ""

def _used_tool(messages, name=None):
    for msg in messages:
        if msg["role"] == "assistant":
            for block in msg["content"]:
                if hasattr(block, "type") and block.type == "tool_use":
                    if name is None or block.name == name:
                        return True
    return False


def test_agent_writes_and_reads_file():
    messages = [{"role": "user", "content":
        "create a file tests/_tmp_agent.txt with content 'hello from agent', then read it back"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[write+read] → {reply}")
    assert _used_tool(messages, "write_file") or _used_tool(messages, "bash")
    fp = WORKDIR / "tests/_tmp_agent.txt"
    if fp.exists():
        fp.unlink()


def test_agent_edits_file():
    run_write("tests/_tmp_agent_edit.txt", "the quick brown fox")
    messages = [{"role": "user", "content":
        "in tests/_tmp_agent_edit.txt replace the word 'quick' with 'slow'"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[edit] → {reply}")
    content = run_read("tests/_tmp_agent_edit.txt")
    assert "slow" in content
    (WORKDIR / "tests/_tmp_agent_edit.txt").unlink()
