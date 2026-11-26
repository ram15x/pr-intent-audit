import json, threading, time, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
from pr_audit.server import App, make_handler, _clean


def _start(tmp_path, runner):
    app = App(Path("."), tmp_path / "d", tmp_path / "models", 0, runner)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app)); app.port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return app, srv, f"http://127.0.0.1:{app.port}"


def _req(url, method="GET", body=None, cookie=None, host=None, ctype="application/json"):
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    r.add_header("Content-Type", ctype)
    if cookie: r.add_header("Cookie", cookie)
    if host: r.add_header("Host", host)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def _fake(job):
    job.emit({"stage": "start", "n": 1, "hunks": 3})
    job.emit({"stage": "requirement", "i": 1, "n": 1, "text": "x", "status": "done", "note": "", "evidence": ["a:1-2"]})
    return {"data": {"reqs": [{}], "rank": 90}, "markdown": "# md", "rank": 90, "band": "Good", "title": "T", "source": "https://github.com/o/r/pull/1"}


def test_full_lifecycle_and_auth(tmp_path):
    app, srv, base = _start(tmp_path, _fake)
    try:
        code, _, h = _req(base + "/")
        assert code == 200 and "pa=" in h["Set-Cookie"] and "frame-src" in h["Content-Security-Policy"]
        ck = f"pa={app.token}"
        assert _req(base + "/api/status")[0] == 403                      # no cookie
        assert _req(base + "/api/status", cookie=ck, host="evil.example:80")[0] == 403   # wrong Host (DNS rebinding)
        assert _req(base + "/api/audit", "POST", {"mode": "pr", "url": "https://github.com/o/r/pull/1"}, cookie=ck, ctype="text/plain")[0] == 415
        assert _req(base + "/api/audit", "POST", {"mode": "pr", "url": "http://evil"}, cookie=ck)[0] == 400
        code, body, _ = _req(base + "/api/audit", "POST", {"mode": "pr", "url": "https://github.com/o/r/pull/1", "ask": "- x"}, cookie=ck)
        assert code == 202; jid = json.loads(body)["job"]
        for _ in range(50):
            j = json.loads(_req(base + f"/api/jobs/{jid}", cookie=ck)[1])
            if j["state"] in ("done", "error"): break
            time.sleep(0.05)
        assert j["state"] == "done" and j["run_id"] and any(e["stage"] == "requirement" for e in j["events"])
        rid = j["run_id"]
        assert json.loads(_req(base + "/api/runs", cookie=ck)[1])[0]["rank"] == 90
        assert b"PR Intent Audit" in _req(base + f"/api/runs/{rid}/report.html", cookie=ck)[1]
        assert _req(base + f"/api/runs/{rid}/report.md", cookie=ck)[1] == b"# md"
        assert _req(base + "/api/runs/..%2f..%2fetc/data", cookie=ck)[0] == 404      # no path traversal
        assert _req(base + f"/api/runs/{rid}", "DELETE", cookie=ck)[0] == 200
        assert json.loads(_req(base + "/api/runs", cookie=ck)[1]) == []
    finally:
        srv.shutdown()


def test_one_audit_at_a_time_and_errors_are_reported(tmp_path):
    gate = threading.Event()
    def slow(job): gate.wait(3); raise ValueError("boom")
    app, srv, base = _start(tmp_path, slow)
    try:
        ck = f"pa={app.token}"; _req(base + "/")
        body = {"mode": "pr", "url": "https://github.com/o/r/pull/1"}
        c1, b1, _ = _req(base + "/api/audit", "POST", body, cookie=ck); assert c1 == 202
        assert _req(base + "/api/audit", "POST", body, cookie=ck)[0] == 409
        gate.set(); jid = json.loads(b1)["job"]
        for _ in range(50):
            j = json.loads(_req(base + f"/api/jobs/{jid}", cookie=ck)[1])
            if j["state"] == "error": break
            time.sleep(0.05)
        assert j["state"] == "error" and j["error"] == "boom"
    finally:
        srv.shutdown()


def test_clean_validates():
    import pytest
    with pytest.raises(ValueError): _clean({"mode": "local", "repo": "", "ask": ""})
    with pytest.raises(ValueError): _clean({"mode": "x"})
    assert _clean({"mode": "local", "repo": ".", "ask": "- a", "escalate": 1})["escalate"] is True


def test_real_runner_on_a_local_repo_with_stub_judge(tmp_path, monkeypatch):
    import subprocess
    from pr_audit import pipeline as P
    from pr_audit.lexical import lexical_scorer
    from pr_audit.schemas import Judgment, Verdict
    repo = tmp_path / "r"; repo.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)
    run("init", "-q"); (repo / "a.py").write_text("def f():\n    return 1\n"); run("add", "."); run("commit", "-qm", "init")
    (repo / "a.py").write_text("def f():\n    return 1\n\ndef retry_with_backoff(fn):\n    return fn()\n"); run("commit", "-qam", "retry")

    def stub_pipeline(root, models, local, retrieval, escalate, context=False, log=None):
        def judge(i, text, top):
            h = top[0]; q = [l for l in h.added if "retry" in l][:1]
            return Judgment(req_id=i, verdict=Verdict.done, hunk_ids=[h.id], quotes=q, reason="stub")
        return P.Pipeline(lexical_scorer(), None, {"tau": 0.5, "band": 0.1}, judge, "mode: stub", True, None)
    monkeypatch.setattr(P, "make_pipeline", stub_pipeline)
    app = App(Path("."), tmp_path / "d", tmp_path / "m", 0)
    job = app.start({"mode": "local", "repo": str(repo), "base": "HEAD~1", "head": "HEAD", "ask": "- add retry with backoff",
                     "url": "", "retrieval": "lexical", "escalate": False, "context": False})
    for _ in range(100):
        if job.state in ("done", "error"): break
        time.sleep(0.05)
    assert job.state == "done", job.error
    stages = [e["stage"] for e in job.events]
    assert stages[:2] == ["fetch", "setup"] and "requirement" in stages
    run_ = app.load_run(job.run_id)
    assert run_["rank"] == 100 and run_["data"]["reqs"][0]["status"] == "done" and "retry" in run_["markdown"].lower()
