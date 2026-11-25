from pr_audit.requirements import clean_ask, split_requirements

ISSUE = """# Issue #35: Concurrent calls share temp paths

## Environment
- OS: Linux
- Python: 3.12

## Expected
- [ ] Each call should use a unique temp directory
- [ ] Temp files must be removed after the call
- [x] Add a regression test

```
Traceback (most recent call last): boom
```
"""


def test_boilerplate_and_code_stripped():
    c = clean_ask(ISSUE)
    assert "Linux" not in c and "Traceback" not in c and "unique temp" in c


def test_checklist_split():
    r = split_requirements(ISSUE)
    assert [x.text for x in r] == ["Each call should use a unique temp directory",
                                   "Temp files must be removed after the call",
                                   "Add a regression test"]


def test_prose_fallback():
    r = split_requirements("Login is broken. We should add rate limiting to the login endpoint. It must return 429 after five tries.")
    assert len(r) == 2 and all(not x.unclear for x in r)
