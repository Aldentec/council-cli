# Council

A CLI-first meeting room for AI advisors. Stage multi-agent conversations around your project, pressure-test decisions in real time, and get structured feedback from distinct AI personas — all from your terminal.

```
council start

  Alex (CEO)       > The wedge is narrow but defensible. I'd prioritize one vertical first.
  Jordan (CTO)     > The API latency is the real risk. You haven't solved cold-start yet.
  Sam (CFO)        > Your burn projections assume 40% gross margin. That's optimistic.
  Morgan (Devil's) > What if your top customer churns in month three?
```

---

## What it does

Council reads your project files once, injects the context into every advisor, and runs a live conversation. Point it at a folder with a spec, a README, a pitch deck, or raw notes — the room sees what you see.

- **6 built-in templates** — Startup Board, Engineering Review, Product Launch, Creative Agency, Debate Panel, War Room
- **Terminal UI** (default) or **browser mode** for presentations
- **Portable config** — one `council.yaml` you can commit and share
- **Saved teams** — switch agent rosters across projects instantly
- **Context-aware** — scans your files, summarizes large ones, caches results

---

## Installation

### Global (recommended)

```bash
pipx install git+https://github.com/Aldentec/council-cli.git
```

Or with pip:

```bash
pip install git+https://github.com/Aldentec/council-cli.git
```

After this, `council` is available in every terminal window.

### From source

```bash
git clone https://github.com/Aldentec/council-cli.git
cd council-cli
pip install -e .
```

---

## Getting an Anthropic API key

Council uses the Anthropic API to power your advisors. Here's how to get a key:

1. Go to [console.anthropic.com](https://console.anthropic.com/) and sign up or log in
2. Open the **API Keys** section in the left sidebar
3. Click **Create Key**, give it a name (e.g. "council"), and copy it — you won't see it again
4. Add some credits under **Billing** → **Add credit** (a few dollars is enough to run many sessions)

That's all. Paste the key when Council asks during `council init`, or add it manually to your `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

> **Tip:** Your key is scoped to your account. Never commit it to git — `council init` adds `.env` to `.gitignore` automatically.

---

## Quick start

```bash
# 1. Go to any project folder
cd my-project

# 2. Run the setup wizard
council init

# 3. Add your API key to the generated .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# 4. Start the meeting
council start
```

That's it. The room is live.

---

## Commands

### Core

| Command | Description |
|---|---|
| `council init` | Interactive wizard — creates `council.yaml` and `.env` |
| `council start` | Launch the terminal meeting room |
| `council start --web` | Launch browser-based meeting room |
| `council list` | Show all configured advisors |
| `council add-agent` | Add a new advisor to the current council |
| `council import <github-url>` | Import a `council.yaml` from a GitHub URL |
| `council reset` | Delete the current `council.yaml` |

### Teams

| Command | Description |
|---|---|
| `council teams` | List all saved team rosters |
| `council save <name>` | Save the current team with a name |
| `council use <name>` | Load a saved team into the current directory |
| `council switch` | Interactively pick and load a saved team |
| `council delete <name>` | Remove a saved team |

### Start options

```
council start [OPTIONS]

  --web              Launch browser UI instead of terminal
  --host TEXT        Host to bind (default: 127.0.0.1)
  --port INTEGER     Port to bind (default: 4000)
  --open/--no-open   Auto-open browser (default: open)
```

---

## Configuration

Council is driven by `council.yaml` in your project root. Commit this file — it's portable.

```yaml
council_version: 1.0.0

project:
  name: My Startup
  description: A customer data platform for SMB finance teams
  industry: Technology
  stage: Pre-seed

context:
  directories:
    - .
  files:
    - docs/ARCHITECTURE.md
  ignore:
    - tests/
    - node_modules/
  max_tokens: 6000          # total context budget
  summarize_threshold: 800  # files larger than this are AI-summarized

agents:
  - name: Alex
    role: CEO
    persona: Visionary operator focused on wedge and narrative
    system_prompt: You are Alex, a seasoned CEO...
    model: claude-3-5-sonnet-latest
    color: "#C9A227"

  - name: Jordan
    role: CTO
    persona: Skeptical technical lead who challenges delivery risk
    system_prompt: You are Jordan, a pragmatic CTO...
    model: claude-3-5-sonnet-latest
    color: "#4A90E2"

settings:
  max_turns: 10
  sequential: true
  user_can_interject: true
  conversation_style: collaborative   # collaborative | debate | socratic
```

### Context scanning

When you start a session, Council:

1. Scans the directories and files listed in `context`
2. Filters by type (`.md`, `.txt`, `.yaml`, `.json`, `.toml`, `.rst`) and size (max 50KB)
3. Applies ignore patterns — `node_modules`, `.git`, `__pycache__`, `*.lock`, etc.
4. Prioritizes files by name (README, PRD, spec, architecture rank higher)
5. Summarizes large files via Claude if they exceed `summarize_threshold`
6. Caches the compiled briefing — subsequent runs are instant unless files change

Cache lives in `~/.council/cache/`. Delete it to force a full re-scan.

---

## Templates

Choose one during `council init` or customize from there.

| Template | Agents |
|---|---|
| **Startup Board** | CEO, CTO, CFO, Devil's Advocate |
| **Engineering Review** | Senior Dev, Security, QA, Architect |
| **Product Launch** | PM, Marketer, Customer Advocate, Data Analyst |
| **Creative Agency** | Art Director, Copywriter, Strategist, Account Lead |
| **Debate Panel** | Proponent, Skeptic, Mediator, Devil's Advocate |
| **War Room** | Crisis Manager, PR Lead, Legal, Operations |

---

## Using the terminal room

```
You > Should we launch the free tier before we have 100 paying customers?

  Alex (CEO)    > Free tier is a distribution bet, not a revenue bet. The question is...
  Jordan (CTO)  > Infrastructure cost per free user will compound. You need rate limits...
  Sam (CFO)     > You're trading LTV now for top-of-funnel velocity. What's your payback...
  Morgan (DA)   > What if the free users never convert and you've built support load...

You > Jordan, what's your actual recommendation?
  Jordan (CTO)  > Ship it with hard resource caps and a 30-day trial ceiling. Don't...

You > /end
  [Summary generated — key points, decisions, action items, open questions]
```

**Mentions:** Name an agent to have them speak first. Ask a direct question to one agent and only they respond.

**Commands during a session:**
- `/end` or `/summary` — generate a structured meeting summary
- `/quit` — exit the room

---

## Browser mode

```bash
council start --web
```

Opens at `http://127.0.0.1:4000`. Agents stream responses in real time. Includes a sidebar with the roster, a composer at the bottom, and a one-click summary you can copy as plain text. Built with FastAPI + HTMX.

---

## Teams

Save a roster once, reuse it across any project.

```bash
# Save the current council
council save startup-board

# In a different project folder
council use startup-board

# Or pick interactively from a list
council switch
```

Teams are stored as YAML files in `~/.council/teams/`. Share them by copying the files or committing them to a shared repo.

---

## Meeting summaries

End any session with `/end`:

```
## Key points discussed
## Decisions reached
## Action items
## Dissenting opinions
## Open questions
```

In web mode, copy the full summary to clipboard with one click.

---

## Environment

Council needs one secret:

```env
# .env  (created by council init — do not commit)
ANTHROPIC_API_KEY=sk-ant-...
```

Council searches upward from the current directory for a `.env` file. If no key is found, it runs with mock replies so you can still test your setup offline.

---

## Requirements

- Python 3.10+
- An Anthropic API key — see [Getting an Anthropic API key](#getting-an-anthropic-api-key) above

---

## Development

```bash
git clone https://github.com/Aldentec/council-cli.git
cd council-cli
pip install -e ".[dev]"
pytest
```

Key modules:

| File | Purpose |
|---|---|
| `cli.py` | All commands |
| `models.py` | Config schema and YAML I/O |
| `wizard.py` | Interactive init wizard |
| `orchestrator.py` | Conversation orchestration and streaming |
| `context/` | File scanning, summarization, caching |
| `tui.py` | Terminal UI |
| `server.py` | FastAPI web backend |
| `templates/` | Built-in agent rosters |

---

## License

MIT
