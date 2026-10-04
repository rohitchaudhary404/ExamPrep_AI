#!/usr/bin/env python3
"""Internet search for previous-year questions (PYQs) + source aggregation.

Search backends (configurable in Settings):
  * "duckduckgo" — free, no key needed (default)
  * "tavily"      — needs an API key (https://tavily.com)
  * "serpapi"     — needs an API key (https://serpapi.com)
"""

MAX_SNIPPET = 600


def _ddg_search(query, max_results=5):
    from ddgs import DDGS

    with DDGS() as ddgs:
        raw = list(ddgs.text(query, max_results=max_results))
    out = []
    for r in raw:
        url = (r.get("href") or r.get("url") or "").strip()
        if not url:
            continue
        out.append({
            "title": (r.get("title") or "").strip(),
            "url": url,
            "snippet": (r.get("body") or r.get("snippet") or "").strip()[:MAX_SNIPPET],
        })
    return out


def _tavily_search(query, api_key, max_results=5):
    import requests

    r = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": max_results, "include_answer": False},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return [
        {
            "title": res.get("title", ""),
            "url": res.get("url", ""),
            "snippet": (res.get("content") or "")[:MAX_SNIPPET],
        }
        for res in data.get("results", [])
        if res.get("url")
    ]


def _serpapi_search(query, api_key, max_results=5):
    import requests

    r = requests.get(
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": api_key, "num": max_results},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    return [
        {
            "title": res.get("title", ""),
            "url": res.get("link", ""),
            "snippet": (res.get("snippet") or "")[:MAX_SNIPPET],
        }
        for res in data.get("organic_results", [])
        if res.get("link")
    ]


def search_web(query, provider="duckduckgo", api_key="", max_results=5):
    provider = (provider or "duckduckgo").lower()
    if provider == "tavily" and api_key:
        return _tavily_search(query, api_key, max_results)
    if provider in ("serpapi", "google") and api_key:
        return _serpapi_search(query, api_key, max_results)
    return _ddg_search(query, max_results)


def _context_of(payload):
    level = (payload.get("level") or "school").lower()
    subject = (payload.get("subject") or "").strip()
    if level == "university":
        parts = []
        for key in ("university", "course"):
            v = (payload.get(key) or "").strip()
            if v:
                parts.append(v)
        sem = (payload.get("semester") or "").strip()
        if sem:
            parts.append(f"Semester {sem}")
        if subject:
            parts.append(subject)
        context = " ".join(parts)
        return context or "university"
    board = (payload.get("board") or "CBSE").strip()
    cls = str(payload.get("class_level") or "").strip()
    ctx = f"{board} Class {cls} {subject}".strip() if cls else f"{board} {subject}".strip()
    return ctx


def build_queries(payload, topics):
    """Return (queries, context) for PYQ web search."""
    context = _context_of(payload)
    queries = []
    for t in (topics or [])[:3]:
        name = (t.get("topic") if isinstance(t, dict) else str(t)).strip()
        if name:
            queries.append(f"{context} {name} previous year questions")
    if not queries:
        queries.append(f"{context} previous year question papers")
    return queries, context


def search_pyqs_web(payload, topics, provider, api_key):
    """Search the web for PYQs across the top topics and aggregate unique results."""
    queries, context = build_queries(payload, topics)
    results, seen = [], set()
    for q in queries:
        try:
            for r in search_web(q, provider, api_key, max_results=5):
                url = (r.get("url") or "").strip()
                if url and url not in seen:
                    seen.add(url)
                    results.append(r)
        except Exception:
            continue  # a single failed query shouldn't kill the whole feature
    return results, context


def results_to_blob(results, limit=6000):
    """Flatten search results into a compact text blob for the LLM pattern analysis."""
    lines = []
    for r in results:
        title = r.get("title") or ""
        snippet = r.get("snippet") or ""
        url = r.get("url") or ""
        lines.append(f"TITLE: {title}\nSNIPPET: {snippet}\nURL: {url}\n")
    blob = "\n".join(lines)
    if len(blob) > limit:
        blob = blob[:limit] + "\n…(truncated)"
    return blob
