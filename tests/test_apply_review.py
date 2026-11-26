import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import apply_review as A


def _gold(tmp):
    g = [{"pr": "https://github.com/o/r/pull/1", "title": "t", "creep_hunks": [{"hunk": "a.py:1-2", "confidence": "low"}],
          "requirements": [{"id": 1, "text": "x", "status": "done", "hunks": ["a.py:1-2"]}, {"id": 2, "text": "y", "status": "unclear", "hunks": []}]}]
    (tmp / "gold_draft.json").write_text(json.dumps(g)); (tmp / "gold_extra_draft.json").write_text("[]"); (tmp / "gold_large_draft.json").write_text("[]")


SHEET = """1. **DONE** (medium) R1: x
   your_label: unclear   why: depends on outside code
2. **UNCLEAR** (low) R2: y
   your_label: ____   why: ____
- CREEP label: `a.py:1-2`
   your_label (creep|not creep): not creep
"""


def test_apply_changes_status_and_removes_creep(tmp_path):
    _gold(tmp_path)
    problems, report, ok = A.apply(tmp_path, SHEET)
    assert ok and not problems and len(report) == 2
    g = json.loads((tmp_path / "gold_draft.json").read_text())[0]
    r1, r2 = g["requirements"]
    assert (r1["status"], r1["claude_label"], r1["labeled_by"], r1["owner_reviewed"]) == ("unclear", "done", "owner", True)
    assert "owner_reviewed" not in r2 and g["creep_hunks"] == []


def test_stale_sheet_is_refused_and_nothing_is_written(tmp_path):
    _gold(tmp_path)
    problems, _r, ok = A.apply(tmp_path, SHEET.replace("**DONE**", "**PARTIAL**"))
    assert not ok and "sheet says PARTIAL" in problems[0]
    assert json.loads((tmp_path / "gold_draft.json").read_text())[0]["requirements"][0]["status"] == "done"


def test_invalid_label_is_refused(tmp_path):
    _gold(tmp_path)
    assert not A.apply(tmp_path, SHEET.replace("unclear   why", "maybe   why"))[2]
