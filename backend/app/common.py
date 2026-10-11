import re
from typing import List

BUG_TYPES = ("race_condition", "deadlock", "concurrency_issue")
PRIORITY = {"deadlock": 3, "race_condition": 2, "concurrency_issue": 1}

_KEYWORD_LINE = re.compile(r"\b(synchronized|Lock|lock\(|wait\(|notify|volatile|Thread|Executor|Atomic)\b")


def normalize_type(value: str) -> str:
    v = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if "deadlock" in v:
        return "deadlock"
    if "race" in v:
        return "race_condition"
    return "concurrency_issue"


def verdict_from_types(types: List[str]) -> str:
    if not types:
        return "safe"
    return max(types, key=lambda t: PRIORITY.get(t, 0))


def guess_line(code: str) -> int:
    """Used when a detector (the local classifier) cannot give a line number:
    point to the first concurrency-related line, else line 1."""
    for i, line in enumerate(code.splitlines(), start=1):
        if _KEYWORD_LINE.search(line):
            return i
    return 1


def number_lines(code: str) -> str:
    return "\n".join(f"{i:>4} | {line}" for i, line in enumerate(code.splitlines(), start=1))
