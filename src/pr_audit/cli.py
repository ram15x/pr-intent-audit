from __future__ import annotations
import json
from pathlib import Path
import typer
from .env import load_env

app = typer.Typer(add_completion=False, help="Audit whether a PR did what was asked.")
ROOT = Path(__file__).resolve().parents[2]


@app.callback()
def main() -> None:
    """PR Intent Audit."""


@app.command()
def run(url: str = typer.Argument(..., help="GitHub PR URL"),
        ask_file: Path = typer.Option(None, "--ask-file", help="Text file with the ask (e.g. the prompt you gave an agent)"),
        out: Path = typer.Option(Path("report.md"), "--out"),
        html: Path = typer.Option(None, "--html", help="Also write a self-contained HTML report (score breakdown + evidence viewer)"),
        models: Path = typer.Option(ROOT / "models", "--models"),
        local: bool = typer.Option(False, "--local", help="Use only our local models (no LLM calls; weak at within-PR judging)"),
        retrieval: str = typer.Option("auto", "--retrieval", help="auto | model | lexical. lexical = word overlap, no model files needed"),
        escalate: bool = typer.Option(False, "--escalate", help="Experimental: when the top-5 hunks do not give a verified 'done', look at the top 12 (max 2 judge calls per requirement)")):
    """Audit one PR against its ask and write a Markdown report."""
    from .audit import load_scorer, run_audit
    from .ingest import fetch_pr
    from .report import render_markdown
    load_env(ROOT / ".env")
    ask = ask_file.read_text(encoding="utf-8") if ask_file else None
    typer.echo("fetching PR ...")
    try:
        bundle = fetch_pr(url, ask_override=ask)
    except ValueError as e:
        typer.echo(f"error: {e}\nexpected something like https://github.com/ztrange/veri/pull/2693", err=True)
        raise typer.Exit(2)
    if not bundle.hunks:
        raise typer.Exit("no auditable hunks in this PR")
    _audit_and_write(bundle, models, local, retrieval, out, html, escalate)

@app.command("local")
def local_cmd(ask_file: Path = typer.Argument(..., help="Text file with the ask (the prompt you gave the agent, a spec or an issue)"),
              repo: Path = typer.Option(Path("."), "--repo", help="Git repository"),
              base: str = typer.Option("HEAD~1", "--base", help="Base ref (what the work started from)"),
              head: str = typer.Option("HEAD", "--head", help="Head ref; use '' for the working tree"),
              out: Path = typer.Option(Path("report.md"), "--out"),
              html: Path = typer.Option(None, "--html"),
              models: Path = typer.Option(ROOT / "models", "--models"),
              local: bool = typer.Option(False, "--local"),
              retrieval: str = typer.Option("auto", "--retrieval")):
    """Audit local commits (no PR needed) against an ask file. Example: pr-audit local prompt.txt --base main~3 --head HEAD"""
    from .local import bundle_from_git
    load_env(ROOT / ".env")
    try:
        bundle = bundle_from_git(repo, ask_file.read_text(encoding="utf-8"), base, head or None)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2)
    if not bundle.hunks:
        raise typer.Exit("no auditable hunks between those refs")
    _audit_and_write(bundle, models, local, retrieval, out, html)


@app.command("serve")
def serve_cmd(port: int = typer.Option(8765, "--port"),
              data_dir: Path = typer.Option(Path(".pr-audit"), "--data-dir", help="Where finished audits are stored"),
              models: Path = typer.Option(ROOT / "models", "--models"),
              no_browser: bool = typer.Option(False, "--no-browser")):
    """Open the local web app (paste a PR URL or local commits, watch the audit, open the evidence report)."""
    from .server import serve
    load_env(ROOT / ".env")
    serve(ROOT, data_dir, models, port, open_browser=not no_browser)


def _audit_and_write(bundle, models: Path, local: bool, retrieval: str, out: Path, html: Path | None, escalate: bool = False) -> None:
    from .audit import run_audit
    from .pipeline import make_pipeline
    from .report import render_markdown
    try:
        pl = make_pipeline(ROOT, models, local, retrieval, escalate, log=typer.echo)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    typer.echo(f"scoring {len(bundle.hunks)} hunks ...")
    audit = run_audit(bundle, pl.scorer, pl.clf, tau=pl.cfg["tau"], band=pl.cfg["band"], judge=pl.judge)
    out.write_text(render_markdown(audit, pl.info), encoding="utf-8")
    if html:
        from .html_report import render_html
        html.write_text(render_html(audit, pl.info), encoding="utf-8")
        typer.echo(f"html: {html}")
    typer.echo(f"rank: {audit.rank} ({audit.band}) -> {out}")


if __name__ == "__main__":
    app()
