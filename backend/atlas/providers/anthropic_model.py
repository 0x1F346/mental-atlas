"""Claude adapter for schema-constrained extraction calls.

Checked against the Anthropic API documentation on 2026-11-25. Current models
reject forced tool use, so the schema is enforced with structured outputs
(`output_config.format`) rather than a forced tool call. Requests are streamed so
long outputs do not hit HTTP timeouts. Code still validates everything returned.
"""

import json
from typing import Any

import anthropic

from atlas.pipeline.stages import StageError
from atlas.providers.base import ToolCall, ToolResult

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MIN_MAX_TOKENS = 16000
# Constraints structured outputs does not accept; code enforces them after the call.
_UNSUPPORTED = frozenset({"minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength"})


def supported_schema(schema: Any) -> Any:
    """A copy of a JSON schema without the constraints structured outputs rejects."""
    if isinstance(schema, dict):
        return {k: supported_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED}
    if isinstance(schema, list):
        return [supported_schema(item) for item in schema]
    return schema


class AnthropicExtractionModel:
    def __init__(
        self,
        api_key: str | None,
        *,
        effort_model: str,
        effort: str,
        fallbacks: bool = True,
        client: Any | None = None,
    ) -> None:
        self._client = client or anthropic.Anthropic(api_key=api_key, max_retries=3)
        self._effort_model = effort_model
        self._effort = effort
        self._fallbacks = fallbacks

    def call(self, request: ToolCall) -> ToolResult:
        output_config: dict[str, Any] = {
            "format": {
                "type": "json_schema",
                "schema": supported_schema(request.tool["input_schema"]),
            }
        }
        if request.model == self._effort_model:
            output_config["effort"] = self._effort
        params: dict[str, Any] = {
            "model": request.model,
            "max_tokens": max(request.max_tokens, MIN_MAX_TOKENS),
            "system": [
                {"type": "text", "text": block.text}
                | ({"cache_control": {"type": "ephemeral"}} if block.cache else {})
                for block in request.system
            ],
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": b.text} for b in request.user],
                }
            ],
            "output_config": output_config,
        }
        # A declined request is retried server-side on the recommended fallback model.
        # Haiku has no server-side fallback.
        use_fallback = self._fallbacks and "haiku" not in request.model
        manager: Any
        try:
            if use_fallback:
                manager = self._client.beta.messages.stream(
                    betas=[FALLBACK_BETA], fallbacks="default", **params
                )
            else:
                manager = self._client.messages.stream(**params)
            with manager as stream:
                message: Any = stream.get_final_message()
        except anthropic.AuthenticationError as error:
            raise StageError("model_auth_failed") from error
        except anthropic.PermissionDeniedError as error:
            raise StageError("model_auth_failed") from error
        except anthropic.RateLimitError as error:
            raise StageError("model_unavailable", retryable=True) from error
        except anthropic.APIStatusError as error:
            if error.status_code >= 500:
                raise StageError("model_unavailable", retryable=True) from error
            raise StageError("model_rejected_request") from error
        except anthropic.APIConnectionError as error:
            raise StageError("model_unavailable", retryable=True) from error

        if message.stop_reason == "refusal":
            raise StageError("model_refused")
        if message.stop_reason == "max_tokens":
            raise StageError("model_output_truncated")
        text = next((block.text for block in message.content if block.type == "text"), None)
        try:
            data = json.loads(text) if text else None
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            raise StageError("model_output_invalid", retryable=True)
        usage = {
            name: int(getattr(message.usage, name, 0) or 0)
            for name in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
        }
        return ToolResult(data=data, model=str(message.model), usage=usage)
