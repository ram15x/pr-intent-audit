from pr_audit.pairs import build_pairs, split_of
from pr_audit.schemas import Hunk, PRBundle


def PR(url, ask):
    h = [Hunk(id=f"f{i}.py:1-2", file=f"f{i}.py", start=1, end=2, added=["x = 1"], text="") for i in range(3)]
    return PRBundle(source=url, title="t", ask=ask, hunks=h)


def test_balanced_and_repo_split_consistent():
    bs = [PR("https://github.com/o/r1/pull/1", "- We should add A\n- We should add B"),
          PR("https://github.com/o/r1/pull/2", "- We should add C\n- We should add D"),
          PR("https://github.com/o/r2/pull/3", "- We should add E\n- We should add F")]
    rows = build_pairs(bs)
    assert {r["label"] for r in rows} == {0, 1}
    assert sum(r["label"] for r in rows) == len(rows) / 2
    for repo in {r["repo"] for r in rows}:
        assert len({r["split"] for r in rows if r["repo"] == repo}) == 1
    assert split_of("o/r1") == split_of("o/r1")


def test_map_commit_hunks():
    from pr_audit.commits import map_commit_hunks
    mk = lambda i, f, add: Hunk(id=i, file=f, start=1, end=2, added=add, text="")
    final = [mk("a:1-9", "a.py", ["x = compute(1)", "y = compute(2)"]), mk("b:1-9", "b.py", ["z = other(3)"])]
    commit = [mk("tmp", "a.py", ["x = compute(1)"])]
    assert map_commit_hunks(commit, final) == ["a:1-9"]
    assert map_commit_hunks([mk("t", "c.py", ["x = compute(1)"])], final) == []
