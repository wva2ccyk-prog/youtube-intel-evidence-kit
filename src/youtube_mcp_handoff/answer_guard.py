from __future__ import annotations

from typing import Any

FORBIDDEN_PHRASES: tuple[str, ...] = (
    "fact checked",
    "verified true",
    "truth-ranked result",
    "사실로 판명",
    "정답",
    "거짓으로 판명",
)

REQUIRED_EXPRESSIONS: tuple[str, ...] = (
    "synthetic fixture",
    "caption fragment claim risk",
    "not truth-ranked",
    "not fact-checked",
)

REQUIRED_LIMITATION_FIELDS: tuple[str, ...] = (
    "synthetic_fixture_only",
    "caption_fragment_claim_risk",
    "not truth-ranked",
    "not fact-checked",
)


def validate_public_demo_answer(answer: str) -> list[str]:
    errors: list[str] = []
    lower = answer.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in lower:
            errors.append(f"forbidden_phrase:{phrase}")
    for expr in REQUIRED_EXPRESSIONS:
        if expr.lower() not in lower:
            errors.append(f"missing_required:{expr}")
    return errors


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_text(v) for v in value)
    return str(value)


def validate_public_demo_answer_payload(payload: dict[str, Any]) -> list[str]:
    """Validate structured AI-app answers before user display.

    The string guard remains for backward compatibility. This structured guard is
    stricter: user-facing payloads must carry a limitations list instead of only
    relying on a prose disclaimer that a model may paraphrase away.
    """
    errors: list[str] = []
    answer_text = _flatten_text(payload.get("answer") or payload.get("content") or payload.get("text") or "")
    lower = answer_text.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in lower:
            errors.append(f"forbidden_phrase:{phrase}")

    limitations = payload.get("limitations") or payload.get("limitations_display") or []
    limitation_text = " ".join(str(item).lower() for item in limitations) if isinstance(limitations, list) else ""
    if not isinstance(limitations, list):
        errors.append("limitations_not_list")
        limitation_text = ""
    for required in REQUIRED_LIMITATION_FIELDS:
        if required.lower() not in limitation_text:
            errors.append(f"missing_limitation:{required}")
    return errors
