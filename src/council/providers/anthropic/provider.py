from __future__ import annotations

import os
import time
from typing import Any, Generator

from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile
from council.providers.utils import build_system_prompt, fallback_meeting_summary, history_to_text

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None  # type: ignore[assignment,misc]

FALLBACK_MODELS = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]

MODEL_ALIASES: dict[str, str] = {
    "claude-sonnet-4-6": "claude-sonnet-4-5",
    "claude-3-5-sonnet-latest": "claude-sonnet-4-5",
    "claude-3-5-haiku-latest": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}


def _extract_text(response: Any) -> str:
    texts: list[str] = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", "") == "text":
            texts.append(getattr(block, "text", ""))
    return "".join(texts).strip()


class AnthropicProvider:
    provider_name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
        self.client = Anthropic(api_key=self.api_key) if self.api_key and Anthropic else None

    def _model_name(self, requested: str, small: bool = False) -> str:
        model = requested or ("claude-haiku-4-5-20251001" if small else "claude-sonnet-4-5")
        return MODEL_ALIASES.get(model, model)

    def ping(self) -> tuple[bool, str]:
        if not self.client:
            return False, "Anthropic: no API key set"
        start = time.monotonic()
        try:
            self.client.messages.create(
                model=self._model_name("", small=True),
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply with one word: ready"}],
            )
            ms = int((time.monotonic() - start) * 1000)
            return True, f"Anthropic connected ({ms}ms)"
        except Exception as exc:
            msg = str(exc)
            if "credit balance is too low" in msg or "credits" in msg.lower():
                return False, "Anthropic: no credits — top up at console.anthropic.com"
            if "authentication" in msg.lower() or "api_key" in msg.lower() or "401" in msg:
                return False, "Anthropic: invalid API key"
            return False, f"Anthropic unreachable — {msg[:80]}"

    def fetch_models(self) -> list[str]:
        if self.client:
            try:
                page = self.client.models.list(limit=100)
                ids = [m.id for m in page.data if "claude" in m.id.lower()]
                if ids:
                    return ids
            except Exception:
                pass
        return list(FALLBACK_MODELS)

    def expand_persona(
        self,
        name: str,
        role: str,
        short_persona: str,
        project_name: str,
        project_description: str,
    ) -> str:
        prompt = (
            f"Expand this advisor persona into a rich system prompt for a meeting simulation.\n"
            f"Project: {project_name}\nDescription: {project_description}\n"
            f"Advisor: {name} — {role}\nShort persona: {short_persona}\n\n"
            "Return only the system prompt in plain text."
        )
        if self.client:
            try:
                response = self.client.messages.create(
                    model=self._model_name("", small=True),
                    max_tokens=350,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = _extract_text(response)
                if text:
                    return text
            except Exception:
                pass
        return (
            f"You are {name}, the {role} in Council's meeting room. "
            f"Your core persona is: {short_persona}. Speak with conviction, use concrete reasoning, "
            "challenge weak assumptions, and help the room reach a stronger decision. Stay in character, "
            "reference the shared project briefing, and keep your contribution practical, specific, and concise."
        )

    def summarize_file(self, filename: str, content: str) -> str:
        prompt = (
            "Summarize this file for a team of AI advisors reviewing this project.\n"
            "Preserve: key decisions, technical constraints, important facts, open questions.\n"
            f"Be concise. Do not editorialize.\n\n[file: {filename}]\n{content}"
        )
        if self.client:
            try:
                response = self.client.messages.create(
                    model=self._model_name("", small=True),
                    max_tokens=450,
                    timeout=15.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = _extract_text(response)
                if text:
                    return f"[Summarized from {filename}]\n{text}"
            except Exception:
                pass
        lines = [line.strip() for line in content.splitlines() if line.strip()][:10]
        return f"[Summarized from {filename}]\n" + "\n".join(lines)

    def stream_reply(
        self,
        agent: AgentConfig,
        council: CouncilFile,
        shared_context: str,
        history: list[dict],
    ) -> Generator[str, None, None]:
        if not self.client:
            raise RuntimeError("No Anthropic API key configured")
        system = build_system_prompt(agent, council, shared_context)
        transcript = history_to_text(history)
        latest_user = next(
            (item["content"] for item in reversed(history) if item.get("speaker") == "You"), ""
        )
        with self.client.messages.stream(
            model=self._model_name(agent.model),
            max_tokens=120,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Latest user question: {latest_user or 'The meeting is just beginning.'}\n\n"
                        f"Meeting transcript so far:\n{transcript or 'No prior discussion yet.'}\n\n"
                        f"Respond only as {agent.name}, the {agent.role}. One sharp point. "
                        "Build on what was just said if useful. No lists, no headers, no preamble."
                    ),
                }
            ],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def summarize_meeting(self, council: CouncilFile, history: list[dict]) -> str:
        transcript = history_to_text(history)
        prompt = (
            "Summarize this meeting in structured Markdown with these sections: "
            "Key points discussed, Decisions reached, Action items, Dissenting opinions, Open questions.\n\n"
            f"Project: {council.project.name}\n\n{transcript}"
        )
        if self.client:
            try:
                response = self.client.messages.create(
                    model=self._model_name(""),
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = _extract_text(response)
                if text:
                    return text
            except Exception:
                pass
        return fallback_meeting_summary(council, history)
