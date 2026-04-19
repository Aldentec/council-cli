from __future__ import annotations

import os
from typing import Generator

from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile, ProvidersConfig
from council.providers.base import LLMProvider
from council.providers import detect_provider, make_provider


class CouncilService:
    """Multi-provider facade: routes each agent's calls to the correct backend."""

    def __init__(self, council: CouncilFile | None = None) -> None:
        cfg = council.providers if council else ProvidersConfig()
        self._ollama_base_url = os.getenv("OLLAMA_BASE_URL", cfg.ollama_base_url)
        self._ollama_default_model = os.getenv("OLLAMA_DEFAULT_MODEL", cfg.ollama_default_model)
        self._default_provider_name = cfg.default_provider
        self._cache: dict[str, LLMProvider] = {}
        self.last_error: str | None = None
        self.last_mode: str = "?"

    def _get_provider(self, name: str) -> LLMProvider:
        if name not in self._cache:
            self._cache[name] = make_provider(
                name,
                ollama_base_url=self._ollama_base_url,
                ollama_default_model=self._ollama_default_model,
            )
        return self._cache[name]

    def _provider_for_agent(self, agent: AgentConfig) -> LLMProvider:
        return self._get_provider(detect_provider(agent.model, agent.provider))

    def _default(self) -> LLMProvider:
        return self._get_provider(self._default_provider_name)

    def ping(self) -> tuple[bool, str]:
        return self._default().ping()

    def fetch_models(self) -> list[str]:
        return self._default().fetch_models()

    def expand_persona(
        self,
        name: str,
        role: str,
        short_persona: str,
        project_name: str,
        project_description: str,
    ) -> str:
        return self._default().expand_persona(name, role, short_persona, project_name, project_description)

    def summarize_file(self, filename: str, content: str) -> str:
        return self._default().summarize_file(filename, content)

    def stream_reply(
        self,
        agent: AgentConfig,
        council: CouncilFile,
        shared_context: str,
        history: list[dict],
    ) -> Generator[str, None, None]:
        provider = self._provider_for_agent(agent)
        self.last_error = None
        try:
            self.last_mode = provider.provider_name
            yield from provider.stream_reply(agent, council, shared_context, history)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_mode = "mock"
            fallback = self._local_reply(agent, council, history)
            for token in fallback.split():
                yield token + " "

    def summarize_meeting(self, council: CouncilFile, history: list[dict]) -> str:
        return self._default().summarize_meeting(council, history)

    def _local_reply(self, agent: AgentConfig, council: CouncilFile, history: list[dict]) -> str:
        latest_user = next(
            (item["content"] for item in reversed(history) if item.get("speaker") == "You"),
            "the current plan",
        )
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


# Backward-compatible alias
CouncilAI = CouncilService
AnthropicFacade = CouncilService
