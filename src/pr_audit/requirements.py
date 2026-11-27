"""Rule-based ask cleaning + requirement splitting. No model.

Strips issue-template boilerplate (environment, versions, logs), then splits what's left into
atomic requirement candidates: checklist items first, bullets second, sentences last.
"""
from __future__ import annotations
import re
from .schemas import Requirement

# Sections that describe the reporter's setup, not the ask.
SKIP_HEADINGS = re.compile(
    r"^(environment|env|system info|versions?|logs?|stack ?trace|traceback|screenshots?|"
    r"additional context|checklist before|reproduc\w*|steps to reproduce|how to reproduce|"
    r"os|platform|configuration|labels?)\b", re.I)
CHECKBOX = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s+(.*\S)")
BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*\S)")
MODAL = re.compile(r"\b(should|must|need(?:s)? to|needs|add|remove|fix|support|allow|ensure|make|"
                   r"return|raise|handle|replace|rename|implement|update|change)\b", re.I)


# Items that are process/template noise, not requirements on the code.
NOISE = re.compile(
    r"^(?:(?:i|we)(?:'ve| have| had| did| confirm| checked| searched| read| followed| tested| ran| reviewed)\b"
    r"|(?:the )?(?:pull request|pr)\s+(?:has been|is|was)\s+(?:reviewed|approved)"
    r"|related issues?\b|relat(?:es|ed) to\b|(?:closes|fixes|resolves|refs?|see)\s+#?\d+"
    r"|#\d+\b|[A-Z][A-Z0-9]+-\d+\b.{0,25}$"
    r"|\*\*(?:estimated|actual)\s+hours|\*\*(?:pr link|epic|track|sprint|estimate)\b"
    r"|pull (?:the )?latest\b"
    r"|\*\*[^*\n]{1,30}\*\*\s*:\s*v?[\w.+-]{1,20}$"                       # '**Python version**: 3.6.2' (environment key/value)
    r"|\*\*(?:code completion|testing|peer review|documentation|deployment readiness)\*\*\s*:"   # definition-of-done template
    r"|please (?:run|update|install|note|see)\b"                                # instructions to the reader, not code requirements
    r"|(?:the )?(?:pr|pull request|changes?) (?:is|are) (?:tagged|compliant)\b|(?:the )?(?:charm )?style guide was\b|(?:the )?contributing guide was\b"
    r"|bug fix \(|new feature \(|breaking change \(|reviewer has tested|all new and existing tests"
    r"|changes have been manually tested|all todos related to this pr|there are automated tests for newly written"   # PR-template checklist
    r"|all bugs discovered while working|(?:documentation|changelog(?:\.md)?)\b.{0,120}\bhas been updated"
    r"|what problem/issue are you fixing|what does this pr implement)", re.I)
REVIEWED_BY = re.compile(r"\b(?:reviewed|approved) by\b", re.I)
# A plain line that introduces alternatives: bullets under it are options, not obligations.
OPTION_INTRO = re.compile(r"(possible approaches|fix options|options?\b.*:|alternatives?\b.*:|to evaluate|not commit to|and/or\s*$)", re.I)


def _is_noise(item: str) -> bool:
    t = item.strip()
    if not t or (t.endswith(":") and len(t) < 40):
        return True
    return bool(NOISE.match(t) or REVIEWED_BY.search(t))


def clean_ask(text: str) -> str:
    out, skipping = [], False
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^#{1,6}\s*(.+)", line)
        if m:
            skipping = bool(SKIP_HEADINGS.match(re.sub(r"^[^\w]+", "", m.group(1)).strip()))   # '### 🪜 How to reproduce'

            if not skipping:
                out.append(line)
            continue
        if skipping:
            continue
        line = re.sub(r"<!--.*?-->", "", line)
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def split_requirements(text: str, max_reqs: int = 12) -> list[Requirement]:
    return split_requirements_ex(text, max_reqs)[0]


def split_requirements_ex(text: str, max_reqs: int = 12) -> tuple[list[Requirement], int]:
    """(requirements kept, number found beyond max_reqs and therefore NOT audited)."""
    cleaned = clean_ask(text)
    items: list[tuple[str, bool]] = []
    optional = False
    for line in cleaned.splitlines():
        m = CHECKBOX.match(line) or BULLET.match(line)
        if m:
            items.append((m.group(m.lastindex), optional))
        elif re.match(r"^#{1,6}\s", line) or not line.strip():
            optional = optional and not re.match(r"^#{1,6}\s", line) and bool(not line.strip())
            if re.match(r"^#{1,6}\s", line):
                optional = bool(OPTION_INTRO.search(line))
        else:
            optional = bool(OPTION_INTRO.search(line))
    had_list = len(items) >= 2          # judge list structure before dropping noise items
    items = [(t, o) for t, o in items if not _is_noise(t)]
    if not had_list:  # no list structure: fall back to modal-verb sentences
        flat = re.sub(r"\s+", " ", re.sub(r"^#+\s*", "", cleaned, flags=re.M))
        sents = re.split(r"(?<=[.!?])\s+", flat)
        items = [(s_, False) for s_ in sents if MODAL.search(s_) and 15 <= len(s_) <= 300 and not _is_noise(s_)]
    reqs = []
    for i, (s_, opt) in enumerate(items[:max_reqs], 1):
        s_ = re.sub(r"\s+", " ", s_).strip()
        reqs.append(Requirement(id=i, text=s_, source_sentence=s_, unclear=not MODAL.search(s_), optional=opt))
    return reqs, max(0, len(items) - max_reqs)
