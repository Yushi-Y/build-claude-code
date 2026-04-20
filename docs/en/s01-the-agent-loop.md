# s01: The Agent Loop

`[ s01 ] s02 > s03 > s04 > s05 > s06 | s07 > s08 > s09 > s10 > s11 > s12`

> *"One loop & Bash is all you need"* -- one tool + one loop = an agent.
>
> **Harness layer**: The loop -- the model's first connection to the real world.

## Problem

A language model can reason about code, but it can't *touch* the real world -- can't read files, run tests, or check errors. Without a loop, every tool call requires you to manually copy-paste results back. You become the loop.

## Solution

```
+--------+      +-------+      +---------+
|  User  | ---> |  LLM  | ---> |  Tool   |
| prompt |      |       |      | execute |
+--------+      +---+---+      +----+----+
                    ^                |
                    |   tool_result  |
                    +----------------+
                    (loop until stop_reason != "tool_use")
```

One exit condition controls the entire flow. The loop runs until the model stops calling tools.

## How It Works

1. User prompt becomes the first message.

```python
messages.append({"role": "user", "content": query})
```

2. Send messages + tool definitions to the LLM.

```python
response = client.messages.create(
    model=MODEL, system=SYSTEM, messages=messages,
    tools=TOOLS, max_tokens=8000,
)
```

3. Append the assistant response. Check `stop_reason` -- if the model didn't call a tool, we're done.

```python
messages.append({"role": "assistant", "content": response.content})
if response.stop_reason != "tool_use":
    return
```

4. Execute each tool call, collect results, append as a user message. Loop back to step 2.

```python
results = []
for block in response.content:
    if block.type == "tool_use":
        output = run_bash(block.input["command"])
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output,
        })
messages.append({"role": "user", "content": results})
```

Assembled into one function:

```python
def agent_loop(query):
    messages = [{"role": "user", "content": query}]
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = run_bash(block.input["command"])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
        messages.append({"role": "user", "content": results})
```

That's the entire agent in under 30 lines. Everything else in this course layers on top -- without changing the loop.

## What Changed

| Component     | Before     | After                          |
|---------------|------------|--------------------------------|
| Agent loop    | (none)     | `while True` + stop_reason     |
| Tools         | (none)     | `bash` (one tool)              |
| Messages      | (none)     | Accumulating list              |
| Control flow  | (none)     | `stop_reason != "tool_use"`    |

## Try It

```sh
cd learn-claude-code
python agents/s01_agent_loop.py
```

1. `Create a file called hello.py that prints "Hello, World!"`
2. `List all Python files in this directory`
3. `What is the current git branch?`
4. `Create a directory called test_output and write 3 files in it`

## Full Trace: "use python to calculate 123 * 456"

Two API calls. Two loop iterations. Here's exactly what `messages` looks like at every step.

**Step 1 — user input appended:**
```python
messages = [
    {"role": "user", "content": "use python to calculate 123 * 456"}
]
```

**Step 2 — first API call to Claude.**

**Step 3 — Claude responds with a `tool_use` block** (just structured JSON output — Claude executes nothing):
```python
response.stop_reason = "tool_use"
response.content = [
    ToolUseBlock(type="tool_use", id="toolu_01ABC", name="bash",
                 input={"command": "python3 -c 'print(123 * 456)'"})
]
```

**Step 4 — harness appends assistant turn:**
```python
messages = [
    {"role": "user",      "content": "use python to calculate 123 * 456"},
    {"role": "assistant", "content": [ToolUseBlock(id="toolu_01ABC", ...)]}
]
```

**Step 5 — `stop_reason == "tool_use"` so loop continues. Harness runs the command:**
```python
run_bash("python3 -c 'print(123 * 456)'")  # → "56088"
```

**Step 6 — harness appends tool result as a user message:**
```python
messages = [
    {"role": "user",      "content": "use python to calculate 123 * 456"},
    {"role": "assistant", "content": [ToolUseBlock(id="toolu_01ABC", ...)]},
    {"role": "user",      "content": [
        {"type": "tool_result", "tool_use_id": "toolu_01ABC", "content": "56088"}
    ]}
]
```

**Step 7 — second API call to Claude** with full updated messages.

**Step 8 — Claude sees `"56088"` in context, responds with text:**
```python
response.stop_reason = "end_turn"
response.content = [TextBlock(text="The result of 123 × 456 = 56,088")]
```

**Step 9 — harness appends final response, `stop_reason != "tool_use"` so loop exits:**
```python
messages = [
    {"role": "user",      "content": "use python to calculate 123 * 456"},
    {"role": "assistant", "content": [ToolUseBlock(...)]},
    {"role": "user",      "content": [{"type": "tool_result", "content": "56088"}]},
    {"role": "assistant", "content": [TextBlock(text="The result of 123 × 456 = 56,088")]}
]
```

**Step 10 — REPL prints the last text block:**
```
The result of 123 × 456 = 56,088
```

Claude never executes code. It only outputs a `tool_use` block describing what it wants run.
Your harness reads that block, runs it, and feeds the result back as the next message.
