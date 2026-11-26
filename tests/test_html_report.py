import json, re
from pr_audit.audit import Audit, ReqResult
from pr_audit.html_report import build_data, render_html
from pr_audit.schemas import Hunk, PRBundle


def make(evil=False):
    t = "</script><img src=x onerror=alert(1)>" if evil else "x"
    hs = [Hunk(id="a.py:1-3", file="a.py", start=1, end=3, added=["def login(): pass"], text="@@ -0,0 +1,1 @@\n+def login(): pass"),
          Hunk(id="b.py:1-2", file="b.py", start=1, end=2, added=["print(1)"], text="@@ -0,0 +1,1 @@\n+print(1)"),
          Hunk(id="tests/t.py:1-2", file="tests/t.py", start=1, end=2, added=["assert 1"], text="+assert 1")]
    b = PRBundle(source="https://github.com/o/r/pull/1", title="T " + t, ask="x", hunks=hs)
    reqs = [ReqResult(1, "add login " + t, "done", .9, [("a.py:1-3", .9, ["def login(): pass"])], "ok"),
            ReqResult(2, "add logout", "missing", .1, [], ""),
            ReqResult(3, "add audit log", "unclear", .3, [], "judge error: x")]
    return Audit(b, reqs, "unclear", {}, [("b.py:1-2", .1)], 40, "significant gaps", ["coverage 0.50 over 2 decided"], False)


def test_breakdown_matches_rank_formula():
    d = build_data(make())
    bd = d["breakdown"]
    assert [r["id"] for r in bd["decided"]] == [1, 2] and bd["coverage"] == 0.5 and bd["creep_penalty"] == 5
    assert round(bd["coverage"] * 100) - bd["creep_penalty"] == 45   # what the UI derives; run_audit gives the real rank
    assert [r["id"] for r in bd["excluded"]] == [3]
    assert d["hunks"][0]["claimed_by"] == [1] and d["hunks"][1]["creep"] is True


def test_html_is_self_contained_and_script_safe():
    h = render_html(make(evil=True))
    assert h.count("</script>") == 2          # the data block + the app script only: PR text cannot close either
    data = re.search(r'id="data">(.*?)</script>', h, re.S).group(1)
    assert json.loads(data)["reqs"][0]["text"].startswith("add login </script>")
    assert "http://" not in h.replace("http://www.w3.org", "") and "src=\"http" not in h
    assert "innerHTML" in h and h.count("innerHTML") == 1   # only the constant ring svg
