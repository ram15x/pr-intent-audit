import random
from pr_audit.inject import build_cases, partial, creep
from pr_audit.schemas import PRBundle, Hunk, Verdict


def H(f, i):
    return Hunk(id=f"{f}:{i}-{i+2}", file=f, start=i, end=i + 2, added=["x"], text="x")


def PR(name, files):
    return PRBundle(source=name, ask=f"ask {name}", hunks=[H(f, k * 10) for k, f in enumerate(files)])


A = PR("A", ["a.py", "b.py", "c.py", "d.py", "tests/test_a.py"])
B = PR("B", ["z.py", "y.py"])


def test_all_four_kinds_and_labels():
    cases = build_cases([A, B], seed=1)
    kinds = {(c.case_id.split('#')[0], c.kind) for c in cases}
    assert {"clean", "mismatch", "creep", "partial"} <= {k for _, k in kinds}
    for c in cases:
        if c.kind == "mismatch":
            assert c.label == Verdict.missing
        if c.kind == "partial":
            assert c.label == Verdict.partial


def test_partial_never_drops_everything_or_tests_only():
    c = partial(A, random.Random(0))
    assert c and 0 < len(c.meta["dropped"]) < 4
    assert partial(B, random.Random(0)) is None      # too few substantive hunks


def test_creep_ids_marked_and_not_colliding():
    c = creep(A, B, random.Random(0))
    assert c.unrequested and all(u.startswith("foreign::") for u in c.unrequested)
    ids = [h.id for h in c.hunks]
    assert len(ids) == len(set(ids))


def test_composite_truth():
    from pr_audit.inject import composite
    a = PRBundle(source="A", ask="- We should add alpha\n- We should add beta", hunks=[H("a.py", 1)])
    b = PRBundle(source="B", ask="- We should add gamma\n- We should add delta", hunks=[H("b.py", 1)])
    full, part = composite(a, b)
    assert full.label == Verdict.done and part.label == Verdict.partial
    assert len(part.hunks) == 1 and len(full.hunks) == 2
    assert part.meta["reqs_missing_in_partial"] == ["We should add gamma", "We should add delta"]
