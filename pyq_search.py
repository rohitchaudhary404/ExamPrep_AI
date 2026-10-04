#!/usr/bin/env python3
"""Local CBSE PYQ (previous-year question) database lookup.

The database is a plain JSON file (pyq_db.json) that ships with a starter set
of well-known CBSE board questions. It is intentionally easy to extend: add
entries with `topics` keywords and the matcher will find them.

There is no official public CBSE "PYQ API", so this module provides a local,
searchable database keyed by topic tags.
"""

import glob
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_cache = None


def _db_files():
    """Every pyq_db*.json file in the project dir — lets you drop in extra files."""
    files = glob.glob(os.path.join(BASE_DIR, "pyq_db*.json"))
    return sorted(files)


def load_pyq_db():
    global _cache
    if _cache is not None:
        return _cache
    _cache = []
    for path in _db_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            _cache.extend(data)
    return _cache


def get_db_stats():
    db = load_pyq_db()
    return {"total_questions": len(db)}


_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "in", "on", "for", "with", "is", "are",
    "to", "what", "why", "how", "its", "their", "explain", "define", "state",
    "write", "give", "name", "draw", "between", "difference", "differentiate",
    "following", "list", "two", "one", "example", "examples", "and", "the",
}


def _norm(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text


def _tokens(text):
    words = _norm(text).split()
    return [w for w in words if w and w not in _STOPWORDS]


def _query_tokens(topics):
    """Build a set of matching tokens from the extracted topic objects."""
    tokens = set()
    for t in topics:
        if not isinstance(t, dict):
            continue
        for field in ("topic",):
            for tok in _tokens(str(t.get(field) or "")):
                if len(tok) > 2:  # ignore single/two-letter noise
                    tokens.add(tok)
        for kw in t.get("keywords") or []:
            for tok in _tokens(str(kw)):
                if len(tok) > 2:
                    tokens.add(tok)
    return tokens


def _class_matches(q_class, class_level):
    if not class_level:
        return True
    try:
        return int(q_class) == int(class_level)
    except (TypeError, ValueError):
        return True


def _board_matches(q_board, board):
    if not board or not q_board:
        return True
    qb = q_board.lower()
    b = board.lower()
    return qb == b or b in qb or qb in b


_SUBJECT_ALIASES = {
    "maths": "mathematics",
    "math": "mathematics",
    "sst": "social science",
    "social studies": "social science",
    "social": "social science",
    "sci": "science",
    "bio": "biology",
    "chem": "chemistry",
    "phy": "physics",
    "cs": "computer science",
    "computer": "computer science",
    "business": "business studies",
    "english literature": "english",
}


def _canon_subject(s):
    s = (s or "").strip().lower()
    return _SUBJECT_ALIASES.get(s, s)


def _subject_matches(q_subject, subject):
    if not subject or not q_subject:
        return True
    # Exact (canonical) match only — avoids "Science" matching "Social Science".
    return _canon_subject(q_subject) == _canon_subject(subject)


def search_pyqs(topics, board=None, class_level=None, subject=None, limit=10):
    """Score and return the most relevant PYQs for the given extracted topics."""
    db = load_pyq_db()
    if not db or not topics:
        return []

    query = _query_tokens(topics)
    if not query:
        return []

    scored = []
    for q in db:
        if not _class_matches(q.get("class"), class_level):
            continue
        if not _board_matches(q.get("board"), board):
            continue
        if not _subject_matches(q.get("subject"), subject):
            continue

        q_tokens = _tokens(str(q.get("question") or ""))
        tag_tokens = set()
        for tag in q.get("topics") or []:
            tag_tokens.update(_tokens(str(tag)))

        score = 0
        matched = set()
        for tok in query:
            if tok in tag_tokens:
                score += 4
                matched.add(tok)
            elif tok in q_tokens:
                score += 1
                matched.add(tok)

        # Require a meaningful match: at least two distinct topic-keyword hits
        # (with at least one strong tag-level match), so single generic words
        # like "series" or "power" cannot drag in unrelated questions.
        if score < 5 or len(matched) < 2:
            continue
        scored.append((score, q, sorted(matched)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {**item[1], "_match_score": item[0], "_matched": item[2]}
        for item in scored[:limit]
    ]
