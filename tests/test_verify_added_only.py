from pr_audit.schemas import Hunk, Judgment, Verdict
from pr_audit.verify import verify_judgment, quotes_in


def _h():
    return Hunk(id="a.py:1-4", file="a.py", start=1, end=4, added=["def new_fn():"], removed=["def old_fn():"],
                text=" import os\n-def old_fn():\n+def new_fn():\n     return 1")


def _j(q):
    return Judgment(req_id=1, verdict=Verdict.done, hunk_ids=["a.py:1-4"], quotes=[q], reason="r")


def test_legacy_accepts_context_line():
    assert verify_judgment(_j("import os"), [_h()], added_only=False).verdict == Verdict.done


def test_added_only_rejects_context_and_removed():
    for q in ("import os", "def old_fn():"):
        j = verify_judgment(_j(q), [_h()], added_only=True)
        assert j.verdict == Verdict.unclear and j.downgraded_because


def test_added_only_accepts_added_line_even_with_plus_marker():
    assert verify_judgment(_j("+def new_fn():"), [_h()], added_only=True).verdict == Verdict.done
    assert quotes_in(_h(), ["import os"], added_only=True) == []
