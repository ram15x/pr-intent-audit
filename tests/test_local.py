import subprocess
import pytest
from pr_audit.local import bundle_from_git, _check_ref


def git(repo, *a):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("def a():\n    return 1\n")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "one")
    (tmp_path / "a.py").write_text("def a():\n    return 1\n\ndef login():\n    return True\n")
    (tmp_path / "poetry.lock").write_text("x\n")
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "two")
    return tmp_path


def test_bundle_from_commit_range_has_real_hunks_and_drops_noise(repo):
    b = bundle_from_git(repo, "- add a login function", base="HEAD~1", head="HEAD")
    assert b.ask_source == "agent_prompt" and b.source.startswith("local:")
    assert [h.file for h in b.hunks] == ["a.py"] and any("def login" in l for l in b.hunks[0].added)
    assert any("poetry.lock" in n for n in b.notes)


def test_working_tree_diff(repo):
    (repo / "a.py").write_text("def a():\n    return 2\n\ndef login():\n    return True\n")
    b = bundle_from_git(repo, "x", base="HEAD", head=None)
    assert b.hunks and "working-tree" in b.source


def test_refs_cannot_inject_options_or_shell(repo):
    for bad in ("--output=/tmp/x", "HEAD; rm -rf /", "a b", ""):
        with pytest.raises(ValueError):
            _check_ref(bad)
    with pytest.raises(ValueError):
        bundle_from_git(repo, "x", base="no-such-ref", head="HEAD")
