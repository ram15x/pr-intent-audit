from pr_audit.diffs import parse_diff
from pr_audit.schemas import Judgment, Verdict
from pr_audit.verify import verify_judgment

DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,4 @@
 def greet(name):
-    return "hi"
+    if not name:
+        raise ValueError("name required")
+    return f"hi {name}"
diff --git a/package-lock.json b/package-lock.json
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,1 +1,1 @@
-a
+b
"""


def test_parse_drops_noise_and_ids():
    hunks, notes = parse_diff(DIFF)
    assert [h.id for h in hunks] == ["app.py:1-4"]
    assert any("package-lock.json" in n for n in notes)


def test_real_evidence_passes():
    hunks, _ = parse_diff(DIFF)
    j = Judgment(req_id=1, verdict=Verdict.done, hunk_ids=["app.py:1-4"],
                 quotes=['raise ValueError("name required")'])
    assert verify_judgment(j, hunks).verdict == Verdict.done


def test_fabricated_quote_is_downgraded():
    hunks, _ = parse_diff(DIFF)
    j = Judgment(req_id=1, verdict=Verdict.done, hunk_ids=["app.py:1-4"],
                 quotes=["validate_email(name)"])
    out = verify_judgment(j, hunks)
    assert out.verdict == Verdict.unclear and out.downgraded_because


def test_fake_hunk_and_missing_evidence_downgraded():
    hunks, _ = parse_diff(DIFF)
    j = Judgment(req_id=1, verdict=Verdict.done, hunk_ids=["nope.py:1-2"], quotes=["x"])
    assert verify_judgment(j, hunks).verdict == Verdict.unclear
    j2 = Judgment(req_id=2, verdict=Verdict.partial)
    assert verify_judgment(j2, hunks).verdict == Verdict.unclear


def test_missing_verdict_needs_no_quotes():
    hunks, _ = parse_diff(DIFF)
    j = Judgment(req_id=3, verdict=Verdict.missing, reason="searched app.py")
    assert verify_judgment(j, hunks).verdict == Verdict.missing
