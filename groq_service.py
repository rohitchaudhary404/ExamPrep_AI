#!/usr/bin/env python3
"""Groq LLM integration for ExamPrep AI.

Takes notes + context (school board/class OR university/course/semester) and
returns structured study material: key points, important questions, and
high-yield topics. Also analyses web search results to surface the most
repeated previous-year questions across the internet.
"""

import json
import os
import re
import threading
import time

import groq as groq_mod

from pyq_search import search_pyqs
import web_search

DEFAULT_MODEL = "openai/gpt-oss-120b"
ALLOWED_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "allam-2-7b",
]

# Cap the number of simultaneous LLM calls so a burst of users can't hammer the
# provider or exhaust memory.
_LLM_SEM = threading.BoundedSemaphore(8)

SYSTEM_PROMPT = (
    "You are ExamPrep AI, an expert study assistant for school board exams "
    "(CBSE, ICSE, state boards) and university/college exams. You are precise, "
    "exam-focused, and syllabus-aware.\n\n"
    "You receive a student's notes and their context (board/class or "
    "university/course/semester). Analyse the notes deeply and produce structured, "
    "high-yield exam material.\n\n"
    "Respond ONLY with a single valid JSON object (no markdown fences, no extra text) "
    "with exactly this shape:\n"
    "{\n"
    '  "summary": "<2-3 sentence plain-language summary of what the notes cover>",\n'
    '  "key_points": ["<concise key point>", ...],\n'
    '  "important_topics": [\n'
    "    {\n"
    '      "topic": "<short topic name>",\n'
    '      "weightage": "<High|Medium|Low>",\n'
    '      "exam_probability": "<Very Likely|Likely|Possible>",\n'
    '      "reason": "<one sentence on why this topic is frequently asked>",\n'
    '      "keywords": ["<kw1>", "<kw2>", ...]\n'
    "    }\n"
    "  ],\n"
    '  "important_questions": [\n'
    "    {\n"
    '      "question": "<a realistic exam-style question based on the notes>",\n'
    '      "marks": <integer 1..15>,\n'
    '      "type": "<Very Short|Short|Long|Numerical|Diagram|MCQ>",\n'
    '      "topic": "<topic this question maps to>"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- key_points: 5-10 concise bullets covering core facts/concepts/formulas/definitions.\n"
    "- important_topics: 4-8 topics ranked by likelihood of appearing in exams; keywords are "
    "3-8 lowercase keywords/synonyms useful for locating previous-year questions.\n"
    "- important_questions: 5-10 realistic exam-style questions (mix of types and marks).\n"
    "- Base everything strictly on the student's notes and the standard syllabus; do not invent "
    "unrelated content.\n"
    "- Keep the JSON valid; escape any double quotes inside string values."
)

WEB_PATTERN_PROMPT = (
    "You are an exam-trend analyst. Below are web search results about previous-year exam "
    "questions for a specific course/subject. Identify which questions and topics are MOST "
    "REPEATED across these sources (i.e. appear in multiple results / multiple years).\n\n"
    "Respond ONLY with a single valid JSON object with exactly this shape:\n"
    "{\n"
    '  "trend": "<1-2 sentence summary of the most repeated patterns>",\n'
    '  "repeated_topics": [\n'
    '    {"topic": "<topic name>", "frequency": "<Very Frequent|Frequent|Moderate>", "mentions": <int>}\n'
    "  ],\n"
    '  "repeated_questions": [\n'
    '    {"question": "<the repeated question>", "frequency": "<Very Frequent|Frequent>", "type": "<Theory|Numerical|Diagram|MCQ>", "source_urls": ["<url>", ...]}\n'
    "  ]\n"
    "}\n\n"
    "- repeated_topics: 3-6 topics that recur most, ranked by how often they appear.\n"
    "- repeated_questions: 4-8 concrete questions that are repeated across sources, with the "
    "URLs where they were seen. Only include questions that appear in at least one source.\n"
    "- source_urls MUST be URLs that literally appear in the SEARCH RESULTS above — copy them "
    "exactly, do not invent, shorten, or modify them.\n"
    "- Keep the JSON valid."
)


def _parse_json(text):
    if not text:
        raise ValueError("empty model response")
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _build_user_prompt(payload, notes):
    level = (payload.get("level") or "school").lower()
    if level == "university":
        uni = (payload.get("university") or "").strip() or "(not specified)"
        course = (payload.get("course") or "").strip() or "(not specified)"
        sem = str(payload.get("semester") or "").strip()
        subject = (payload.get("subject") or "").strip() or "(not specified)"
        return (
            f"Level: University\nUniversity/College: {uni}\nCourse/Program: {course}\n"
            f"Semester/Year: {sem}\nSubject: {subject}\n\n"
            f"STUDENT NOTES:\n{notes}\n\n"
            "Analyse the notes above and return the JSON study pack "
            "(summary, key_points, important_topics, important_questions)."
        )
    board = (payload.get("board") or "CBSE").strip()
    cls = str(payload.get("class_level") or "").strip() or "(not specified)"
    subject = (payload.get("subject") or "").strip() or "(not specified)"
    return (
        f"Board: {board}\nClass: {cls}\nSubject: {subject}\n\n"
        f"STUDENT NOTES:\n{notes}\n\n"
        "Analyse the notes above and return the JSON study pack "
        "(summary, key_points, important_topics, important_questions)."
    )


def _call_groq(api_key, model, messages, max_tokens=3000, temperature=0.3, json_mode=True):
    with _LLM_SEM:
        client = groq_mod.Groq(api_key=api_key, timeout=180.0)
        last_exc = None
        for attempt in range(3):
            try:
                kwargs = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
                content = (resp.choices[0].message.content or "").strip()
                if not content:
                    raise ValueError("Groq returned an empty response")
                return content
            except (groq_mod.AuthenticationError, groq_mod.BadRequestError):
                raise  # invalid key / bad request — retrying won't help
            except Exception as exc:  # network / rate-limit / server / timeout
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        raise last_exc


def _normalize(data):
    key_points = data.get("key_points") or []
    if isinstance(key_points, str):
        key_points = [key_points]
    key_points = [str(x).strip() for x in key_points if str(x).strip()]

    topics = data.get("important_topics") or []
    if isinstance(topics, dict):
        topics = list(topics.values())
    clean_topics = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        name = str(t.get("topic") or "").strip()
        if not name:
            continue
        keywords = t.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [keywords]
        clean_topics.append({
            "topic": name,
            "weightage": str(t.get("weightage") or "Medium").strip(),
            "exam_probability": str(t.get("exam_probability") or "Possible").strip(),
            "reason": str(t.get("reason") or "").strip(),
            "keywords": [str(k).strip() for k in keywords if str(k).strip()],
        })

    questions = data.get("important_questions") or []
    if isinstance(questions, dict):
        questions = list(questions.values())
    clean_questions = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()
        if not text:
            continue
        try:
            marks = int(q.get("marks") or 0)
        except (TypeError, ValueError):
            marks = 0
        clean_questions.append({
            "question": text,
            "marks": marks,
            "type": str(q.get("type") or "Short").strip(),
            "topic": str(q.get("topic") or "").strip(),
        })

    return {
        "summary": str(data.get("summary") or "").strip(),
        "key_points": key_points,
        "important_topics": clean_topics,
        "important_questions": clean_questions,
    }


def _normalize_web(data):
    topics = []
    for t in (data.get("repeated_topics") or [])[:6]:
        if not isinstance(t, dict):
            continue
        name = str(t.get("topic") or "").strip()
        if not name:
            continue
        try:
            mentions = int(t.get("mentions") or 0)
        except (TypeError, ValueError):
            mentions = 0
        topics.append({
            "topic": name,
            "frequency": str(t.get("frequency") or "Moderate").strip(),
            "mentions": mentions,
        })

    questions = []
    for q in (data.get("repeated_questions") or [])[:8]:
        if not isinstance(q, dict):
            continue
        text = str(q.get("question") or "").strip()
        if not text:
            continue
        src = q.get("source_urls") or []
        if isinstance(src, str):
            src = [src]
        questions.append({
            "question": text,
            "frequency": str(q.get("frequency") or "Frequent").strip(),
            "type": str(q.get("type") or "Theory").strip(),
            "source_urls": [str(u).strip() for u in src if str(u).strip()],
        })

    return {
        "trend": str(data.get("trend") or "").strip(),
        "repeated_topics": topics,
        "repeated_questions": questions,
    }


def analyze_web_patterns(api_key, model, blob, context):
    messages = [
        {"role": "system", "content": WEB_PATTERN_PROMPT},
        {"role": "user", "content": f"CONTEXT: {context}\n\nSEARCH RESULTS:\n{blob}"},
    ]
    raw = _call_groq(api_key, model, messages, max_tokens=1800, temperature=0.2)
    return _normalize_web(_parse_json(raw))


def _local_pyqs(payload, topics):
    level = (payload.get("level") or "school").lower()
    if level == "university":
        # Local DB is school-focused; still surface same-subject foundational PYQs.
        return search_pyqs(
            topics, board=None, class_level=None,
            subject=(payload.get("subject") or "").strip() or None, limit=8,
        )
    return search_pyqs(
        topics,
        board=(payload.get("board") or "").strip() or None,
        class_level=str(payload.get("class_level") or "").strip() or None,
        subject=(payload.get("subject") or "").strip() or None,
        limit=10,
    )


def analyze_notes(payload):
    """Main entry point called by the HTTP handler. Returns a dict."""
    notes = (payload.get("notes") or "").strip()
    if not notes:
        return {"error": "Please paste some notes to analyse."}
    if len(notes) < 20:
        return {"error": "Notes look too short — please paste at least a few lines."}

    api_key = (payload.get("api_key") or "").strip() or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return {"error": "No API key available. Add your LLM API key in Settings or set GROQ_API_KEY in .env"}

    model = (payload.get("model") or "").strip() or os.environ.get("GROQ_MODEL", DEFAULT_MODEL).strip()
    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(payload, notes)},
    ]

    try:
        raw = _call_groq(api_key, model, messages)
        data = _normalize(_parse_json(raw))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"AI analysis failed: {exc}"}

    result = {
        "summary": data["summary"],
        "key_points": data["key_points"],
        "important_topics": data["important_topics"],
        "important_questions": data["important_questions"],
        "pyqs": _local_pyqs(payload, data["important_topics"]),
        "model": model,
    }

    # ---- optional internet PYQ search + repeated-pattern analysis ----------
    web_enabled = payload.get("web_search")
    if web_enabled is None:
        web_enabled = True
    web = {"enabled": bool(web_enabled), "trend": "", "repeated_topics": [],
           "repeated_questions": [], "sources": [], "error": None}
    if web_enabled and data["important_topics"]:
        provider = (payload.get("search_provider") or "duckduckgo").strip()
        search_key = (payload.get("search_api_key") or "").strip() or os.environ.get("SEARCH_API_KEY", "").strip()
        try:
            sources, context = web_search.search_pyqs_web(
                payload, data["important_topics"], provider, search_key)
            web["sources"] = sources
            if sources:
                blob = web_search.results_to_blob(sources)
                web.update(analyze_web_patterns(api_key, model, blob, context))
        except Exception as exc:  # noqa: BLE001 — web is best-effort
            web["error"] = f"Web search skipped: {exc}"
    result["web"] = web

    return result
