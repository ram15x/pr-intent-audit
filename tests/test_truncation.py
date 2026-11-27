from pr_audit.requirements import split_requirements_ex


def test_reports_dropped_requirements():
    ask = "\n".join(f"- The service must handle case number {i} correctly" for i in range(15))
    reqs, dropped = split_requirements_ex(ask, max_reqs=12)
    assert len(reqs) == 12 and dropped == 3
    assert split_requirements_ex(ask, max_reqs=20)[1] == 0
