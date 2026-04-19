# Council

A CLI-first meeting room for AI advisors. Stage multi-agent conversations around your project, pressure-test decisions in real time, and get structured feedback from distinct AI personas — all from your terminal.

```
council start

  Alex (CEO)       > The wedge is narrow but defensible. I'd prioritize one vertical first.
  Jordan (CTO)     > The API latency is the real risk. You haven't solved cold-start yet.
  Sam (CFO)        > Your burn projections assume 40% gross margin. That's optimistic.
  Morgan (Devil's) > What if your top customer churns in month three?
```

**Runs 100% locally with Ollama — no API key, no cost, no data leaving your machine.** Anthropic cloud models are also supported if you prefer.

---

## What it does

Council reads your project files once, injects the context into every advisor, and runs a live conversation. Point it at a folder with a spec, a README, a pitch deck, or raw notes — the room sees what you see.

- **100% local by default** — runs on Ollama with any model you have pulled
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

**With Anthropic cloud support:**

```bash
pipx install "council[anthropic] @ git+https://github.com/Aldentec/council-cli.git"
```

### From source

```bash
git clone https://github.com/Aldentec/council-cli.git
cd council-cli
pip install -e .

# Optional: add Anthropic support
pip install -e ".[anthropic]"
```

---

## Running locally with Ollama

Ollama lets you run open-source LLMs on your own machine. Council defaults to Ollama — no API key needed.

### 1. Install Ollama

**macOS / Linux:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Windows:** Download the installer from [ollama.com/download](https://ollama.com/download) and run it.

### 2. Pull a model

```bash
# Recommended — fast and capable for advisory conversations
ollama pull llama3.2

# Larger, more detailed responses
ollama pull llama3.1

# Lightweight, fastest responses
ollama pull phi3

# Other good options
ollama pull mistral
ollama pull gemma2
```

> **Model size guide:** `llama3.2` (~2GB) runs well on most machines with 8GB RAM. `llama3.1` (~4GB) gives richer responses but needs 16GB. `phi3` (~2GB) is the fastest option on constrained hardware.

### 3. Start the Ollama server

```bash
ollama serve
```

Keep this running in a separate terminal. Council connects to it at `http://localhost:11434` by default.

### 4. Start Council

```bash
cd my-project
council init    # choose Ollama when asked
council start
```

That's it — your advisors are fully local.

---

## Quick start with Anthropic (cloud)

If you prefer Anthropic's Claude models instead:

```bash
# 1. Install with Anthropic support
pip install "council[anthropic] @ git+https://github.com/Aldentec/council-cli.git"

# 2. Go to any project folder
cd my-project

# 3. Run the setup wizard — choose Anthropic when asked
council init

# 4. Add your API key to the generated .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# 5. Start the meeting
council start
```

See [Getting an Anthropic API key](#getting-an-anthropic-api-key) below for how to obtain a key.

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
| `council model` | Switch AI models for your advisors interactively |
| `council model <name>` | Set all advisors to a specific model immediately |
| `council context` | Show which files are in context and their token usage |
| `council context add <path>` | Add a directory or file to the context scan |
| `council context remove <path>` | Remove a directory or file from context |
| `council context ignore <pattern>` | Add a glob ignore pattern (e.g. `tests/`) |
| `council context ignore <pattern> --remove` | Remove an existing ignore pattern |
| `council context clear-cache` | Force a full re-scan on next start |
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

providers:
  default_provider: ollama          # ollama | anthropic
  ollama_base_url: http://localhost:11434
  ollama_default_model: llama3.2   # used for file summarization and persona expansion

agents:
  - name: Alex
    role: CEO
    persona: Visionary operator focused on wedge and narrative
    system_prompt: You are Alex, a seasoned CEO...
    model: llama3.2      # any locally pulled Ollama model
    color: "#C9A227"

  - name: Jordan
    role: CTO
    persona: Skeptical technical lead who challenges delivery risk
    system_prompt: You are Jordan, a pragmatic CTO...
    model: llama3.2
    color: "#4A90E2"

settings:
  max_turns: 10
  sequential: true
  user_can_interject: true
  conversation_style: collaborative   # collaborative | debate | socratic
```

### Mixing providers per agent

Each agent can use a different model and provider. The provider is auto-detected from the model name — `claude-*` routes to Anthropic, everything else routes to Ollama.

```yaml
agents:
  - name: Alex
    role: CEO
    model: llama3.2          # → Ollama (local)
    color: "#C9A227"

  - name: Jordan
    role: CTO
    model: claude-sonnet-4-6  # → Anthropic (cloud)
    color: "#4A90E2"
```

You can also set `provider` explicitly on any agent if you need to override:

```yaml
  - name: Sam
    role: CFO
    model: llama3.1
    provider: ollama   # explicit override
```

### Context scanning

When you start a session, Council:

1. Scans the directories and files listed in `context`
2. Filters by type (`.md`, `.txt`, `.yaml`, `.json`, `.toml`, `.rst`) and size (max 50KB)
3. Applies ignore patterns — `node_modules`, `.git`, `__pycache__`, `*.lock`, etc.
4. Prioritizes files by name (README, PRD, spec, architecture rank higher)
5. Summarizes large files via the configured model if they exceed `summarize_threshold`
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

**Commands during a session:**
- `/end` or `/summary` — generate a structured meeting summary
- `/quit` — exit the room

### How Council decides who speaks

Not every advisor responds to every message. Council uses a speaker selection algorithm to route each message to the 1–2 most relevant advisors, then rotates naturally so no single voice dominates.

**The rules, in order:**

1. **All-room cues** — if your message contains "everyone", "all of you", "the whole room", or similar, every advisor responds.
2. **Direct address** — if you name exactly one advisor and ask a direct question ("Jordan, what's your take?"), only they respond.
3. **Two-person teams** — if there are only two advisors, both always respond.
4. **Relevance + rotation** — otherwise, Council scores each advisor by how well their role and persona match the topic of your message (keyword overlap, stop words removed). Advisors who spoke recently receive a small penalty that fades after ~5 turns. The top 2 scorers respond.

**In practice:** ask about engineering risk and the CTO responds. Ask about pricing and the CFO and CEO respond. Send a few messages and the room rotates naturally without you having to direct traffic.

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

Council reads from a `.env` file in your project directory (or any parent directory). Generated by `council init` — never commit it.

```env
# .env

# Ollama (local — default)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.2

# Anthropic (cloud — optional)
ANTHROPIC_API_KEY=sk-ant-...
```

If neither provider is reachable, Council falls back to built-in scripted voices so you can still test your setup offline.

---

## Getting an Anthropic API key

Only needed if you want to use Claude cloud models.

1. Go to [console.anthropic.com](https://console.anthropic.com/) and sign up or log in
2. Open the **API Keys** section in the left sidebar
3. Click **Create Key**, give it a name (e.g. "council"), and copy it — you won't see it again
4. Add some credits under **Billing** → **Add credit** (a few dollars is enough to run many sessions)

Paste the key into your `.env` as `ANTHROPIC_API_KEY=sk-ant-...`

> **Tip:** Your key is scoped to your account. Never commit it to git — `council init` adds `.env` to `.gitignore` automatically.

---

## Requirements

- Python 3.10+
- **For local mode:** [Ollama](https://ollama.com) running locally with at least one model pulled
- **For cloud mode:** An Anthropic API key + `pip install "council[anthropic]"`

---

## Development

```bash
git clone https://github.com/Aldentec/council-cli.git
cd council-cli
pip install -e ".[dev]"

# Optional: add Anthropic support
pip install -e ".[dev,anthropic]"

pytest
```

Key modules:

| File | Purpose |
|---|---|
| `cli.py` | All commands |
| `models.py` | Config schema and YAML I/O |
| `wizard.py` | Interactive init wizard |
| `orchestrator.py` | Conversation routing and multi-provider streaming |
| `providers/` | Provider backends — `ollama_provider.py`, `anthropic_provider.py` |
| `context/` | File scanning, summarization, caching |
| `tui.py` | Terminal UI |
| `server.py` | FastAPI web backend |
| `templates/` | Built-in agent rosters |

---

## License

MIT
