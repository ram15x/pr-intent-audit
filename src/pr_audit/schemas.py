from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    done = "done"
    partial = "partial"
    missing = "missing"
    unclear = "unclear"


class Hunk(BaseModel):
    id: str                      # "path:start-end" (new-file line range)
    file: str
    start: int
    end: int
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    text: str = ""               # raw hunk text incl. context


class PRBundle(BaseModel):
    source: str                  # URL or local label
    title: str = ""
    body: str = ""
    ask: str = ""                # the ask: agent prompt, issue text, or spec
    ask_source: str = "pr_body"  # agent_prompt | issue | pr_body | spec
    hunks: list[Hunk] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # e.g. "diff cut: 3 files dropped"


class Requirement(BaseModel):
    id: int
    text: str
    source_sentence: str = ""
    unclear: bool = False
    optional: bool = False       # listed as an option/approach to evaluate: not doing it is not a gap


class Judgment(BaseModel):
    req_id: int
    verdict: Verdict
    hunk_ids: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    reason: str = ""
    downgraded_because: list[str] = Field(default_factory=list)
