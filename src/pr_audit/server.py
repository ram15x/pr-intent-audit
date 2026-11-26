"""Local web app: paste a PR URL (or pick local commits), give the ask, watch requirements resolve, open the evidence report.

Standard library only. Binds to 127.0.0.1. Every API call needs the session cookie set when the page is served and a
Host header for this server (blocks other websites and DNS rebinding from driving your API keys). One audit runs at a
time (free-tier quota). Runs are stored as JSON under the data directory so history survives restarts."""
from __future__ import annotations
import json, secrets, threading, time, traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WEB = Path(__file__).parent / "web"
MAX_BODY = 400_000


class Job:
    def __init__(self, jid: str, params: dict):
        self.id, self.params, self.state = jid, params, "queued"
        self.events: list[dict] = []; self.run_id: str | None = None; self.error: str | None = None
        self.started = time.time(); self.tokens = 0

    def emit(self, ev: dict) -> None:
        ev = dict(ev); ev["t"] = round(time.time() - self.started, 1); self.events.append(ev)

    def view(self, since: int = 0) -> dict:
        return {"id": self.id, "state": self.state, "events": self.events[since:], "next": len(self.events),
                "run_id": self.run_id, "error": self.error, "tokens": self.tokens}


class App:
    def __init__(self, root: Path, data_dir: Path, models: Path, port: int, runner=None):
        self.root, self.models, self.port = root, models, port
        self.runs_dir = data_dir / "runs"; self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(24)
        self.jobs: dict[str, Job] = {}; self.lock = threading.Lock()
        self.runner = runner or self._real_runner

    # ---- audit execution -------------------------------------------------
    def _real_runner(self, job: Job) -> dict:
        from .audit import run_audit
        from .html_report import build_data
        from .report import render_markdown
        from .pipeline import make_pipeline
        p = job.params
        job.emit({"stage": "fetch", "msg": "Fetching the pull request" if p["mode"] == "pr" else "Reading the local diff"})
        if p["mode"] == "pr":
            from .ingest import fetch_pr
            bundle = fetch_pr(p["url"], ask_override=p["ask"] or None)
        else:
            from .local import bundle_from_git
            bundle = bundle_from_git(Path(p["repo"]), p["ask"], p["base"] or "HEAD~1", p["head"] or None)
        if not bundle.hunks:
            raise ValueError("No auditable hunks in this diff.")
        job.emit({"stage": "setup", "msg": f"{len(bundle.hunks)} hunks to search"})
        pl = make_pipeline(self.root, self.models, False, "lexical" if p["retrieval"] == "lexical" else "auto", bool(p["escalate"]),
                           context=bool(p.get("context")))
        audit = run_audit(bundle, pl.scorer, pl.clf, tau=pl.cfg["tau"], band=pl.cfg["band"], judge=pl.judge, progress=job.emit)
        if pl.llm is not None:
            job.tokens = pl.llm.calls.get("groq_tokens", 0)
            job.emit({"stage": "usage", "calls": dict(pl.llm.calls)})
        return {"data": build_data(audit, pl.info), "markdown": render_markdown(audit, pl.info), "rank": audit.rank, "band": audit.band,
                "title": bundle.title or bundle.source, "source": bundle.source}

    def _work(self, job: Job) -> None:
        job.state = "running"
        try:
            res = self.runner(job)
            rid = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)
            rec = {"id": rid, "created": time.time(), "title": res["title"], "source": res["source"], "rank": res["rank"], "band": res["band"],
                   "mode": job.params["mode"], "escalate": bool(job.params["escalate"]), "tokens": job.tokens,
                   "data": res["data"], "markdown": res.get("markdown", "")}
            (self.runs_dir / f"{rid}.json").write_text(json.dumps(rec), encoding="utf-8")
            job.run_id, job.state = rid, "done"
        except Exception as e:                                   # shown to the user; never leaves the job hanging
            job.state, job.error = "error", _friendly(e)
            if not isinstance(e, (ValueError, RuntimeError)):
                job.events.append({"stage": "trace", "msg": traceback.format_exc()[-1200:]})

    def start(self, params: dict) -> Job | None:
        with self.lock:
            if any(j.state in ("queued", "running") for j in self.jobs.values()):
                return None
            job = Job(secrets.token_hex(4), params); self.jobs[job.id] = job
        threading.Thread(target=self._work, args=(job,), daemon=True).start()
        return job

    # ---- history ---------------------------------------------------------
    def list_runs(self) -> list[dict]:
        out = []
        for f in self.runs_dir.glob("*.json"):
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                out.append({k: r.get(k) for k in ("id", "created", "title", "source", "rank", "band", "mode", "escalate", "tokens")}
                           | {"requirements": len(r["data"].get("reqs", []))})
            except Exception:
                continue
        return sorted(out, key=lambda r: -(r["created"] or 0))

    def load_run(self, rid: str) -> dict | None:
        if not rid.replace("-", "").isalnum():
            return None
        f = self.runs_dir / f"{rid}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def delete_run(self, rid: str) -> bool:
        if not rid.replace("-", "").isalnum():
            return False
        f = self.runs_dir / f"{rid}.json"
        if f.exists():
            f.unlink(); return True
        return False

    def status(self) -> dict:
        import os
        prov = [n for n in ("GEMINI", "GROQ") if os.environ.get(f"{n}_API_KEY")]
        have = (self.models / "relevance").exists() and (self.models / "verdict.joblib").exists()
        return {"providers": [p.lower() for p in prov], "trained_models": have, "runs": len(list(self.runs_dir.glob("*.json"))),
                "demo": (self.root / "docs/demo_report.html").exists(), "busy": any(j.state in ("queued", "running") for j in self.jobs.values())}


def _friendly(e: Exception) -> str:
    m = str(e) or e.__class__.__name__
    if "daily quota" in m or "HTTP 429" in m:
        return "The judge's free-tier quota is used up (HTTP 429). Cached answers are kept; try again after the quota resets. " + m[:200]
    if "all providers failed" in m:
        return "The LLM judge could not be reached: " + m[:240]
    return m[:600]


def _clean(body: dict) -> dict:
    mode = body.get("mode", "pr")
    if mode not in ("pr", "local"):
        raise ValueError("mode must be 'pr' or 'local'")
    p = {"mode": mode, "ask": str(body.get("ask", ""))[:20000], "url": str(body.get("url", "")).strip(), "repo": str(body.get("repo", "")).strip(),
         "base": str(body.get("base", "")).strip()[:200], "head": str(body.get("head", "")).strip()[:200],
         "retrieval": "lexical" if body.get("retrieval") == "lexical" else "auto", "escalate": bool(body.get("escalate")),
         "context": bool(body.get("context"))}
    if mode == "pr" and not p["url"].startswith("https://github.com/"):
        raise ValueError("Enter a GitHub pull request URL, e.g. https://github.com/owner/repo/pull/123")
    if mode == "local" and (not p["repo"] or not p["ask"].strip()):
        raise ValueError("Local audits need a repository folder and the ask text.")
    return p


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        server_version = "pr-audit"

        def log_message(self, *a):  # quiet
            pass

        # -- helpers
        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            return (self.headers.get("Host") or "") in (f"127.0.0.1:{app.port}", f"localhost:{app.port}")

        def _authed(self) -> bool:
            c = SimpleCookie(self.headers.get("Cookie") or "")
            return "pa" in c and secrets.compare_digest(c["pa"].value, app.token) and self._host_ok()

        # -- routes
        def do_GET(self):
            path = urlparse(self.path).path
            if not self._host_ok():
                return self._json(403, {"error": "bad host"})
            if path in ("/", "/index.html"):
                html = (WEB / "app.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8",
                                  {"Set-Cookie": f"pa={app.token}; HttpOnly; SameSite=Strict; Path=/",
                                   "Content-Security-Policy": "default-src 'self' 'unsafe-inline'; frame-src 'self'; img-src 'self' data:; connect-src 'self'"})
            if not self._authed():
                return self._json(403, {"error": "open the app from its own page first"})
            if path == "/api/status":
                return self._json(200, app.status())
            if path == "/api/runs":
                return self._json(200, app.list_runs())
            if path == "/demo":
                f = app.root / "docs/demo_report.html"
                return self._send(200, f.read_bytes(), "text/html; charset=utf-8") if f.exists() else self._json(404, {"error": "no demo report"})
            if path.startswith("/api/jobs/"):
                j = app.jobs.get(path.split("/")[3])
                if not j:
                    return self._json(404, {"error": "unknown job"})
                since = int((urlparse(self.path).query.split("since=")[-1] or 0)) if "since=" in urlparse(self.path).query else 0
                return self._json(200, j.view(since))
            if path.startswith("/api/runs/"):
                parts = path.split("/")
                r = app.load_run(parts[3]) if len(parts) > 3 else None
                if not r:
                    return self._json(404, {"error": "unknown run"})
                what = parts[4] if len(parts) > 4 else "data"
                if what == "data":
                    return self._json(200, {k: v for k, v in r.items() if k != "markdown"})
                if what == "report.html":
                    from .html_report import render_from_data
                    return self._send(200, render_from_data(r["data"], r["title"]).encode(), "text/html; charset=utf-8",
                                      {"Content-Disposition": f'inline; filename="pr-audit-{r["id"]}.html"'})
                if what == "report.md":
                    return self._send(200, r.get("markdown", "").encode(), "text/markdown; charset=utf-8",
                                      {"Content-Disposition": f'attachment; filename="pr-audit-{r["id"]}.md"'})
                if what == "report.json":
                    return self._send(200, json.dumps(r["data"], indent=1).encode(), "application/json",
                                      {"Content-Disposition": f'attachment; filename="pr-audit-{r["id"]}.json"'})
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            if not self._authed():
                return self._json(403, {"error": "forbidden"})
            if "application/json" not in (self.headers.get("Content-Type") or ""):
                return self._json(415, {"error": "json only"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._json(413, {"error": "request too large"})
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._json(400, {"error": "bad json"})
            if path == "/api/audit":
                try:
                    params = _clean(body)
                except ValueError as e:
                    return self._json(400, {"error": str(e)})
                job = app.start(params)
                if job is None:
                    return self._json(409, {"error": "Another audit is running. One at a time keeps the free-tier quota safe."})
                return self._json(202, {"job": job.id})
            return self._json(404, {"error": "not found"})

        def do_DELETE(self):
            path = urlparse(self.path).path
            if not self._authed():
                return self._json(403, {"error": "forbidden"})
            if path.startswith("/api/runs/") and app.delete_run(path.split("/")[3]):
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "not found"})
    return H


def serve(root: Path, data_dir: Path, models: Path, port: int = 8765, open_browser: bool = True, runner=None) -> None:
    app = App(root, data_dir, models, port, runner)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{port}/"
    print(f"PR Intent Audit app: {url}   (Ctrl+C to stop; runs are saved in {app.runs_dir})")
    if open_browser:
        import webbrowser; threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
