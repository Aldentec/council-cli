from council.application.decision_ledger import (
    DecisionLedger,
    coordinator_state,
    detect_contradictions,
    parse_revision,
)


def test_detect_reddit_contradiction_without_revision():
    ledger = DecisionLedger()
    ledger.upsert(
        topic="Reddit ads",
        status="active",
        statement="Delay Reddit ads until direct customer interviews are completed.",
    )

    contradictions = detect_contradictions(
        ledger,
        "Jordan",
        "We should spend $10k on Reddit next week to test traction.",
    )

    assert len(contradictions) == 1
    assert contradictions[0].speaker == "Jordan"


def test_parse_revision_requires_topic_and_suggestion():
    revision = parse_revision(
        "PROPOSED REVISION\n"
        "Topic: Reddit ads\n"
        "Suggestion: Run a constrained budget experiment.\n"
        "Reason: Gather controlled evidence.\n"
        "Risk: Could distract from interviews.\n"
        "Trigger: KPI guardrails are set.\n"
        "Approver: Meeting owner\n"
    )

    assert revision is not None
    assert revision.topic == "Reddit ads"
    assert "constrained budget" in revision.suggestion


def test_coordinator_state_includes_conflict_and_revisions():
    ledger = DecisionLedger()
    ledger.upsert(
        topic="Reddit ads",
        status="active",
        statement="Delay Reddit ads until direct customer interviews are completed.",
    )
    contradictions = detect_contradictions(
        ledger,
        "Sam",
        "I recommend allocating budget for Reddit immediately.",
    )
    revision = parse_revision(
        "PROPOSED REVISION\n"
        "Topic: Reddit ads\n"
        "Suggestion: Time-boxed spend test.\n"
    )

    state = coordinator_state(ledger, [revision] if revision else [], contradictions)

    assert "Current decisions" in state
    assert "Proposed revisions" in state
    assert "Consistency check" in state
    assert "Sam" in state
