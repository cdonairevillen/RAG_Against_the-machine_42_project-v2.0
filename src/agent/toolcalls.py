"""Tool calling for local chat models, whatever their convention.

Every model of the project can act as the agent, but each one declares
and calls tools its own way:
    native        the chat template takes `tools=` (Qwen3: a <tools>
                  section in the system turn, calls as <tool_call>{json}
                  </tool_call>).
    system_tools  the tools go as a JSON string in a `tools` field of the
                  system message (Phi-4-mini, an option until Phase 7:
                  <|tool|>[...]<|/tool|>, calls as
                  <|tool_call|>[...]<|/tool_call|>).
    prompt        the template knows nothing about tools: they are
                  described in the system prompt and the call format is
                  asked for in plain text (any other model).
The parser accepts every wrapper and JSON shape those produce.
"""
import ast
import json
import re
from typing import Any

SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search",
        "description": (
            "Search the knowledge base. Returns the most relevant sources "
            "of the best matching domain."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Complete, self-contained question.",
                },
                "domains": {
                    "type": "string",
                    "description": (
                        "Optional comma-separated domains to search in."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

CALL_WRAPPERS = re.compile(
    r"<tool_call>(.*?)(?:</tool_call>|$)"
    r"|<\|tool_call\|>(.*?)(?:<\|/tool_call\|>|$)",
    flags=re.DOTALL,
)

PROMPT_STYLE_HELP = (
    "\n\n# Tools\nYou can call these functions:\n{tools}\n"
    "To call one, reply with a JSON object inside <tool_call></tool_call> "
    "tags:\n<tool_call>\n{{\"name\": <function-name>, \"arguments\": "
    "<args-json-object>}}\n</tool_call>"
)


def tool_style(chat_template: str) -> str:
    """The tool convention of a chat template (see module docstring)."""
    if "message['tools']" in chat_template \
            or 'message["tools"]' in chat_template:
        return "system_tools"
    if "tools" in chat_template:
        return "native"
    return "prompt"


def render(tokenizer: Any, messages: list[dict[str, Any]],
           tools: list[dict[str, Any]]) -> str:
    """Chat prompt with the tools declared the way the model expects.

    Args:
        tokenizer: The model's tokenizer (with its chat template).
        messages: system, user, assistant and 'tool' messages.
        tools: OpenAI-style function definitions.

    Returns:
        The prompt text, ready for generation.
    """
    style = tool_style(str(tokenizer.chat_template or ""))
    messages = [dict(m) for m in messages]
    kwargs: dict[str, Any] = {
        "tokenize": False, "add_generation_prompt": True,
        # Qwen3: answer without a reasoning block; ignored elsewhere.
        "enable_thinking": False,
    }
    functions = [t["function"] for t in tools]
    if style == "native":
        kwargs["tools"] = tools
    elif style == "system_tools":
        messages[0]["tools"] = json.dumps(functions, ensure_ascii=False)
    else:
        messages[0]["content"] += PROMPT_STYLE_HELP.format(
            tools=json.dumps(functions, ensure_ascii=False, indent=1)
        )
        # Plain templates may not accept a 'tool' role.
        for message in messages:
            if message["role"] == "tool":
                message["role"] = "user"
                message["content"] = "Tool result:\n" + message["content"]
    return str(tokenizer.apply_chat_template(messages, **kwargs))


def load_json(blob: str) -> Any:
    """Parse JSON leniently (small models drift to Python literals)."""
    blob = blob.strip()
    try:
        return json.loads(blob)
    except ValueError:
        pass
    try:
        return ast.literal_eval(blob)
    except (ValueError, SyntaxError):
        return None


def normalise(call: Any) -> list[dict[str, Any]]:
    """{name, arguments} dicts from one decoded tool-call payload."""
    if isinstance(call, list):
        return [c for item in call for c in normalise(item)]
    if not isinstance(call, dict):
        return []
    if isinstance(call.get("function"), dict):
        call = call["function"]
    name = call.get("name")
    arguments = call.get("arguments", call.get("parameters", {}))
    if isinstance(arguments, str):
        arguments = load_json(arguments) or {}
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return []
    return [{"name": name, "arguments": arguments}]


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Tool calls in a model's raw output, in order.

    Accepts <tool_call>...</tool_call>, <|tool_call|>...<|/tool_call|>
    (closing tag optional, outputs get cut) and a bare JSON object or
    list as the whole answer.

    Returns:
        [{"name": str, "arguments": dict}, ...]; [] when there is none.
    """
    calls: list[dict[str, Any]] = []
    for match in CALL_WRAPPERS.finditer(text):
        payload = match.group(1) if match.group(1) is not None \
            else match.group(2)
        calls.extend(normalise(load_json(payload or "")))
    if calls:
        return calls
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        return normalise(load_json(stripped))
    return []
