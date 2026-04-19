from __future__ import annotations

import re

from council.domain.models.agent import AgentConfig

# Common single-character transpositions/insertions that fool exact matching.
# Maps a normalised misspelling pattern → canonical word.
# Only covers words that appear in ROLE_AFFINITIES topic sets.
_FUZZY_CORRECTIONS: dict[str, str] = {}


def _build_fuzzy_index() -> None:
    """Populate _FUZZY_CORRECTIONS from all topic keywords in ROLE_AFFINITIES."""
    # Imported lazily here to avoid circular import at module level.
    # Called once after ROLE_AFFINITIES is defined.
    for _, topic_keys in ROLE_AFFINITIES:
        for word in topic_keys:
            if len(word) < 4:
                continue
            # Allow one deletion anywhere in the word as a typo signature
            for i in range(len(word)):
                variant = word[:i] + word[i + 1:]
                if variant not in _FUZZY_CORRECTIONS:
                    _FUZZY_CORRECTIONS[variant] = word
            # Allow one insertion (represented by checking common doubled letters)
            for i in range(len(word)):
                doubled = word[:i] + word[i] + word[i:]
                if doubled not in _FUZZY_CORRECTIONS:
                    _FUZZY_CORRECTIONS[doubled] = word

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "to", "of", "in", "on", "at", "for",
    "with", "by", "from", "and", "or", "but", "not", "this", "that",
    "it", "i", "we", "you", "he", "she", "they", "what", "how", "why",
    "when", "where", "who", "which", "think", "about", "our", "your",
    "my", "their", "us", "me", "him", "her", "just", "so", "if", "as",
})

ALL_ROOM_CUES = ["everyone", "everybody", "all of you", "whole room", "all advisors"]
DIRECT_CUES = ["what do you think", "thoughts", "do you agree", "weigh in", "tell me", "your take", "your view"]
FOLLOWUP_CUES = [
    "elaborate", "explain", "what do you mean", "tell me more", "go on",
    "can you", "you said", "you mentioned", "expand on", "how so",
    "say more", "why is that", "what about that", "be more specific",
]

# Maps substrings found in an agent's role → topic keywords that boost that role.
# Bridges the gap when message vocabulary differs from persona vocabulary
# (e.g. "paid ads" won't match "finance" lexically, but the affinity map connects them).
ROLE_AFFINITIES: list[tuple[frozenset[str], frozenset[str]]] = [
    (
        frozenset({"cfo", "finance", "financial", "treasurer"}),
        frozenset({"cost", "spend", "budget", "revenue", "profit", "money", "pay", "paid",
                   "price", "pricing", "roi", "cac", "ltv", "advertising", "ads", "ad",
                   "burn", "cash", "margin", "economics", "investment", "expense"}),
    ),
    (
        frozenset({"cto", "technical", "engineer", "engineering", "architect"}),
        frozenset({"code", "technical", "api", "database", "performance", "security",
                   "infrastructure", "deploy", "build", "system", "software", "backend",
                   "frontend", "stack", "latency", "scalability", "refactor"}),
    ),
    (
        frozenset({"ceo", "founder", "chief executive", "president", "director"}),
        frozenset({"strategy", "growth", "market", "vision", "product", "customer",
                   "brand", "launch", "scale", "investor", "fundraise", "narrative"}),
    ),
    (
        frozenset({"marketing", "growth", "brand", "demand"}),
        frozenset({"campaign", "brand", "audience", "conversion", "funnel", "ads",
                   "advertising", "content", "social", "seo", "traffic", "creative",
                   "copy", "messaging", "channel", "engagement", "retention"}),
    ),
    (
        frozenset({"legal", "compliance", "risk", "counsel"}),
        frozenset({"legal", "law", "compliance", "risk", "liability", "contract",
                   "regulation", "privacy", "gdpr", "terms", "policy"}),
    ),
    (
        frozenset({"devil", "skeptic", "critic", "advocate"}),
        frozenset({"risk", "wrong", "fail", "problem", "issue", "challenge",
                   "concern", "assumption", "flaw", "downside", "worst"}),
    ),
    (
        frozenset({"design", "designer", "ux", "ui", "creative", "art"}),
        frozenset({"design", "ux", "visual", "interface", "aesthetic", "color",
                   "layout", "typography", "user", "experience", "branding"}),
    ),
    (
        frozenset({"product", "pm", "manager"}),
        frozenset({"feature", "roadmap", "requirement", "feedback", "sprint",
                   "backlog", "priority", "scope", "milestone", "user story"}),
    ),
]


def _fuzzy_normalize(word: str) -> str:
    """Return the canonical spelling if this word looks like a known typo, else return it unchanged."""
    if not _FUZZY_CORRECTIONS:
        _build_fuzzy_index()
    return _FUZZY_CORRECTIONS.get(word, word)


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {_fuzzy_normalize(w) for w in words if w not in _STOP_WORDS and len(w) > 2}


def score_relevance(message: str, agent: AgentConfig) -> float:
    msg_tokens = tokenize(message)
    agent_tokens = tokenize(f"{agent.role} {agent.name} {agent.persona}")
    if not msg_tokens:
        return 0.0
    return len(msg_tokens & agent_tokens) / len(msg_tokens)


def affinity_boost(message: str, agent: AgentConfig) -> float:
    role_lower = agent.role.lower()
    msg_tokens = tokenize(message)
    for role_keys, topic_keys in ROLE_AFFINITIES:
        if any(k in role_lower for k in role_keys):
            overlap = msg_tokens & topic_keys
            if overlap:
                return min(0.4, 0.15 + len(overlap) * 0.05)
    return 0.0
