import json
from pr_audit.naive import build_naive_prompt, naive_verdicts
from pr_audit.schemas import Hunk


def hs():
    return [Hunk(id="a.py:1-2", file="a.py", start=1, end=2, added=["def add_login(): pass"], text="")]


def test_prompt_contains_all_requirements_and_hunks():
    p = build_naive_prompt(["add login", "add rate limit"], hs())
    assert "1. add login" in p and "2. add rate limit" in p and "[a.py:1-2]" in p and "def add_login" in p


def test_parses_verdicts_and_defaults_missing_entries_to_unclear():
    llm = lambda prompt: "text " + json.dumps({"verdicts": [{"req": 1, "verdict": "Done"}, {"req": 9, "verdict": "done"}]})
    v, err = naive_verdicts(llm, ["a", "b"], hs())
    assert v == {1: "done", 2: "unclear"} and err is None


def test_llm_failure_is_reported_not_silent():
    def boom(prompt): raise RuntimeError("all providers failed (last: groq HTTP 429)")
    v, err = naive_verdicts(boom, ["a"], hs())
    assert v == {1: "unclear"} and "429" in err
