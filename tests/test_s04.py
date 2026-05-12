"""Basic tests for s04_subagent.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(override=True)

import shutil
import pytest
from agents.s04_subagent import (
    CHILD_TOOLS, PARENT_TOOLS, run_subagent, agent_loop, WORKDIR
)


# --- structural invariants ---

def test_child_has_no_task_tool():
    """Children cannot recursively spawn subagents."""
    names = [t["name"] for t in CHILD_TOOLS]
    assert "task" not in names

def test_parent_has_task_tool():
    """Only the parent can dispatch subtasks."""
    names = [t["name"] for t in PARENT_TOOLS]
    assert "task" in names

def test_parent_tools_extend_child_tools():
    """PARENT_TOOLS = CHILD_TOOLS + [task]."""
    child_names = {t["name"] for t in CHILD_TOOLS}
    parent_names = {t["name"] for t in PARENT_TOOLS}
    assert child_names.issubset(parent_names)
    assert parent_names - child_names == {"task"}


# --- helpers (same shape as s02/s03 tests) ---

def _get_final_text(messages):
    last = messages[-1]
    if last["role"] != "assistant":
        return ""
    for block in last["content"]:
        if hasattr(block, "text"):
            return block.text
    return ""

def _used_tool(messages, name):
    for msg in messages:
        if msg["role"] == "assistant":
            for block in msg["content"]:
                if hasattr(block, "type") and block.type == "tool_use" and block.name == name:
                    return True
    return False


# --- run_subagent (real API) ---

def test_subagent_returns_summary_string():
    """Trivial prompt — child should produce a non-empty text summary."""
    out = run_subagent("Say the single word HELLO and stop. No tools needed.")
    print(f"\n[subagent direct] → {out!r}")
    assert isinstance(out, str)
    assert "HELLO" in out.upper()


# --- agent_loop with `task` dispatch (real API) ---

def test_subtask_finds_testing_framework():
    """Prompt 1: Use a subtask to find what testing framework this project uses."""
    messages = [{"role": "user", "content":
        "Use a subtask to find what testing framework this project uses. "
        "Look at requirements.txt and the tests/ directory."}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[find framework] → {reply[:300]}")

    assert _used_tool(messages, "task"), "expected parent to delegate via task"
    assert "pytest" in reply.lower()


def test_subtask_summarizes_py_files():
    """Prompt 2: Delegate reading and summarizing .py files."""
    d = WORKDIR / "tests/_tmp_s04_summarize"
    d.mkdir(exist_ok=True)
    (d / "math_utils.py").write_text("def square(x):\n    return x * x\n")
    (d / "string_utils.py").write_text("def shout(s):\n    return s.upper()\n")
    (d / "io_utils.py").write_text("def load(p):\n    return open(p).read()\n")

    try:
        messages = [{"role": "user", "content":
            f"Delegate to a subtask: read all .py files in {d.relative_to(WORKDIR)} "
            "and summarize what each one does in one sentence."}]
        agent_loop(messages)
        reply = _get_final_text(messages)
        print(f"\n[summarize py] → {reply[:400]}")

        assert _used_tool(messages, "task"), "expected parent to delegate via task"
        lower = reply.lower()
        # all three filenames (or their stems) should appear in the summary
        assert "math" in lower
        assert "string" in lower
        assert "io" in lower
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_subtask_creates_module_and_parent_verifies():
    """Prompt 3: Use a task to create a new module, then verify it from here."""
    target = WORKDIR / "tests/_tmp_s04_module.py"
    if target.exists():
        target.unlink()

    try:
        messages = [{"role": "user", "content":
            f"Use a task to create a new Python module at {target.relative_to(WORKDIR)} "
            "with a function `greet(name)` that returns f'Hello, {name}!'. "
            "Then verify it from here by reading the file back."}]
        agent_loop(messages)
        reply = _get_final_text(messages)
        print(f"\n[create+verify] → {reply[:300]}")

        # parent delegated creation
        assert _used_tool(messages, "task"), "expected parent to delegate via task"
        # parent verified the result itself (not inside the child)
        assert _used_tool(messages, "read_file") or _used_tool(messages, "bash"), \
            "expected parent to verify after the subtask"
        # file actually exists with the right function
        assert target.exists(), "expected module file to be created"
        content = target.read_text()
        assert "def greet" in content
        assert "Hello" in content
    finally:
        if target.exists():
            target.unlink()
