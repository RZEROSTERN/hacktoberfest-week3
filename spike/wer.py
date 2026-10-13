"""Pairwise word error rate between transcripts (no human reference yet: this measures
agreement between engines/models, not accuracy). Usage: uv run python wer.py a.json b.json ..."""

import itertools
import json
import re
import sys


def words(path: str) -> list[str]:
    with open(path) as f:
        text = " ".join(s["text"] for s in json.load(f))
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


if __name__ == "__main__":
    paths = sys.argv[1:]
    texts = {p: words(p) for p in paths}
    for p in paths:
        print(f"{p}: {len(texts[p])} words")
    for a, b in itertools.combinations(paths, 2):
        print(f"WER {a.split('/')[-1]} vs {b.split('/')[-1]}: {edit_distance(texts[a], texts[b]) / len(texts[a]):.1%}")
