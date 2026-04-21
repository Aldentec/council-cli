from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re


@dataclass
class DecisionItem:
    decision_id: str
    topic: str
    status: str
    statement: str


@dataclass
class ProposedRevision:
    topic: str
    suggestion: str
    reason: str
    risk: str
    trigger: str
    approver: str


@dataclass
class DecisionLedger:
    decisions: list[DecisionItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"decisions": [asdict(item) for item in self.decisions]}

    @classmethod
    def from_dict(cls, payload: dict | None) -> "DecisionLedger":
        if not payload:
            return cls()
        items = []
        for raw in payload.get("decisions", []):
            if not isinstance(raw, dict):
                continue
            items.append(
                DecisionItem(
                    decision_id=str(raw.get("decision_id", "")).strip(),
                    topic=str(raw.get("topic", "")).strip(),
                    status=str(raw.get("status", "")).strip() or "active",
                    statement=str(raw.get("statement", "")).strip(),
                )
            )
        return cls(decisions=[i for i in items if i.decision_id and i.statement])

    def upsert(self, topic: str, status: str, statement: str) -> None:
        clean_topic = topic.strip().lower()
        for item in self.decisions:
            if item.topic.lower() == clean_topic:
                item.status = status.strip() or item.status
                item.statement = statement.strip() or item.statement
                return
        next_id = f"D{len(self.decisions) + 1}"
        self.decisions.append(
            DecisionItem(decision_id=next_id, topic=topic.strip(), status=status.strip() or "active", statement=statement.strip())
        )

    def render_for_prompt(self) -> str:
        if not self.decisions:
            return "(none yet)"
        lines = []
        for item in self.decisions:
            lines.append(f"- [{item.decision_id}] {item.topic} | {item.status} | {item.statement}")
        return "\n".join(lines)


@dataclass
class Contradiction:
    summary: str
    speaker: str


REVISION_TOPIC_RE = re.compile(r"^topic\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
REVISION_SUGGESTION_RE = re.compile(r"^suggestion\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
REVISION_REASON_RE = re.compile(r"^reason\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
REVISION_RISK_RE = re.compile(r"^risk\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
REVISION_TRIGGER_RE = re.compile(r"^trigger\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
REVISION_APPROVER_RE = re.compile(r"^approver\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def parse_revision(text: str) -> ProposedRevision | None:
    if "PROPOSED REVISION" not in text.upper():
        return None

    def _get(pattern: re.Pattern[str]) -> str:
        match = pattern.search(text)
        return match.group(1).strip() if match else ""

    topic = _get(REVISION_TOPIC_RE)
    suggestion = _get(REVISION_SUGGESTION_RE)
    if not topic or not suggestion:
        return None
    return ProposedRevision(
        topic=topic,
        suggestion=suggestion,
        reason=_get(REVISION_REASON_RE),
        risk=_get(REVISION_RISK_RE),
        trigger=_get(REVISION_TRIGGER_RE),
        approver=_get(REVISION_APPROVER_RE),
    )


def detect_contradictions(ledger: DecisionLedger, speaker: str, response: str) -> list[Contradiction]:
    lower = response.lower()
    contradictions: list[Contradiction] = []
    for item in ledger.decisions:
        statement = item.statement.lower()
        topic = item.topic.lower()
        if "reddit" in topic or "reddit" in statement:
            delays = "delay" in statement or "defer" in statement
            spend_now = ("spend" in lower or "$" in lower or "budget" in lower) and (
                "reddit" in lower and "delay" not in lower and "defer" not in lower
            )
            if delays and spend_now and "PROPOSED REVISION" not in response.upper():
                contradictions.append(
                    Contradiction(
                        speaker=speaker,
                        summary=(
                            f"Conflicts with [{item.decision_id}] by recommending immediate Reddit spend without marking a proposed revision."
                        ),
                    )
                )
    return contradictions


def coordinator_state(ledger: DecisionLedger, revisions: list[ProposedRevision], contradictions: list[Contradiction]) -> str:
    active = [f"[{d.decision_id}] {d.statement}" for d in ledger.decisions if d.status.lower() == "active"]
    lines = ["Coordinator — Final State", "Current decisions:"]
    lines.extend([f"- {item}" for item in active] or ["- None recorded"]) 
    lines.append("Proposed revisions:")
    if revisions:
        for revision in revisions:
            lines.append(f"- {revision.topic}: {revision.suggestion}")
    else:
        lines.append("- None")
    lines.append("Consistency check:")
    if contradictions:
        for conflict in contradictions:
            lines.append(f"- {conflict.speaker}: {conflict.summary}")
    else:
        lines.append("- No conflicts detected")
    return "\n".join(lines)
