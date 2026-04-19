from __future__ import annotations

import json
import time
from typing import Generator

import httpx

from council.models import AgentConfig, CouncilFile

OLLAMA_FALLBACK_MODELS = ["llama3.2", "llama3.1", "mistral", "phi3", "gemma2"]


class OllamaProvider:
    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model

    def ping(self) -> tuple[bool, str]:
        start = time.monotonic()
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            ms = int((time.monotonic() - start) * 1000)
            models = response.json().get("models", [])
            count = len(models)
            label = f"{count} model{'s' if count != 1 else ''} available"
            return True, f"Ollama connected ({ms}ms, {label})"
        except httpx.ConnectError:
            return False, "Ollama not running — start with: ollama serve"
        except Exception as exc:
            return False, f"Ollama unreachable — {str(exc)[:80]}"

    def fetch_models(self) -> list[str]:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=10.0)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [m["name"] for m in models if m.get("name")]
            return names if names else list(OLLAMA_FALLBACK_MODELS)
        except Exception:
            return list(OLLAMA_FALLBACK_MODELS)

    def _chat(self, model: str, messages: list[dict], max_tokens: int = 450) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        response = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=120.0)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()

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
            "Return only the system prompt in plain text. Keep it under 200 words."
        )
        try:
            return self._chat(self._default_model, [{"role": "user", "content": prompt}], max_tokens=350)
        except Exception:
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
        try:
            text = self._chat(self._default_model, [{"role": "user", "content": prompt}], max_tokens=450)
            return f"[Summarized from {filename}]\n{text}"
        except Exception:
            lines = [line.strip() for line in content.splitlines() if line.strip()][:10]
            return f"[Summarized from {filename}]\n" + "\n".join(lines)

    def stream_reply(
        self,
        agent: AgentConfig,
        council: CouncilFile,
        shared_context: str,
        history: list[dict],
    ) -> Generator[str, None, None]:
        system = self._build_system_prompt(agent, council, shared_context)
        transcript = self._history_to_text(history)
        latest_user = next(
            (item["content"] for item in reversed(history) if item.get("speaker") == "You"), ""
        )
        model = agent.model or self._default_model
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"Latest user question: {latest_user or 'The meeting is just beginning.'}\n\n"
                        f"Meeting transcript so far:\n{transcript or 'No prior discussion yet.'}\n\n"
                        f"Respond only as {agent.name}, the {agent.role}. One sharp point. "
                        "Build on what was just said if useful. No lists, no headers, no preamble."
                    ),
                },
            ],
            "stream": True,
            "options": {"num_predict": 120},
        }
        with httpx.stream("POST", f"{self._base_url}/api/chat", json=payload, timeout=120.0) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if data.get("done"):
                        break

    def summarize_meeting(self, council: CouncilFile, history: list[dict]) -> str:
        transcript = self._history_to_text(history)
        prompt = (
            "Summarize this meeting in structured Markdown with these sections: "
            "Key points discussed, Decisions reached, Action items, Dissenting opinions, Open questions.\n\n"
            f"Project: {council.project.name}\n\n{transcript}"
        )
        try:
            return self._chat(self._default_model, [{"role": "user", "content": prompt}], max_tokens=800)
        except Exception:
            from council.providers.anthropic_provider import _fallback_summary
            return _fallback_summary(council, history)

    def _history_to_text(self, history: list[dict]) -> str:
        lines = []
        for item in history:
            speaker = item.get("speaker", "Unknown")
            role = item.get("role", "")
            prefix = f"[{speaker} — {role}]" if role else f"[{speaker}]"
            lines.append(f"{prefix}: {item.get('content', '')}")
        return "\n".join(lines)

    def _build_system_prompt(self, agent: AgentConfig, council: CouncilFile, shared_context: str) -> str:
        return (
            f"{agent.system_prompt}\n\n"
            f"Conversation style: {council.settings.conversation_style}. "
            "You are in a live meeting. Speak in 2-3 sentences only — never more. "
            "No bullet points, no numbered lists, no bold headers, no section titles. "
            "Plain spoken sentences only. Make one concrete point and stop.\n\n"
            "## Project Briefing\n"
            f"{shared_context}"
        )
