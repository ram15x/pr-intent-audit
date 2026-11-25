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
        models: Path = typer.Option(ROOT / "models", "--models"),
        local: bool = typer.Option(False, "--local", help="Use only our local models (no LLM calls; weak at within-PR judging)")):
    """Audit one PR against its ask and write a Markdown report."""
    import joblib
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
    cfg = json.loads((models / "verdict.json").read_text(encoding="utf-8"))
    clf = joblib.load(models / "verdict.joblib")
    typer.echo(f"scoring {len(bundle.hunks)} hunks ...")
    judge, mode = None, "local models only"
    if not local:
        from .llm import LLM
        from .judge import judge_requirement
        llm = LLM(ROOT / ".cache/llm")
        if llm.providers:
            judge = lambda i, t, top: judge_requirement(llm, i, t, top, verify=True)
            mode = f"hybrid (judge providers: {', '.join(llm.providers)}; PR text is sent to them)"
        else:
            typer.echo("no GEMINI_API_KEY / GROQ_API_KEY found: falling back to local models only (weak within-PR)")
    audit = run_audit(bundle, load_scorer(models / "relevance"), clf, tau=cfg["tau"], band=cfg["band"], judge=judge)
    out.write_text(render_markdown(audit, f"mode: {mode}; relevance model {models / 'relevance'}"), encoding="utf-8")
    typer.echo(f"rank: {audit.rank} ({audit.band}) -> {out}")


if __name__ == "__main__":
    app()
