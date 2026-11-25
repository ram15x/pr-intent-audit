from pr_audit.coverage import features, orphan_flags, FEATURE_NAMES


def test_all_covered_vs_one_uncovered():
    covered = [[0.9, 0.1], [0.2, 0.8]]
    gap = [[0.9, 0.1], [0.2, 0.1]]
    fc, fg = dict(zip(FEATURE_NAMES, features(covered))), dict(zip(FEATURE_NAMES, features(gap)))
    assert fc["frac_req_cov_0.5"] == 1.0 and fg["frac_req_cov_0.5"] == 0.5
    assert fg["min_best"] < fc["min_best"]


def test_orphans():
    assert orphan_flags([[0.9, 0.1, 0.2]], 0.5) == [False, True, True]


def test_empty_is_safe():
    assert features([]) == [0.0] * len(FEATURE_NAMES)
