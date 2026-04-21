from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from council.application.council_service import CouncilService
from council.application.meeting_session import MeetingSession
from council.domain.models.config import CouncilFile
from council.infrastructure.context.cache import ContextBuildResult
from council.infrastructure.sessions.store import SavedSession, SessionStore, canonical_team_signature
from council.ui.tui.display import print_startup_summary

console = Console()


def _save_session(
    council: CouncilFile,
    session: MeetingSession,
    service: CouncilService,
    workspace: Path,
    *,
    with_summary: bool,
) -> None:
    if not council.settings.persist_sessions:
        return
    if not session.history:
        return

    user_turns = [h for h in session.history if h.get("speaker") == "You"]
    if not user_turns:
        return

    summary = ""
    if with_summary:
        try:
            summary = service.summarize_meeting(council, session.history)
        except Exception:
            pass

    # Cache team identification across multiple saves during the same session
    if not hasattr(session, "_team_cache"):
        team_id = canonical_team_signature(council.project.name, council.agents)
        team_meeting_number = SessionStore(workspace).next_team_meeting_number(team_id)
        session._team_cache = (team_id, team_meeting_number)
    else:
        team_id, team_meeting_number = session._team_cache

    saved = SavedSession(
        session_id=session.session_id,
        started_at=session.started_at,
        project_name=council.project.name,
        history=session.history,
        team_id=team_id,
        team_meeting_number=team_meeting_number,
        summary=summary,
        turn_count=len(user_turns),
    )
    SessionStore(workspace).save(saved)
    if with_summary:
        console.print("[dim]Session saved with summary.[/dim]")
    else:
        console.print("[dim]Session saved.[/dim]")


def run_tui(
    council: CouncilFile,
    result: ContextBuildResult,
    workspace: Path | None = None,
    api_status: tuple[bool, str] | None = None,
) -> None:
    service = CouncilService(council)
    session = MeetingSession(council, result.content, service)
    cwd = workspace or Path.cwd()

    print_startup_summary(council, result, mode="TUI", api_status=api_status)
    roster = Table(title="Advisors", header_style="bold #C9A227")
    roster.add_column("Name")
    roster.add_column("Role")
    roster.add_column("Persona")
    for agent in council.agents:
        roster.add_row(agent.name, agent.role, agent.persona)
    console.print(roster)
    console.print("[bold #C9A227]Commands:[/bold #C9A227] /end for summary, /export to save transcript, /quit to leave")

    warned_about_fallback = False

    while True:
        try:
            message = console.input("\n[bold #C9A227]You[/bold #C9A227] > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[#8B8680]Meeting closed.[/#8B8680]")
            _save_session(council, session, service, cwd, with_summary=False)
            break

        if not message:
            continue
        if message.lower() in {"/quit", "quit", "exit"}:
            console.print("[#8B8680]Meeting closed.[/#8B8680]")
            _save_session(council, session, service, cwd, with_summary=False)
            break
        if message.lower() in {"/end", "/summary"}:
            console.print("\n[bold #C9A227]Meeting Summary[/bold #C9A227]")
            summary_text = session.end_meeting()
            console.print(Markdown(summary_text))
            _save_session(council, session, service, cwd, with_summary=True)
            break
        if message.lower() == "/export":
            _save_session(council, session, service, cwd, with_summary=False)
            console.print("[dim]Transcript exported.[/dim]")
            continue

        console.print(Panel.fit(message, title="You", border_style="#C9A227"))
        session.history.append({"speaker": "You", "role": "User", "content": message})

        for agent in session._ordered_agents(message):
            console.print(f"\n[bold {agent.color}]{agent.name}[/bold {agent.color}] [#8B8680]— {agent.role}[/#8B8680]")
            full_response = ""
            for token in service.stream_reply(agent, council, result.content, session.history):
                full_response += token
                console.print(token, end="", style=agent.color, highlight=False, soft_wrap=True)
            console.print("")
            if service.last_error and not warned_about_fallback:
                console.print(
                    "[#8B8680]AI request failed — Council is using built-in fallback voices for this session.[/#8B8680]"
                )
                warned_about_fallback = True
            session.history.append(
                {
                    "speaker": agent.name,
                    "role": agent.role,
                    "content": full_response.strip(),
                }
            )
