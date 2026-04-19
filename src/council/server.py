from __future__ import annotations

import asyncio
from pathlib import Path

import markdown
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from council.context import ContextBuildResult
from council.models import CouncilFile
from council.orchestrator import AnthropicFacade, MeetingOrchestrator

UI_DIR = Path(__file__).resolve().parent / "ui"
TEMPLATES = Environment(
    loader=FileSystemLoader(str(UI_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def create_app(council: CouncilFile, context_result: ContextBuildResult) -> FastAPI:
    app = FastAPI(title="Council", version="0.1.0")
    queue: asyncio.Queue[str] = asyncio.Queue()
    orchestrator = MeetingOrchestrator(council, context_result.content, AnthropicFacade())

    app.state.council = council
    app.state.context_result = context_result
    app.state.queue = queue
    app.state.orchestrator = orchestrator
    app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        template = TEMPLATES.get_template("index.html")
        html_text = template.render(project=council.project, agents=council.agents, request=request)
        return HTMLResponse(html_text)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/meeting/stream")
    async def meeting_stream(request: Request) -> StreamingResponse:
        async def event_source():
            while True:
                if await request.is_disconnected():
                    break
                payload = await queue.get()
                yield payload

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/meeting/message", response_class=HTMLResponse)
    async def meeting_message(message: str = Form(...)) -> HTMLResponse:
        clean = message.strip()
        if not clean:
            return HTMLResponse("")
        asyncio.create_task(orchestrator.queue_round(clean, queue))
        return HTMLResponse(orchestrator.user_html(clean))

    @app.post("/meeting/end", response_class=HTMLResponse)
    async def end_meeting() -> HTMLResponse:
        summary_markdown = orchestrator.end_meeting()
        summary_html = markdown.markdown(summary_markdown, extensions=["extra", "tables", "sane_lists"])
        card = (
            '<section class="summary-card">'
            '<div class="summary-top">'
            '<h2>Meeting Summary</h2>'
            '<button class="copy-button" onclick="copySummary()">Copy</button>'
            '</div>'
            f'<div id="meeting-summary" class="summary-body">{summary_html}</div>'
            '</section>'
        )
        return HTMLResponse(card)

    return app
