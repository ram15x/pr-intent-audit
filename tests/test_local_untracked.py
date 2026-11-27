import subprocess
from pr_audit.local import bundle_from_git


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=a@b.c", "-c", "user.name=t", *a], check=True, capture_output=True)


def test_untracked_new_file_is_in_working_tree_audit(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "."); _git(tmp_path, "commit", "-qm", "init")
    (tmp_path / "newmod.py").write_text("def validate_email(s):\n    return '@' in s\n")
    (tmp_path / "blob.bin").write_bytes(b"\0\1\2")
    b = bundle_from_git(tmp_path, "add validate_email", base="HEAD", head=None)
    files = {h.file for h in b.hunks}
    assert "newmod.py" in files and "blob.bin" not in files
    assert any("validate_email" in l for h in b.hunks for l in h.added)


def test_commit_range_ignores_untracked(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "."); _git(tmp_path, "commit", "-qm", "init")
    (tmp_path / "new.py").write_text("y = 2\n")
    assert bundle_from_git(tmp_path, "t", base="HEAD", head="HEAD").hunks == []
