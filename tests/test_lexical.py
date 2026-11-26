from pr_audit.lexical import lexical_scorer


def test_ranks_the_matching_hunk_first():
    s = lexical_scorer()
    req = "Add rate limiting middleware for the login endpoint"
    hunks = ["def unrelated_helper(): return 1", "class RateLimiter:\n    def login_endpoint(self): pass", "README text about docs"]
    sc = s([(req, h) for h in hunks])
    assert sc.index(max(sc)) == 1


def test_empty_requirement_scores_zero():
    assert lexical_scorer()([("the and for", "anything here")]) == [0.0]


def test_identifiers_and_boost_prefers_exact_named_hunk():
    from pr_audit.retrieval import identifiers, identifier_boost
    assert identifiers("Add `sync_compose_profiles` in `roles/x/reconcile.yml` and call handleLogin") == \
        ["sync_compose_profiles", "roles/x/reconcile.yml", "handleLogin"]
    req = "Add `sync_compose_profiles` to reconcile"
    a = "roles/x/other.yml\n+ reconcile reconcile reconcile compose"
    b = "roles/x/reconcile.yml\n+ def sync_compose_profiles(): pass"
    base = lambda pairs: [1.0 if h is a else 0.5 for _, h in pairs]       # base score prefers the wrong hunk
    s = identifier_boost(base)([(req, a), (req, b)])
    assert s[1] > s[0]
