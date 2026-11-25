from pr_audit.lexical import lexical_scorer


def test_ranks_the_matching_hunk_first():
    s = lexical_scorer()
    req = "Add rate limiting middleware for the login endpoint"
    hunks = ["def unrelated_helper(): return 1", "class RateLimiter:\n    def login_endpoint(self): pass", "README text about docs"]
    sc = s([(req, h) for h in hunks])
    assert sc.index(max(sc)) == 1


def test_empty_requirement_scores_zero():
    assert lexical_scorer()([("the and for", "anything here")]) == [0.0]
