from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_council_env(start_path: str | Path | None = None) -> bool:
    base = Path(start_path or Path.cwd()).resolve()
    candidates = [base / ".env", *[parent / ".env" for parent in base.parents]]

    for candidate in candidates:
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)
            break

    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip().strip('"').strip("'"))
