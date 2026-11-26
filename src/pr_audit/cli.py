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
        retrieval: str = typer.Option("auto", "--retrieval", help="auto | model | lexical. lexical = word overlap, no model files needed")):
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
    _audit_and_write(bundle, models, local, retrieval, out, html)

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


def _audit_and_write(bundle, models: Path, local: bool, retrieval: str, out: Path, html: Path | None) -> None:
    from .audit import load_scorer, run_audit
    from .report import render_markdown
    have_models = (models / "relevance").exists() and (models / "verdict.joblib").exists()
    use_lexical = retrieval == "lexical" or (retrieval == "auto" and not have_models)
    if retrieval == "model" and not have_models:
        raise typer.BadParameter(f"no trained models in {models}; see README 'Train the models yourself' or use --retrieval lexical")
    if use_lexical and local:
        raise typer.BadParameter("--local needs the trained models; train them or drop --local")
    if use_lexical:
        from .lexical import lexical_scorer
        scorer, clf, cfg = lexical_scorer(), None, {"tau": 0.5, "band": 0.10}
        typer.echo("retrieval: lexical word overlap (no trained models found or --retrieval lexical)")
    else:
        cfg = json.loads((models / "verdict.json").read_text(encoding="utf-8"))
        import joblib
        clf = joblib.load(models / "verdict.joblib")
        scorer = load_scorer(models / "relevance")
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
            if use_lexical:
                raise typer.BadParameter("lexical retrieval needs an LLM judge: set GEMINI_API_KEY and/or GROQ_API_KEY")
            typer.echo("no GEMINI_API_KEY / GROQ_API_KEY found: falling back to local models only (weak within-PR)")
    audit = run_audit(bundle, scorer, clf, tau=cfg["tau"], band=cfg["band"], judge=judge)
    info = f"mode: {mode}; retrieval: {'lexical word overlap' if use_lexical else 'trained CodeBERT relevance model'}"
    out.write_text(render_markdown(audit, info), encoding="utf-8")
    if html:
        from .html_report import render_html
        html.write_text(render_html(audit, info), encoding="utf-8")
        typer.echo(f"html: {html}")
    typer.echo(f"rank: {audit.rank} ({audit.band}) -> {out}")



if __name__ == "__main__":
    app()
