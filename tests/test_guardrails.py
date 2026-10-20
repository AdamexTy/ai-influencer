import guardrails


def _valid_plan(**overrides):
    plan = {
        "niche": "Science",
        "topic": "How articulated buses bend without tipping",
        "title": "How Articulated Buses Bend Without Tipping!",
        "script": " ".join(["This"] * 70),
        "keywords": ["engineering", "bus", "physics", "suspension", "urban"],
        "description": "A short science explainer.",
        "hashtags": ["science", "engineering"],
    }
    plan.update(overrides)
    return plan


def test_guardrails_accepts_valid_plan():
    ok, why = guardrails.check(_valid_plan(), {"videos": []})
    assert ok, why


def test_guardrails_rejects_exact_duplicate_topic():
    mem = {"videos": [{"title": "Other", "topic": "How articulated buses bend without tipping"}]}
    ok, why = guardrails.check(_valid_plan(), mem)
    assert not ok
    assert "duplicate topic" in why


def test_guardrails_rejects_near_duplicate_title():
    mem = {"videos": [{"title": "Solar Just Beat Nuclear Power Globally", "topic": "Solar and nuclear milestones"}]}
    plan = _valid_plan(
        title="Solar Energy Just Beat Nuclear Worldwide!",
        topic="What changed in global solar versus nuclear output"
    )
    ok, why = guardrails.check(plan, mem)
    assert not ok
    assert "near-duplicate" in why


def test_guardrails_rejects_malformed_plan_without_traceback():
    ok, why = guardrails.check("not-a-plan", {"videos": []})
    assert not ok
    assert "plan is not" in why
