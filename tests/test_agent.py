import pytest

import agent


def test_parse_json_response_handles_code_fence():
    text = """```json\n{\"title\":\"x\",\"topic\":\"y\"}\n```"""
    parsed = agent._parse_json_response(text)
    assert parsed["title"] == "x"


def test_parse_json_response_rejects_empty():
    with pytest.raises(ValueError):
        agent._parse_json_response("  ")
