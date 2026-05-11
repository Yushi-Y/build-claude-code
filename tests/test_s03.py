"""Basic tests for s03_todo_write.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(override=True)

import pytest
from agents.s03_todo_write import TodoManager, TODO, agent_loop, WORKDIR


# --- TodoManager ---

def test_empty_render():
    tm = TodoManager()
    assert tm.render() == "No todos."

def test_update_and_render():
    tm = TodoManager()
    out = tm.update([
        {"id": "1", "text": "do A", "status": "pending"},
        {"id": "2", "text": "do B", "status": "in_progress"},
    ])
    assert "[ ] #1: do A" in out
    assert "[>] #2: do B" in out
    assert "(0/2 completed)" in out

def test_completed_count():
    tm = TodoManager()
    out = tm.update([
        {"id": "1", "text": "A", "status": "completed"},
        {"id": "2", "text": "B", "status": "completed"},
        {"id": "3", "text": "C", "status": "pending"},
    ])
    assert "(2/3 completed)" in out

def test_max_20():
    tm = TodoManager()
    items = [{"id": str(i), "text": f"t{i}", "status": "pending"} for i in range(21)]
    with pytest.raises(ValueError, match="Max 20"):
        tm.update(items)

def test_only_one_in_progress():
    tm = TodoManager()
    with pytest.raises(ValueError, match="in_progress"):
        tm.update([
            {"id": "1", "text": "A", "status": "in_progress"},
            {"id": "2", "text": "B", "status": "in_progress"},
        ])

def test_empty_text_rejected():
    tm = TodoManager()
    with pytest.raises(ValueError, match="text required"):
        tm.update([{"id": "1", "text": "", "status": "pending"}])

def test_invalid_status_rejected():
    tm = TodoManager()
    with pytest.raises(ValueError, match="invalid status"):
        tm.update([{"id": "1", "text": "A", "status": "done"}])

def test_atomic_update_on_failure():
    """If validation fails partway, state must not change."""
    tm = TodoManager()
    tm.update([{"id": "1", "text": "original", "status": "pending"}])
    with pytest.raises(ValueError):
        tm.update([
            {"id": "1", "text": "new", "status": "pending"},
            {"id": "2", "text": "", "status": "pending"},  # invalid
        ])
    # original state preserved
    assert tm.items[0]["text"] == "original"


# --- agent_loop (real API) ---

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


@pytest.fixture(autouse=True)
def reset_todo():
    """Clear global TODO state before each real-API test."""
    TODO.items = []
    yield
    TODO.items = []


def test_refactor_hello_uses_todo():
    """Multi-step refactor — agent should plan with todos."""
    # Arrange: create the file the agent will refactor
    fp = WORKDIR / "tests/_tmp_hello.py"
    fp.write_text("def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n")

    messages = [{"role": "user", "content":
        "Refactor the file tests/_tmp_hello.py: add type hints, docstrings, and a main guard"}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[refactor] → {reply[:300]}")

    assert _used_tool(messages, "todo"), "expected agent to plan with todo"
    content = fp.read_text()
    assert "->" in content or "->" in content or ":" in content  # some type-hint-ish syntax
    assert '__name__' in content  # main guard
    fp.unlink()


def test_create_package_uses_todo():
    """Multi-file creation — agent should plan with todos."""
    pkg_dir = WORKDIR / "tests/_tmp_pkg"

    messages = [{"role": "user", "content":
        "Create a Python package at tests/_tmp_pkg/ with three files: "
        "__init__.py, utils.py (containing a function `square(x)` that returns x*x), "
        "and tests/test_utils.py inside it. Use the todo tool to plan."}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[create pkg] → {reply[:300]}")

    assert _used_tool(messages, "todo"), "expected agent to plan with todo"
    assert (pkg_dir / "__init__.py").exists()
    assert (pkg_dir / "utils.py").exists()

    # cleanup
    import shutil
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)


def test_review_files_uses_todo():
    """Multi-file review — agent should plan with todos."""
    d = WORKDIR / "tests/_tmp_review"
    d.mkdir(exist_ok=True)
    (d / "a.py").write_text("x=1\ny =2\n")  # style issues: missing space, weird spacing
    (d / "b.py").write_text("def foo( ):\n    pass\n")  # space in args

    messages = [{"role": "user", "content":
        "Review all Python files in tests/_tmp_review/ and fix any style issues. Use the todo tool to plan."}]
    agent_loop(messages)
    reply = _get_final_text(messages)
    print(f"\n[review] → {reply[:300]}")

    assert _used_tool(messages, "todo"), "expected agent to plan with todo"

    import shutil
    if d.exists():
        shutil.rmtree(d)
