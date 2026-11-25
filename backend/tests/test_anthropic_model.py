"""The Claude adapter against a stub client. No live call."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from atlas.pipeline.stages import StageError
from atlas.providers.anthropic_model import AnthropicExtractionModel, supported_schema
from atlas.providers.base import TextBlock, ToolCall

TOOL = {
    "name": "record",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"confidence": {"type": "number", "minimum": 0, "maximum": 1}},
    },
}


class StubStream:
    def __init__(self, message: Any) -> None:
        self._message = message

    def __enter__(self) -> "StubStream":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_final_message(self) -> Any:
        if isinstance(self._message, Exception):
            raise self._message
        return self._message


class StubClient:
    def __init__(self, message: Any) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        outer = self

        class Messages:
            def __init__(self, name: str) -> None:
                self._name = name

            def stream(self, **params: Any) -> StubStream:
                outer.calls.append((self._name, params))
                return StubStream(message)

        self.messages = Messages("messages")
        self.beta = SimpleNamespace(messages=Messages("beta"))


def message(text: str | None, stop_reason: str = "end_turn") -> Any:
    content = [SimpleNamespace(type="thinking", thinking="")]
    if text is not None:
        content.append(SimpleNamespace(type="text", text=text))
    usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        cache_read_input_tokens=7,
        cache_creation_input_tokens=None,
    )
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, model="claude-sonnet-5-5", usage=usage
    )


def request(model: str = "claude-sonnet-5-5") -> ToolCall:
    system = [TextBlock("instructions"), TextBlock("an invented transcript", cache=True)]
    return ToolCall(model, system, [TextBlock("window")], TOOL)


def adapter(client: StubClient, **kwargs: Any) -> AnthropicExtractionModel:
    return AnthropicExtractionModel(
        None, effort_model="claude-sonnet-5-5", effort="medium", client=client, **kwargs
    )


def test_request_uses_structured_output_caching_and_fallbacks() -> None:
    client = StubClient(message('{"confidence": 0.5}'))
    result = adapter(client).call(request())

    assert result.data == {"confidence": 0.5}
    assert result.usage == {
        "input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 0,
    }  # fmt: skip
    name, params = client.calls[0]
    assert name == "beta" and params["fallbacks"] == "default"
    assert params["betas"] == ["server-side-fallback-2026-07-01"]
    assert "tools" not in params and "tool_choice" not in params and "thinking" not in params
    schema = params["output_config"]["format"]["schema"]
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert schema["properties"]["confidence"] == {"type": "number"}
    assert params["output_config"]["effort"] == "medium"
    assert params["system"][0] == {"type": "text", "text": "instructions"}
    assert params["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert params["max_tokens"] >= 16000


def test_the_small_model_gets_no_fallback_and_no_effort_override() -> None:
    client = StubClient(message("{}"))
    adapter(client).call(request("claude-haiku-5-5"))
    name, params = client.calls[0]
    assert name == "messages" and "fallbacks" not in params
    assert "effort" not in params["output_config"]


@pytest.mark.parametrize(
    ("reply", "code", "retryable"),
    [
        (message(None, "refusal"), "model_refused", False),
        (message('{"a":', "max_tokens"), "model_output_truncated", False),
        (message("not json"), "model_output_invalid", True),
        (message("[1, 2]"), "model_output_invalid", True),
    ],
)
def test_bad_answers_become_codes(reply: Any, code: str, retryable: bool) -> None:
    with pytest.raises(StageError) as error:
        adapter(StubClient(reply)).call(request())
    assert (error.value.code, error.value.retryable) == (code, retryable)


def api_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    response = httpx2.Response(
        status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    return cls("an invented error with private words", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (api_error(anthropic.AuthenticationError, 401), "model_auth_failed", False),
        (api_error(anthropic.RateLimitError, 429), "model_unavailable", True),
        (api_error(anthropic.InternalServerError, 503), "model_unavailable", True),
        (api_error(anthropic.BadRequestError, 400), "model_rejected_request", False),
    ],
)
def test_api_errors_become_codes(error: Exception, code: str, retryable: bool) -> None:
    with pytest.raises(StageError) as raised:
        adapter(StubClient(error)).call(request())
    assert (raised.value.code, raised.value.retryable) == (code, retryable)
    assert "private" not in str(raised.value)


def test_unsupported_constraints_are_removed_everywhere() -> None:
    schema = {
        "type": "array",
        "minItems": 1,
        "items": {"type": "string", "maxLength": 5, "enum": ["a"]},
    }
    assert supported_schema(schema) == {"type": "array", "items": {"type": "string", "enum": ["a"]}}
