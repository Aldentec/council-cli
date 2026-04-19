from __future__ import annotations

import asyncio
import html
import os
import time
from dataclasses import dataclass
from typing import Any, Generator
from uuid import uuid4

from council.models import AgentConfig, CouncilFile

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None


FALLBACK_MODELS = [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]

MODEL_ALIASES = {
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


class AnthropicFacade:
    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'")
        self.client = Anthropic(api_key=self.api_key) if self.api_key and Anthropic else None
        self.last_error: str | None = None
        self.last_mode = "api" if self.client else "mock"

    def _model_name(self, requested: str, small: bool = False) -> str:
        model = requested or ("claude-haiku-4-5-20251001" if small else "claude-sonnet-4-5")
        return MODEL_ALIASES.get(model, model)

    def ping(self) -> tuple[bool, str]:
        """Make a minimal API call to confirm connectivity. Returns (ok, display_string)."""
        if not self.client:
            return False, "No API key — mock mode"
        start = time.monotonic()
        try:
            self.client.messages.create(
                model=self._model_name("", small=True),
                max_tokens=10,
                messages=[{"role": "user", "content": "Reply with one word: ready"}],
            )
            ms = int((time.monotonic() - start) * 1000)
            return True, f"Connected ({ms}ms)"
        except Exception as exc:
            msg = str(exc)
            if "credit balance is too low" in msg or "credits" in msg.lower():
                return False, "No credits — top up at console.anthropic.com"
            if "authentication" in msg.lower() or "api_key" in msg.lower() or "401" in msg:
                return False, "Invalid API key"
            return False, f"Unreachable — {msg[:120]}"

    def fetch_models(self) -> list[str]:
        """Return available model IDs from the API, falling back to a hardcoded list."""
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
            f"Project: {project_name}\n"
            f"Description: {project_description}\n"
            f"Advisor: {name} — {role}\n"
            f"Short persona: {short_persona}\n\n"
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
            "Be concise. Do not editorialize.\n\n"
            f"[file: {filename}]\n{content}"
        )
        if self.client:
            try:
                response = self.client.messages.create(
                    model=self._model_name("", small=True),
                    max_tokens=450,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = _extract_text(response)
                if text:
                    return f"[Summarized from {filename}]\n{text}"
            except Exception:
                pass
        lines = [line.strip() for line in content.splitlines() if line.strip()][:10]
        body = "\n".join(lines)
        return f"[Summarized from {filename}]\n{body}"

    def stream_reply(
        self,
        agent: AgentConfig,
        council: CouncilFile,
        shared_context: str,
        history: list[dict[str, str]],
    ) -> Generator[str, None, None]:
        system = self._build_system_prompt(agent, council, shared_context)
        transcript = self._history_to_text(history)
        latest_user = next((item["content"] for item in reversed(history) if item.get("speaker") == "You"), "")
        self.last_error = None
        if self.client:
            try:
                with self.client.messages.stream(
                    model=self._model_name(agent.model),
                    max_tokens=300,
                    system=system,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Latest user question: {latest_user or 'The meeting is just beginning.'}\n\n"
                                f"Meeting transcript so far:\n{transcript or 'No prior discussion yet.'}\n\n"
                                f"Respond only as {agent.name}, the {agent.role}. Add a distinct perspective, "
                                "build on prior speakers when useful, and avoid repeating generic advice."
                            ),
                        }
                    ],
                ) as stream:
                    self.last_mode = "api"
                    for text in stream.text_stream:
                        yield text
                    return
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self.last_mode = "mock"

        fallback = self._local_reply(agent, council, history)
        for token in fallback.split():
            yield token + " "

    def summarize_meeting(self, council: CouncilFile, history: list[dict[str, str]]) -> str:
        transcript = self._history_to_text(history)
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

        user_points = [item["content"] for item in history if item.get("speaker") == "You"]
        advisor_points = [item for item in history if item.get("speaker") != "You"]
        action_item = user_points[-1] if user_points else "Clarify the top priority for the next session."
        dissent = advisor_points[-1]["content"] if advisor_points else "No strong dissent recorded."
        return (
            "## Key points discussed\n"
            f"- {council.project.description}\n"
            f"- {len(advisor_points)} advisor contributions were recorded.\n\n"
            "## Decisions reached\n"
            "- The room aligned on refining the plan through structured discussion.\n\n"
            "## Action items\n"
            f"- Follow up on: {action_item}\n\n"
            "## Dissenting opinions\n"
            f"- {dissent[:240]}\n\n"
            "## Open questions\n"
            "- What evidence or customer signal should the team validate next?\n"
        )

    def _history_to_text(self, history: list[dict[str, str]]) -> str:
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
            "This is a meeting, not a coding task. Be incisive, grounded, and decision-oriented. "
            "Keep responses to 2-3 sentences maximum — sharp and direct, no preamble or filler.\n\n"
            "## Project Briefing\n"
            f"{shared_context}"
        )

    def _local_reply(self, agent: AgentConfig, council: CouncilFile, history: list[dict[str, str]]) -> str:
        latest_user = next((item["content"] for item in reversed(history) if item.get("speaker") == "You"), "the current plan")
        latest_lower = latest_user.lower()
        role = agent.role.lower()
        prior_speaker = next(
            (
                item["speaker"]
                for item in reversed(history)
                if item.get("speaker") not in {"You", agent.name}
            ),
            None,
        )
        lead = f"Building on {prior_speaker}, " if prior_speaker else ""

        if any(keyword in latest_lower for keyword in ["android", "ios", "iphone", "mobile"]):
            if "ceo" in role or "founder" in role:
                return (
                    f"{lead}I would choose the platform that gives {council.project.name} the clearest early wedge. "
                    "If the first users are likely to pay quickly and care about polish, iOS is the better opening move. "
                    "If reach, emerging markets, or broad distribution matter more, Android gets stronger. "
                    "My bias is to start with one platform, learn fast, and avoid splitting focus too early."
                )
            if "cto" in role or "engineer" in role or "architect" in role:
                return (
                    f"{lead}From an engineering angle, iOS first is usually simpler because the device matrix is tighter and QA is faster. "
                    "Android gives you a larger surface area but more fragmentation, more testing paths, and more edge cases. "
                    "Unless Android demand is clearly dominant, I would ship one clean iOS version first and use that learning to de-risk Android."
                )
            if "cfo" in role or "finance" in role:
                return (
                    f"{lead}I would pick the platform with the faster path to payback. iOS often monetizes sooner and carries lower support drag at launch, "
                    "while Android can give more top-of-funnel volume but may cost more to support. "
                    "I would back the platform where we can learn cheaply and prove willingness to pay."
                )
            if "devil" in role or "skeptic" in role:
                return (
                    f"{lead}I think the real risk is deciding iOS versus Android before naming the user segment clearly. "
                    "If the audience is fuzzy, the platform debate becomes a proxy for uncertainty. "
                    "Prove where your earliest obsessed users already live, then commit instead of guessing."
                )

        if "smb" in latest_lower or "enterprise" in latest_lower:
            if "ceo" in role or "founder" in role:
                return f"{lead}I would start with whichever segment has the sharper pain and shorter sales motion. SMB usually wins on speed, enterprise on contract size. Pick the wedge that can create traction fastest."
            if "cto" in role or "engineer" in role or "architect" in role:
                return f"{lead}Enterprise demands more controls, integrations, and reliability upfront. If the product is still early, SMB is usually the cleaner first market from a build perspective."
            if "cfo" in role or "finance" in role:
                return f"{lead}SMB may close faster but can churn harder; enterprise is slower but can support bigger contracts. I would compare payback period, support burden, and cash timing before choosing."

        if "price" in latest_lower or "pricing" in latest_lower or "subscription" in latest_lower:
            return f"{lead}I would not treat pricing as a guess. Set one simple default, one premium tier, and one clear metric to learn whether the value story is strong enough to hold."

        if "ceo" in role or "founder" in role:
            return f"{lead}My CEO view is to force a decision: what is the wedge, who is it for, and what proof would justify the next bet? I would narrow the focus and make the room choose one measurable next move."
        if "cto" in role or "engineer" in role or "architect" in role:
            return f"{lead}My CTO take is to reduce scope until the plan is easy to ship and easy to learn from. The right answer is usually the one with the least complexity for the highest information gain."
        if "cfo" in role or "finance" in role:
            return f"{lead}From the finance side, I care about downside protection, payback speed, and whether the next step buys us real evidence instead of expensive optimism."
        if "marketing" in role or "strategist" in role or "copywriter" in role:
            return f"{lead}I would tighten the positioning, name the audience explicitly, and make sure the message is strong enough that someone immediately understands why this matters now."
        if "legal" in role or "security" in role or "qa" in role:
            return f"{lead}I would stress-test the edge cases now, before the team grows confident around a weak assumption that later breaks trust."
        if "devil" in role or "skeptic" in role:
            return f"{lead}I think the room may be moving too fast past the core assumption. I would name what has to be true for this to work and ask what evidence could prove us wrong quickly."
        return f"{lead}My view is to sharpen the trade-off, pick one concrete next action, and turn the discussion into a decision rather than a loop."


@dataclass
class MeetingOrchestrator:
    council: CouncilFile
    shared_context: str
    ai: AnthropicFacade
    history: list[dict[str, str]]

    def __init__(self, council: CouncilFile, shared_context: str, ai: AnthropicFacade | None = None) -> None:
        self.council = council
        self.shared_context = shared_context
        self.ai = ai or AnthropicFacade()
        self.history = []
        self._lock = asyncio.Lock()

    @staticmethod
    def sse_message(html_fragment: str) -> str:
        safe_lines = html_fragment.splitlines() or [html_fragment]
        data = "\n".join(f"data: {line}" for line in safe_lines)
        return f"event: message\n{data}\n\n"

    def user_html(self, message: str) -> str:
        return (
            '<div class="user-message">'
            '<div class="user-heading">You</div>'
            f'<div class="user-body">{html.escape(message)}</div>'
            '</div>'
        )

    def _ordered_agents(self, user_message: str) -> list[AgentConfig]:
        text = user_message.lower()
        mentioned = [agent for agent in self.council.agents if agent.name.lower() in text]
        if not mentioned:
            return list(self.council.agents)

        direct_cues = [
            "what do you think",
            "thoughts",
            "do you agree",
            "can you weigh in",
            "tell me",
            "?",
        ]
        if len(mentioned) == 1 and any(cue in text for cue in direct_cues):
            return mentioned

        mentioned_names = {agent.name for agent in mentioned}
        return mentioned + [agent for agent in self.council.agents if agent.name not in mentioned_names]

    async def queue_round(self, user_message: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self.history.append({"speaker": "You", "role": "User", "content": user_message})
            for agent in self._ordered_agents(user_message):
                body_id = f"agent-{uuid4().hex}"
                agent_shell = (
                    '<div class="agent-message" hx-swap-oob="beforeend:#transcript">'
                    f'<div class="agent-heading"><span class="agent-swatch" style="background:{html.escape(agent.color)}"></span>'
                    f'<span class="agent-name">{html.escape(agent.name)}</span>'
                    f'<span class="agent-role">{html.escape(agent.role)}</span></div>'
                    f'<div id="{body_id}" class="agent-body"></div>'
                    '</div>'
                )
                await queue.put(self.sse_message(agent_shell))
                full_response = ""
                for token in self.ai.stream_reply(agent, self.council, self.shared_context, self.history):
                    full_response += token
                    token_html = f'<span hx-swap-oob="beforeend:#{body_id}">{html.escape(token)}</span>'
                    await queue.put(self.sse_message(token_html))
                self.history.append(
                    {
                        "speaker": agent.name,
                        "role": agent.role,
                        "content": full_response.strip(),
                    }
                )
                await queue.put(self.sse_message('<div class="agent-divider" hx-swap-oob="beforeend:#transcript"></div>'))

    def end_meeting(self) -> str:
        return self.ai.summarize_meeting(self.council, self.history)
