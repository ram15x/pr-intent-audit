"""Minimal provider wrapper: Gemini + Groq (OpenAI-compatible), disk cache, retry, fallback. Never logs keys."""
from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
import httpx

GEMINI_PREF = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
GROQ_MODEL = "openai/gpt-oss-120b"


class LLM:
    def __init__(self, cache_dir: str | Path = ".cache/llm", providers=("gemini", "groq")):
        self.dir = Path(cache_dir); self.dir.mkdir(parents=True, exist_ok=True)
        self.providers = [p for p in providers if os.environ.get(f"{p.upper()}_API_KEY")]
        self.gemini_model: str | None = None
        self.cool: dict[str, float] = {}     # provider -> skip until (monotonic seconds)
        self.calls = {"cache": 0, "net": 0, "fail": 0}
        self.by_provider: dict[str, int] = {}
        self.http = httpx.Client(timeout=90)

    # -- providers -------------------------------------------------------
    def _pick_gemini(self) -> str:
        if not self.gemini_model:
            r = self.http.get("https://generativelanguage.googleapis.com/v1beta/models",
                              headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, params={"pageSize": 200})
            names = {m["name"].split("/")[-1] for m in r.json().get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])}
            self.gemini_model = next((m for m in GEMINI_PREF if m in names), None) or \
                next((n for n in sorted(names) if "flash" in n), None)
            if not self.gemini_model:
                raise RuntimeError("no usable Gemini model found")
        return self.gemini_model

    def _call(self, provider: str, prompt: str) -> str:
        if provider == "gemini":
            m = self._pick_gemini()
            r = self.http.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                               headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                               json={"contents": [{"parts": [{"text": prompt}]}],
                                     "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        r = self.http.post("https://api.groq.com/openai/v1/chat/completions",
                           headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                           json={"model": GROQ_MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                                 "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    # -- public ----------------------------------------------------------
    def __call__(self, prompt: str) -> str:
        key = hashlib.sha256(prompt.encode()).hexdigest()[:24]
        f = self.dir / f"{key}.json"
        if f.exists():
            self.calls["cache"] += 1
            return json.loads(f.read_text(encoding="utf-8"))["text"]
        last, errs = None, []
        for p in self.providers:
            if self.cool.get(p, 0) > time.monotonic() and len(self.providers) > 1:
                errs.append(f"{p} skipped (cooling down after 429)"); continue
            for attempt in range(6):
                try:
                    text = self._call(p, prompt)
                    f.write_text(json.dumps({"provider": p, "model": self.gemini_model if p == "gemini" else GROQ_MODEL,
                                             "text": text}), encoding="utf-8")
                    self.calls["net"] += 1
                    self.by_provider[p] = self.by_provider.get(p, 0) + 1
                    return text
                except httpx.HTTPStatusError as e:
                    last = f"{p} HTTP {e.response.status_code}"
                    errs.append(last)
                    if e.response.status_code == 429 and p == "gemini" and len(self.providers) > 1:
                        self.cool[p] = time.monotonic() + 900      # quota exhausted: stop hammering it, use the fallback
                        break
                    if e.response.status_code in (429, 503):
                        try:
                            wait = float(e.response.headers.get("retry-after", ""))
                        except ValueError:
                            wait = 12 * (attempt + 1)
                        time.sleep(min(max(wait, 5), 70))      # honour the provider's own hint, capped at ~1 minute
                    else:
                        time.sleep(1)
                    if e.response.status_code not in (429, 503):
                        break
                except Exception as e:
                    last = f"{p} {type(e).__name__}"; errs.append(last); break
        self.calls["fail"] += 1
        raise RuntimeError(f"all providers failed (last: {last}; seen: {', '.join(dict.fromkeys(errs))})")
