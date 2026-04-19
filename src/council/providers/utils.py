from __future__ import annotations

from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile


def history_to_text(history: list[dict]) -> str:
    lines = []
    for item in history:
        speaker = item.get("speaker", "Unknown")
        role = item.get("role", "")
        prefix = f"[{speaker} — {role}]" if role else f"[{speaker}]"
        lines.append(f"{prefix}: {item.get('content', '')}")
    return "\n".join(lines)


def build_system_prompt(agent: AgentConfig, council: CouncilFile, shared_context: str) -> str:
    return (
        f"{agent.system_prompt}\n\n"
        f"Conversation style: {council.settings.conversation_style}. "
        "You are in a live meeting. Speak in 2-3 sentences only — never more. "
        "No bullet points, no numbered lists, no bold headers, no section titles. "
        "Plain spoken sentences only. Make one concrete point and stop.\n\n"
        "## Project Briefing\n"
        f"{shared_context}"
    )


def fallback_meeting_summary(council: CouncilFile, history: list[dict]) -> str:
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
