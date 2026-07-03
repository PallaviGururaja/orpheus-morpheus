"""Standalone follow-up-suggestion helper (Phase 2).

Deliberately NOT a graph node — called post-hoc by ``GET /queries/{id}/followups``
so the streaming ask-graph stays unchanged. Non-fatal: any failure returns an
empty list rather than raising.
"""
import json
import re
from pathlib import Path

from llm.client import LLMClient
from observability.events import get_logger

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("graph.followups")


def _prompt(name: str) -> str:
    return (_PROMPT_DIR / name).read_text(encoding="utf-8").strip()


def _parse_followups(raw: str, limit: int = 3) -> list[str]:
    """Split the model output into clean, distinct one-line questions."""
    out: list[str] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        text = line.strip()
        if not text:
            continue
        # Strip common list markers: "1.", "1)", "-", "*", "•".
        text = re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", text).strip()
        # Drop obvious preamble lines that aren't questions.
        if not text or text.lower().startswith(("here", "sure", "follow")):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def generate_followups(question: str, answer_text: str, profile: dict) -> list[str]:
    """Propose 2-3 follow-up questions. Returns [] on any failure (non-fatal)."""
    try:
        client = LLMClient()
        profile_json = json.dumps(profile or {}, default=str)
        prompt = (
            f"Original question: {question}\n\n"
            f"Answer produced: {answer_text}\n\n"
            f"Dataset profile:\n{profile_json}\n\n"
            "Suggest 2-3 follow-up questions, one per line."
        )
        raw = client.call_model(prompt, system=_prompt("followups.md"))
        followups = _parse_followups(raw)
        _log.info("followups.generated", count=len(followups))
        return followups
    except Exception as exc:  # noqa: BLE001 — non-fatal by contract
        _log.error("followups.error", error=str(exc))
        return []
