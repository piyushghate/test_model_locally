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

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        # Append Claude's turn (may contain text + tool_use blocks) as-is.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            # Final answer — collect any text blocks.
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        # Handle every tool_use block in this turn, build tool_result content.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            impl = TOOL_IMPLEMENTATIONS.get(block.name)
            if impl is None:
                output = {"error": f"Unknown tool: {block.name}"}
            else:
                output = impl(block.input)

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output),
                }
            )

        messages.append({"role": "user", "content": tool_results})

    return "Max turns reached without a final answer."


if __name__ == "__main__":
    print(run("What is (5 + 5) * 3? Also, search for 'best pizza in Balewadi, Pune'."))