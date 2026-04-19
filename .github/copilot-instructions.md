# Council Project Guidelines

## Product Scope
- Council is a local-first meeting-room simulator for AI advisors.
- In scope: conversation orchestration, shared project briefing, CLI workflows, and the terminal meeting room. The web view is secondary.
- Out of scope: code execution, file mutation, background agents, embeddings, and vector search.

## Architecture
- Keep the Python package in the `src/council` tree.
- Put user-facing CLI behavior in `cli.py` and interactive setup in `wizard.py`.
- Keep shared config and validation in `models.py`.
- Keep project briefing logic in `context/builder.py`.
- Keep streaming conversation flow in `orchestrator.py` and HTTP/UI logic in `server.py`.

## Build and Test
- Install locally with `pip install -e ".[dev]"`.
- Run tests with `pytest`.
- Main manual flow: `council init`, then `council start`.

## Conventions
- Prefer small, readable functions over clever abstractions.
- Use Rich styling with Council brand colors for terminal output.
- Treat `council.yaml` as the portable artifact and keep secrets only in `.env`.
- Keep the MVP session-local and in-memory; do not add persistence unless explicitly requested.
- Link to docs instead of duplicating long guidance.
