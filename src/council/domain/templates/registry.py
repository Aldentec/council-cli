from __future__ import annotations

from importlib import resources

import yaml

from council.domain.models.config import TemplateRoster


def _template_files() -> list:
    template_root = resources.files("council").joinpath("templates")
    preferred_order = {
        "startup-board.yaml": 0,
        "creative-agency.yaml": 1,
        "engineering-review.yaml": 2,
        "product-launch.yaml": 3,
        "debate-panel.yaml": 4,
        "war-room.yaml": 5,
    }
    return sorted(
        [item for item in template_root.iterdir() if item.name.endswith(".yaml")],
        key=lambda item: (preferred_order.get(item.name, 999), item.name),
    )


def load_template_rosters() -> list[TemplateRoster]:
    rosters: list[TemplateRoster] = []
    for item in _template_files():
        data = yaml.safe_load(item.read_text(encoding="utf-8")) or {}
        rosters.append(TemplateRoster.model_validate(data))
    return rosters
