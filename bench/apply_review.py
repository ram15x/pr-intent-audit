"""Apply the labels you filled in bench/gold/REVIEW_LOCAL.md back into the gold JSON files.
For every entry where `your_label:` is not `____`, the requirement's status becomes your label, `labeled_by` becomes
"owner" and `owner_reviewed` true; the previous Claude label is kept as `claude_label`. For CREEP lines, answer
`creep` or `not creep`; "not creep" removes the hunk from `creep_hunks`. Entries are matched by position, and each
entry's printed status must equal the JSON's current status, otherwise nothing is written (the sheet is out of date:
regenerate it with make_review_sheet.py, which would lose unsaved answers, so apply first).
Usage: python bench/apply_review.py [--dry]"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FILES = ["gold_draft.json", "gold_extra_draft.json", "gold_large_draft.json"]      # same order as make_review_sheet.py
VALID = {"done", "partial", "missing", "unclear", "exclude"}


def parse(sheet_text):
    """-> (requirements {n: (printed_status, answer|None)}, creep [answer|None, ...] in order)"""
    reqs, creep, cur = {}, [], None
    for line in sheet_text.splitlines():
        m = re.match(r"^(\d+)\. \*\*([A-Z]+)\*\*", line)
        if m:
            cur = ("req", int(m.group(1)), m.group(2).lower()); reqs[cur[1]] = [cur[2], None]; continue
        if line.startswith("- CREEP label:"):
            cur = ("creep", len(creep)); creep.append(None); continue
        a = re.match(r"^\s+your_label[^:]*:\s*(.*?)(?:\s+why:.*)?$", line)
        if a and cur:
            val = a.group(1).strip().lower().strip("_ ").strip()
            if val:
                if cur[0] == "req": reqs[cur[1]][1] = val
                else: creep[cur[1]] = val
    return reqs, creep


def apply(gold_dir, sheet_text, dry=False):
    reqs, creep = parse(sheet_text)
    n = c = changed = 0; problems, report = [], []
    data = {f: json.loads((gold_dir / f).read_text(encoding="utf-8")) for f in FILES}
    for f in FILES:
        for e in data[f]:
            for r in e["requirements"]:
                n += 1
                if n not in reqs: problems.append(f"sheet has no entry {n}"); continue
                printed, ans = reqs[n]
                if printed != r["status"]: problems.append(f"entry {n}: sheet says {printed.upper()}, JSON says {r['status'].upper()}")
                if ans is None: continue
                if ans not in VALID: problems.append(f"entry {n}: '{ans}' is not one of {sorted(VALID)}"); continue
                r["owner_reviewed"] = True
                if ans != r["status"]:
                    r["claude_label"] = r["status"]; r["status"] = ans; r["labeled_by"] = "owner"; changed += 1
                    report.append(f"{n}. {e['pr'].split('github.com/')[1]} R{r['id']}: {r['claude_label']} -> {ans}")
            keep = []
            for ch in e.get("creep_hunks") or []:
                ans = creep[c] if c < len(creep) else None; c += 1
                if ans in ("not creep", "not_creep", "no"):
                    report.append(f"creep removed: {ch['hunk'] if isinstance(ch, dict) else ch}"); changed += 1
                else:
                    keep.append(ch)
            if e.get("creep_hunks") is not None: e["creep_hunks"] = keep
    if c != len(creep): problems.append(f"sheet has {len(creep)} creep entries, JSON has {c}")
    if problems:
        return problems, report, False
    if not dry:
        for f in FILES: (gold_dir / f).write_text(json.dumps(data[f], indent=1, ensure_ascii=False), encoding="utf-8")
    return [], report, True


if __name__ == "__main__":
    gd = ROOT / "bench/gold"; sheet = gd / "REVIEW_LOCAL.md"
    if not sheet.exists(): sys.exit("no REVIEW_LOCAL.md: run bench/make_review_sheet.py first")
    problems, report, ok = apply(gd, sheet.read_text(encoding="utf-8"), "--dry" in sys.argv)
    print("\n".join(problems[:20]) if problems else "\n".join(report) or "no answers filled in yet")
    if ok: print(f"{len(report)} change(s) {'(dry run, nothing written)' if '--dry' in sys.argv else 'written'}")
    else: sys.exit("NOT applied: fix the problems above")
