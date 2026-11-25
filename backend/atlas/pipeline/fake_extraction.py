"""Default answers for the fake extraction model.

Deterministic stand-ins for model output, so the whole pipeline runs with no outside
call. They are rule-of-thumb heuristics, not extraction quality; quality is
measured by `make eval` against the live model.
"""

from typing import Any

from atlas.providers.base import ToolCall
from atlas.providers.fakes import Handler


def fake_speaker_roles(request: ToolCall) -> dict[str, Any]:
    """The voice that asks more questions is the therapist."""
    turns: dict[str, list[str]] = request.context["turns"]
    if len(turns) < 2:
        return {
            "assignments": [{"label": label, "role": "self"} for label in turns],
            "confidence": 0.99,
        }
    questions = {
        label: sum(text.count("?") for text in texts) / max(len(texts), 1)
        for label, texts in turns.items()
    }
    ranked = sorted(questions, key=lambda label: (-questions[label], label))
    therapist, owner = ranked[0], ranked[1]
    gap = questions[therapist] - questions[owner]
    assignments = [{"label": therapist, "role": "therapist"}, {"label": owner, "role": "self"}]
    assignments += [{"label": label, "role": "other"} for label in ranked[2:]]
    return {"assignments": assignments, "confidence": 0.95 if gap >= 0.3 else 0.6}


def default_handlers() -> dict[str, Handler]:
    return {"speaker_roles": fake_speaker_roles}
