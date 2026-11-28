from pr_audit.requirements import requirement_kind


def test_execution_requirements_are_flagged():
    for t in ("Run `pytest -q tests/test_api.py -k chat` to verify 200 response",
              "All tests pass and CI must be green", "Execute the test suite before merging", "ensure the build passes"):
        assert requirement_kind(t) == "execution", t


def test_implementation_requirements_stay_implementation():
    for t in ("Add unit tests for invalid email addresses", "Remove the obsolete pytest audit exemption from CI and add a changelog entry",
              "Update the CI workflow to cache pip", "Add retry with backoff to the fetch client"):
        assert requirement_kind(t) == "implementation", t
