import io
import json
import urllib.error

import pytest

from hnlearn import ollama


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, path, body, timeout):
        self.calls.append((path, body, timeout))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_systemone_returns_answers_and_sends_schema():
    t = FakeTransport([{"model": "clef-flash", "answers": {"q": {"type": "noul", "noul": 0.9}},
                        "usage": {"input_tokens": 10, "output_tokens": 0}}])
    out = ollama.systemone("clef-flash", "state", {"q": {"type": "noul", "instructions": "?"}},
                           transport=t)
    assert out.answers["q"]["noul"] == 0.9 and out.usage["input_tokens"] == 10
    path, body, _ = t.calls[0]
    assert path == "/v1/systemone" and body["model"] == "clef-flash" and body["state"] == "state"
    assert body["keep_alive"]


def test_systemone_rejects_missing_answers():
    t = FakeTransport([{"model": "clef-flash"}])
    with pytest.raises(ollama.OllamaError, match="answers"):
        ollama.systemone("clef-flash", "s", {"q": {"type": "noul", "instructions": "?"}},
                         transport=t)


def test_chat_json_parses_content_and_sets_options():
    content = json.dumps({"title": "T", "blurb": "B"})
    t = FakeTransport([{"message": {"role": "assistant", "content": content},
                        "prompt_eval_count": 50, "eval_count": 20}])
    out = ollama.chat_json("qwen3:30b-a3b", "sys", "user", {"type": "object"}, transport=t)
    assert out.data == {"title": "T", "blurb": "B"}
    assert out.usage == {"input_tokens": 50, "output_tokens": 20}
    _, body, _ = t.calls[0]
    assert body["think"] is False and body["stream"] is False
    assert body["options"]["temperature"] == 0 and body["format"] == {"type": "object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]


def test_chat_json_rejects_invalid_json():
    t = FakeTransport([{"message": {"content": "not json"}}])
    with pytest.raises(ollama.OllamaError, match="not valid JSON"):
        ollama.chat_json("m", "s", "u", {}, transport=t)


def test_http_error_becomes_ollama_error():
    err = urllib.error.HTTPError("http://x", 400, "Bad", {}, io.BytesIO(b'{"error":"bad schema"}'))
    t = FakeTransport([err])
    with pytest.raises(ollama.OllamaError, match="400.*bad schema"):
        ollama.systemone("m", "s", {"q": {"type": "noul", "instructions": "?"}}, transport=t)


def test_connection_error_becomes_ollama_error():
    t = FakeTransport([urllib.error.URLError("Connection refused")])
    with pytest.raises(ollama.OllamaError, match="Connection refused"):
        ollama.chat_json("m", "s", "u", {}, transport=t)
