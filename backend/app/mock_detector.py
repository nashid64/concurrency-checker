"""Tiny rule-based detector. DEMO ONLY: lets you test the whole pipeline (extension -> backend)
without an API key or a trained model. It is NOT a real analyzer."""
import re
from typing import Any, Dict, List

_SYNC = re.compile(r"synchronized\s*\(\s*([\w.]+)\s*\)")
_INC = re.compile(r"^\s*(?:this\.)?(\w+)\s*(?:\+\+|--|\+=|-=)")
_THREADY = re.compile(r"\b(Thread|Runnable|ExecutorService|Executors|CompletableFuture)\b")
_SAFE_DECL = re.compile(r"\b(Atomic\w+|volatile|LongAdder)\b")


def analyze(code: str) -> List[Dict[str, Any]]:
    lines = code.splitlines()
    bugs: List[Dict[str, Any]] = []

    # --- deadlock: nested synchronized blocks taken in opposite order somewhere ---
    stack: List[tuple] = []  # (lock_name, brace_depth_at_open)
    depth = 0
    pairs: Dict[tuple, int] = {}
    for no, line in enumerate(lines, start=1):
        m = _SYNC.search(line)
        if m:
            for outer, _ in stack:
                pairs.setdefault((outer, m.group(1)), no)
            stack.append((m.group(1), depth))
        depth += line.count("{") - line.count("}")
        while stack and depth <= stack[-1][1]:
            stack.pop()
    for (a, b), no in pairs.items():
        if a != b and (b, a) in pairs and no >= pairs[(b, a)]:
            bugs.append({"type": "deadlock", "line": no, "end_line": None, "severity": "error",
                         "message": f"Locks '{a}' and '{b}' are acquired in opposite order in different places, which can deadlock.",
                         "suggestion": "Always acquire the locks in one global order."})

    # --- race: ++ / += on a plain field in a file that uses threads ---
    if _THREADY.search(code):
        plain_fields = set()
        for line in lines:
            fm = re.match(r"\s*(?:private|public|protected)?\s*(?:static\s+)?(?:int|long)\s+(\w+)\s*(?:=|;)", line)
            if fm and not _SAFE_DECL.search(line):
                plain_fields.add(fm.group(1))
        in_sync = 0
        depth = 0
        sync_depths: List[int] = []
        for no, line in enumerate(lines, start=1):
            if _SYNC.search(line) or re.search(r"\bsynchronized\b", line):
                sync_depths.append(depth)
            im = _INC.match(line)
            if im and im.group(1) in plain_fields and not sync_depths:
                bugs.append({"type": "race_condition", "line": no, "end_line": None, "severity": "warning",
                             "message": f"'{im.group(1)}' is updated without synchronization or atomic type; concurrent updates can be lost.",
                             "suggestion": "Use AtomicInteger/AtomicLong or synchronize the update."})
                plain_fields.discard(im.group(1))
            depth += line.count("{") - line.count("}")
            while sync_depths and depth <= sync_depths[-1]:
                sync_depths.pop()
    return bugs
