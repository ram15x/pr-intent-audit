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


def test_process_and_template_noise_is_dropped():
    ask = """- [ ] The login endpoint returns 429 after five tries
- [ ] I have tested this locally
- [ ] The pull request has been reviewed by at least one other team member
- Related issues:
- #89 - DPL-403
- **Estimated hours**: 1
"""
    assert [r.text for r in split_requirements(ask)] == ["The login endpoint returns 429 after five tries"]


def test_ticket_style_ids_with_real_text_are_kept():
    r = split_requirements("- AC-01: Pinned actionlint checks workflows on pull requests\n- AC-02: Actions use full commit SHAs\n")
    assert len(r) == 2


def test_options_under_an_intro_line_are_optional():
    ask = """Fix needed.

Possible approaches (to evaluate, not commit to):
- Split the vendor bundle with manualChunks
- Lazy-load routes

Acceptance:
- The build no longer warns about chunk size
"""
    r = split_requirements(ask)
    assert [(x.text, x.optional) for x in r] == [("Split the vendor bundle with manualChunks", True),
                                               ("Lazy-load routes", True),
                                               ("The build no longer warns about chunk size", False)]


def test_emoji_heading_repro_steps_and_template_noise_are_dropped():
    from pr_audit.requirements import split_requirements
    txt = ("### 🪜 How to reproduce\n1. Go to the page\n2. Hover over the button\n### Expected behaviour\n- The icon should lighten when hovered\n"
           "- **Python version**: 3.6.2\n- **Testing**: Relevant tests have passed.\n- Please run the following to update the config:\n- **Fix**: add the cache layer")
    got = [r.text for r in split_requirements(txt)]
    assert "**Fix**: add the cache layer" in got
    assert not any("Go to" in t or "Hover over" in t or "Python version" in t or "Relevant tests" in t or "Please run" in t for t in got)
