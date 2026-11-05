"""Minimal Ollama HTTP client: decision calls (systemone) and JSON chat calls.

Every failure becomes ``OllamaError`` with the server's message, so stages can record
it per row and move on. The transport is injectable for tests.
"""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hnlearn import config

Transport = Callable[[str, dict[str, Any], float], dict[str, Any]]


class OllamaError(Exception):
    """Any failure talking to Ollama or parsing its reply."""


@dataclass(frozen=True)
class Decision:
    answers: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatJson:
    data: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)


def post(path: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST JSON to the local Ollama server and return the parsed reply (raw urllib errors)."""
    req = urllib.request.Request(config.OLLAMA_URL + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed local URL
        reply = json.loads(resp.read())
    if not isinstance(reply, dict):
        raise ValueError(f"{path}: reply is not a JSON object")
    return reply


def _call(transport: Transport | None, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run the transport and translate every failure into OllamaError."""
    try:
        return (transport or post)(path, body, config.OLLAMA_TIMEOUT_S)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise OllamaError(f"HTTP {e.code} from {path}: {detail}") from e
    except urllib.error.URLError as e:
        raise OllamaError(f"cannot reach Ollama at {config.OLLAMA_URL}: {e.reason}") from e
    except (http.client.HTTPException, ValueError, TimeoutError, OSError) as e:
        raise OllamaError(f"{path}: {type(e).__name__}: {e}") from e


def systemone(model: str, state: str, questions: dict[str, Any], *, keep_alive: str = "10m",
              transport: Transport | None = None) -> Decision:
    """Score ``questions`` against ``state`` with a decision model."""
    body = {"model": model, "state": state, "questions": questions, "keep_alive": keep_alive}
    reply = _call(transport, "/v1/systemone", body)
    answers = reply.get("answers")
    if not isinstance(answers, dict):
        raise OllamaError("systemone reply has no answers object")
    return Decision(answers=answers, usage=reply.get("usage") or {})


def chat_json(model: str, system: str, user: str, schema: dict[str, Any], *,
              think: bool = False, num_ctx: int = 8192, keep_alive: str = "10m",
              transport: Transport | None = None) -> ChatJson:
    """One chat turn with a JSON-schema constrained reply, parsed."""
    body = {"model": model, "stream": False, "think": think, "format": schema,
            "options": {"temperature": 0, "num_ctx": num_ctx}, "keep_alive": keep_alive,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    reply = _call(transport, "/api/chat", body)
    content = (reply.get("message") or {}).get("content", "")
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise OllamaError(f"chat reply is not valid JSON: {content[:200]!r}") from e
    if not isinstance(data, dict):
        raise OllamaError("chat reply JSON is not an object")
    usage = {"input_tokens": reply.get("prompt_eval_count"),
             "output_tokens": reply.get("eval_count")}
    return ChatJson(data=data, usage=usage)
