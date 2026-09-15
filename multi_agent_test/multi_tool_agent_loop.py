"""
Claude API client with two tools:
  1. calculator  - evaluates a math expression, returns the result
  2. web_search  - real web search via DuckDuckGo (ddgs)

Setup:
    pip install anthropic ddgs
    python multi_tool_agent_loop.py
    (model + auth token are read from .claude/settings.json)
"""

import ast
import operator
import os
import json

from anthropic import Anthropic

# Load model/auth config from .claude/settings.json (repo root)
_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude",
    "settings.json",
)


def _load_env_settings() -> dict:
    """Read the 'env' block from .claude/settings.json."""
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("env", {})


_ENV = _load_env_settings()

MODEL = _ENV["ANTHROPIC_MODEL"]

client = Anthropic(
    auth_token=_ENV["ANTHROPIC_AUTH_TOKEN"],
    base_url=_ENV.get("ANTHROPIC_BASE_URL"),
)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

# Safe arithmetic evaluator (no eval()). Supports + - * / // % ** and parens.
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def calculator(expression: str) -> dict:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web via DuckDuckGo and return real results.

    Uses DuckDuckGo (ddgs) because it needs no API key/account, so it works
    without external credentials. Wrapped in try/except so a network failure
    or rate-limit degrades to an {"error": ...} result instead of crashing
    the agent loop.
    """
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=max_results)
        return {
            "query": query,
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"query": query, "error": str(e)}


TOOL_IMPLEMENTATIONS = {
    "calculator": lambda inp: calculator(inp["expression"]),
    "web_search": lambda inp: web_search(inp["query"]),
}


# ---------------------------------------------------------------------------
# Tool schemas (sent to the API)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "calculator",
        "description": (
            "Evaluate a basic arithmetic expression (+, -, *, /, //, %, **, "
            "parentheses) and return the numeric result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The math expression to evaluate, e.g. '(3 + 4) * 2'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for a query and return real results (title, url, "
            "snippet) via DuckDuckGo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                }
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------

def run(user_message: str, max_turns: int = 5) -> str:
    messages = [{"role": "user", "content": user_message}]
    turns = 0

    while turns < max_turns:
        turns += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )
        print(f"response - {response}")
        messages.append({"role": "assistant", "content": response.content})

        stop_reason = response.stop_reason

        if stop_reason == "tool_use":
            # Extract every tool_use block Claude asked for in this turn
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            tool_results = []
            for block in tool_use_blocks:
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                impl = TOOL_IMPLEMENTATIONS.get(tool_name)
                is_error = False

                if impl is None:
                    output = {"error": f"Unknown tool: {tool_name}"}
                    is_error = True
                else:
                    try:
                        output = impl(tool_input)
                    except Exception as e:
                        # Malformed input, missing key, runtime failure, etc.
                        output = {"error": f"{type(e).__name__}: {e}"}
                        is_error = True

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(output),
                    "is_error": is_error,
                })

            # Hand results back to Claude as a user turn, so it can continue
            messages.append({"role": "user", "content": tool_results})
            continue

        elif stop_reason == "end_turn":
            return "".join(b.text for b in response.content if b.type == "text")

        elif stop_reason == "max_tokens":
            partial = "".join(b.text for b in response.content if b.type == "text")
            return partial + "\n[response truncated: hit max_tokens]"

        elif stop_reason == "stop_sequence":
            return "".join(b.text for b in response.content if b.type == "text")

        else:
            # pause_turn, refusal, or any other/unexpected value
            return f"Stopped unexpectedly (stop_reason={stop_reason})"

    return "Max turns reached without a final answer."


if __name__ == "__main__":
    print(run("What is (5 + 5) * 3? Also, search for 'best pizza in Kharadi, Pune'."))