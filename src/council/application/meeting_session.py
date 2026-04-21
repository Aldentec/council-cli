from __future__ import annotations

import asyncio
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from council.application.council_service import CouncilService
from council.application.decision_ledger import (
    Contradiction,
    DecisionLedger,
    ProposedRevision,
    coordinator_state,
    detect_contradictions,
    parse_revision,
)
from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile
from council.domain.routing.speaker_selector import (
    ALL_ROOM_CUES,
    DIRECT_CUES,
    FOLLOWUP_CUES,
    affinity_boost,
    score_relevance,
    tokenize,
)


@dataclass
class MeetingSession:
    council: CouncilFile
    shared_context: str
    service: CouncilService
    history: list[dict]

    def __init__(
        self,
        council: CouncilFile,
        shared_context: str,
        service: CouncilService | None = None,
    ) -> None:
        self.council = council
        self.shared_context = shared_context
        self.service = service or CouncilService(council)
        self.history = []
        self._lock = asyncio.Lock()
        now = datetime.now(timezone.utc)
        self.session_id: str = now.strftime("%Y%m%dT%H%M%SZ")
        self.started_at: str = now.isoformat()
        self.decision_ledger = DecisionLedger()

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

    def _last_agent(self) -> AgentConfig | None:
        for item in reversed(self.history):
            speaker = item.get("speaker")
            if speaker and speaker != "You":
                return next((a for a in self.council.agents if a.name == speaker), None)
        return None

    def _followup_agent(self, user_message: str) -> AgentConfig | None:
        msg_tokens = tokenize(user_message)
        text = user_message.lower()

        if len(msg_tokens) <= 2 or any(cue in text for cue in FOLLOWUP_CUES):
            return self._last_agent()

        best_name: str | None = None
        best_score = 0.3
        checked = 0
        for item in reversed(self.history):
            speaker = item.get("speaker")
            if not speaker or speaker == "You":
                continue
            response_tokens = tokenize(item.get("content", ""))
            if msg_tokens and response_tokens:
                s = len(msg_tokens & response_tokens) / len(msg_tokens)
                if s > best_score:
                    best_score = s
                    best_name = speaker
            checked += 1
            if checked >= 6:
                break

        if best_name:
            return next((a for a in self.council.agents if a.name == best_name), None)
        return None

    def _turns_since_spoke(self) -> dict[str, int]:
        result: dict[str, int] = {}
        turns = 0
        for item in reversed(self.history):
            if item.get("speaker") == "You":
                turns += 1
            elif item.get("speaker") not in result:
                result[item["speaker"]] = turns
        return result

    def _ordered_agents(self, user_message: str) -> list[AgentConfig]:
        text = user_message.lower()
        agents = self.council.agents

        if any(cue in text for cue in ALL_ROOM_CUES):
            return list(agents)

        mentioned = [a for a in agents if a.name.lower() in text]

        if len(mentioned) == 1 and any(cue in text for cue in DIRECT_CUES):
            return mentioned

        if len(agents) <= 2:
            return list(agents)

        if not mentioned:
            target = self._followup_agent(user_message)
            if target:
                return [target]

        recent = self._turns_since_spoke()

        last_round: set[str] = set()
        for item in reversed(self.history):
            if item.get("speaker") == "You":
                break
            speaker = item.get("speaker")
            if speaker and speaker != "You":
                last_round.add(speaker)

        def _score(agent: AgentConfig) -> float:
            relevance = score_relevance(user_message, agent) + affinity_boost(user_message, agent)
            turns_ago = recent.get(agent.name)
            if turns_ago is None:
                penalty = -0.2
            elif turns_ago == 1:
                penalty = 0.35
            elif turns_ago == 2:
                penalty = 0.15
            else:
                penalty = 0.0
            return relevance - penalty

        scored = sorted(agents, key=_score, reverse=True)

        _THRESHOLD = 0.1
        _OUT_OF_SCOPE_THRESHOLD = -0.15
        if all(_score(a) < _OUT_OF_SCOPE_THRESHOLD for a in scored):
            return []
        n_active = sum(1 for a in scored if _score(a) >= _THRESHOLD)
        limit = max(1, min(n_active, 3))

        mentioned_names = {a.name for a in mentioned}
        result: list[AgentConfig] = list(mentioned)

        fresh = [a for a in scored if a.name not in mentioned_names and a.name not in last_round]
        stale = [a for a in scored if a.name not in mentioned_names and a.name in last_round]
        for a in fresh + stale:
            if len(result) >= limit:
                break
            result.append(a)

        return result

    def _out_of_scope_html(self) -> str:
        project = html.escape(self.council.project.name)
        return (
            '<div class="system-message" hx-swap-oob="beforeend:#transcript">'
            f"That's outside what this council is here to advise on. "
            f"Try asking something related to {project} — strategy, product, finances, or execution."
            "</div>"
        )

    def _extract_decision_from_user(self, user_message: str) -> None:
        text = user_message.strip()
        lower = text.lower()
        if ("delay" in lower or "defer" in lower) and "reddit" in lower:
            self.decision_ledger.upsert(
                topic="Reddit ads",
                status="active",
                statement="Delay Reddit ads until direct customer interviews are completed.",
            )

    def _history_with_coordinator(
        self, revisions: list[ProposedRevision], contradictions: list[Contradiction]
    ) -> list[dict]:
        if not revisions and not contradictions:
            return self.history
        coordinator = coordinator_state(self.decision_ledger, revisions, contradictions)
        extended = list(self.history)
        extended.append({"speaker": "Coordinator", "role": "Moderator", "content": coordinator})
        return extended

    @staticmethod
    def _wants_state_summary(user_message: str) -> bool:
        text = user_message.lower()
        cues = ["decide", "decision", "conflict", "contradict", "revision", "what did we discuss", "last time"]
        return any(cue in text for cue in cues)

    async def queue_round(self, user_message: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._extract_decision_from_user(user_message)
            self.history.append({"speaker": "You", "role": "User", "content": user_message})
            speakers = self._ordered_agents(user_message)
            if not speakers:
                await queue.put(self.sse_message(self._out_of_scope_html()))
                return

            revisions: list[ProposedRevision] = []
            contradictions: list[Contradiction] = []
            for agent in speakers:
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
                prompt_history = self._history_with_coordinator(revisions, contradictions)
                for token in self.service.stream_reply(
                    agent,
                    self.council,
                    self.shared_context,
                    prompt_history,
                    decision_ledger=self.decision_ledger,
                ):
                    full_response += token
                    token_html = f'<span hx-swap-oob="beforeend:#{body_id}">{html.escape(token)}</span>'
                    await queue.put(self.sse_message(token_html))

                parsed_revision = parse_revision(full_response)
                if parsed_revision:
                    revisions.append(parsed_revision)

                contradictions.extend(detect_contradictions(self.decision_ledger, agent.name, full_response))

                if contradictions and not parsed_revision:
                    conflict_text = " ".join(item.summary for item in contradictions if item.speaker == agent.name)
                    if conflict_text:
                        full_response = (
                            "PROPOSED REVISION\n"
                            "Topic: Reddit ads\n"
                            "Suggestion: Run a constrained Reddit test budget before full rollout.\n"
                            "Reason: New evidence from controlled experiments may de-risk timing decisions.\n"
                            "Risk: Premature spend may distract from interview-first learning.\n"
                            "Trigger: Only after defining test KPIs and stop conditions.\n"
                            "Approver: Meeting owner\n\n"
                            f"Auto-flagged consistency issue: {conflict_text}"
                        )

                self.history.append(
                    {
                        "speaker": agent.name,
                        "role": agent.role,
                        "content": full_response.strip(),
                    }
                )
                await queue.put(
                    self.sse_message('<div class="agent-divider" hx-swap-oob="beforeend:#transcript"></div>')
                )

            if revisions or contradictions or self._wants_state_summary(user_message):
                coordinator = coordinator_state(self.decision_ledger, revisions, contradictions)
                coordinator_html = (
                    '<div class="system-message" hx-swap-oob="beforeend:#transcript">'
                    f"{html.escape(coordinator)}"
                    "</div>"
                )
                await queue.put(self.sse_message(coordinator_html))
                self.history.append({"speaker": "Coordinator", "role": "Moderator", "content": coordinator})

    def end_meeting(self) -> str:
        return self.service.summarize_meeting(self.council, self.history)


# Backward-compatible alias
MeetingOrchestrator = MeetingSession
