"""Whole-pipeline regression: canned PR + scripted judge -> exact statuses, score, evidence, report text.
Guards the score formula and the evidence rules against accidental change."""
import json
from pr_audit.audit import run_audit
from pr_audit.html_report import build_data, render_html
from pr_audit.judge import judge_requirement
from pr_audit.lexical import lexical_scorer
from pr_audit.report import render_markdown
from pr_audit.schemas import Hunk, PRBundle


def bundle():
    hs = [Hunk(id="auth.py:1-6", file="auth.py", start=1, end=6, added=["def login(user, pw):", "    return check(user, pw)"], text="@@ -0,0 +1,2 @@\n+def login(user, pw):\n+    return check(user, pw)"),
          Hunk(id="limits.py:1-4", file="limits.py", start=1, end=4, added=["def rate_limit(ip):", "    return ip in BUCKET"], text="@@ -0,0 +1,2 @@\n+def rate_limit(ip):\n+    return ip in BUCKET"),
          Hunk(id="misc.py:1-3", file="misc.py", start=1, end=3, added=["print('unrelated cleanup')"], text="@@ -0,0 +1,1 @@\n+print('unrelated cleanup')")]
    return PRBundle(source="golden", title="golden", ask="- add a login function\n- add rate limit for each ip\n- add audit log for admins", hunks=hs)


def scripted(llm_answers):
    def judge(i, t, top):
        return judge_requirement(lambda p: json.dumps(llm_answers[i]), i, t, top, verify=True)
    return judge


ANS = {1: {"verdict": "done", "hunk_ids": ["auth.py:1-6"], "quotes": ["def login(user, pw):"], "reason": "login exists"},
       2: {"verdict": "done", "hunk_ids": ["limits.py:1-4"], "quotes": ["this line is invented"], "reason": "invented quote"},
       3: {"verdict": "missing", "hunk_ids": [], "quotes": [], "reason": "no audit log"}}


def test_golden_scores_statuses_and_evidence():
    a = run_audit(bundle(), lexical_scorer(), None, judge=scripted(ANS))
    assert [r.status for r in a.reqs] == ["done", "unclear", "missing"]       # invented quote is downgraded, never "done"
    assert [e[0] for e in a.reqs[0].evidence] == ["auth.py:1-6"] and a.reqs[0].evidence[0][2] == ["def login(user, pw):"]
    assert a.reqs[1].evidence == []
    # (1 done + 1 missing) / 2 decided = 50; the one unclaimed hunk is listed but not scored. auth.py is cited as evidence, so it is NOT creep.
    assert [c[0] for c in a.creep] == ["misc.py:1-3"] and a.rank == 50
    md = render_markdown(a)
    assert "DONE" in md and "UNCLEAR" in md and "MISSING" in md and "def login(user, pw):" in md
    d = build_data(a)
    assert d["breakdown"]["coverage"] == 0.5 and [r["id"] for r in d["breakdown"]["excluded"]] == [2]
    assert "Copy as PR comment" in render_html(a)


def test_thin_ask_is_flagged():
    b = bundle().model_copy(update={"ask": "make it better"})
    a = run_audit(b, lexical_scorer(), None, judge=scripted({1: ANS[3]}))
    assert any("ask" in n.lower() for n in a.bundle.notes)
