from pr_audit.audit import run_audit
from pr_audit.report import render_markdown
from pr_audit.schemas import Hunk, PRBundle


class FakeClf:
    classes_ = [0, 1, 2]
    def predict_proba(self, X): return [[0.2, 0.6, 0.2]]


def bundle():
    hs = [Hunk(id="a.py:1-3", file="a.py", start=1, end=3, added=["def add_login():", "    return True"], text=""),
          Hunk(id="b.py:1-3", file="b.py", start=1, end=3, added=["def unrelated_thing():", "    pass"], text="")]
    return PRBundle(source="https://github.com/o/r/pull/1", title="t", ask_source="agent_prompt", hunks=hs,
                    ask="- We should add login support\n- We should add rate limiting\n")


def scorer(pairs):   # fake relevance: login req matches a.py only; rate limiting matches nothing
    return [0.9 if ("login" in r and "add_login" in h) else 0.05 for r, h in pairs]


def test_audit_end_to_end():
    a = run_audit(bundle(), scorer, FakeClf(), tau=0.5, band=0.1)
    st = {r.id: r.status for r in a.reqs}
    assert st == {1: "done", 2: "missing"}
    assert a.reqs[0].evidence[0][0] == "a.py:1-3" and "def add_login():" in a.reqs[0].evidence[0][2]
    assert a.rank == 50 - 5          # coverage 0.5, minus one creep candidate (b.py)
    assert [h for h, _ in a.creep] == ["b.py:1-3"]
    md = render_markdown(a)
    assert "MISSING" in md and "DONE" in md and "never approves" in md


def test_audit_with_judge_decides_status_and_partial_counts_half():
    from pr_audit.schemas import Judgment, Verdict
    def judge(i, t, top):
        if i == 1:
            return Judgment(req_id=1, verdict=Verdict.partial, hunk_ids=["a.py:1-3"], quotes=["def add_login():"], reason="login stub only")
        return Judgment(req_id=2, verdict=Verdict.unclear, reason="judge error: RuntimeError")
    a = run_audit(bundle(), scorer, FakeClf(), tau=0.5, band=0.1, judge=judge)
    assert [r.status for r in a.reqs] == ["partial", "unclear"]
    assert a.reqs[0].evidence[0][0] == "a.py:1-3"
    assert a.rank == 50 - 5          # partial counts 0.5 over 1 decided requirement, minus creep
    assert "PARTIAL" in render_markdown(a)


def test_judge_quotes_are_shown_only_under_the_hunk_that_contains_them():
    from pr_audit.schemas import Judgment, Verdict
    def judge(i, t, top):
        return Judgment(req_id=i, verdict=Verdict.done, hunk_ids=["a.py:1-3", "b.py:1-3"], quotes=["def add_login():"], reason="x")
    a = run_audit(bundle(), scorer, FakeClf(), tau=0.5, band=0.1, judge=judge)
    ev = {h: q for h, _, q in a.reqs[0].evidence}
    assert ev["a.py:1-3"] == ["def add_login():"] and ev["b.py:1-3"] == []
