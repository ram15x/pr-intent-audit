"""One tiny call to each configured judge provider, to see which ones currently work. Prints names and status only, never keys."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.env import load_env
from pr_audit.llm import LLM
load_env(ROOT / ".env")
for p in ("gemini", "groq"):
    l = LLM(ROOT / ".cache/llm_check", providers=(p,))
    if not l.providers:
        print(f"{p}: no key in .env"); continue
    try:
        out = l('Reply with this JSON only: {"ok": true}' + f" ({p} check)")
        print(f"{p}: OK -> {out.strip()[:40]}")
    except Exception as e:
        print(f"{p}: FAILED -> {e}")
