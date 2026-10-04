# 🎓 ExamPrep AI — AI Study Assistant for Schools & Universities

Turn raw notes into a complete, exam-ready study pack for **school boards
(CBSE / ICSE / State)** and **universities / colleges**.

## What it does

Paste your notes (or upload a `.txt` / `.md` / `.docx` / `.pdf` file), choose
**School** or **University**, and the app will:

1. **Analyse** your notes with an LLM (Groq under the hood).
2. Generate **key points** (concise revision bullets).
3. Generate the **most important questions** from those notes (with marks & type).
4. Extract the **most important topics** with the **highest chance of appearing in the exam** (weightage + probability + reason).
5. **Match local PYQs** from the built-in question bank (school boards).
6. **Search the web** for PYQs on those topics and **analyse which questions are most repeated** across the internet — showing frequency + source links.
7. **Export** the whole study pack to **Markdown**, **Word (.docx)**, or **PDF**.

## Requirements

- Python 3.9+ (tested on 3.12 / 3.14)
- A free **Groq API key** → https://console.groq.com/keys

```bash
pip install -r requirements.txt
```

## Setup & launch

### 1. Set your API key

**Option A — in-app Settings (recommended):** open the app, click **⚙ Settings**
and paste your LLM API key. It is saved to your browser's `localStorage` (never
on the server).

**Option B — `.env` file (persists server-side):**

```bash
copy .env.example .env   # then edit .env: GROQ_API_KEY=gsk_xxxx
```

### 2. Run it

```bash
python app.py
```

Then open **http://127.0.0.1:8000** in your browser.

To use a different port:

```bash
# Windows (PowerShell)
$env:PORT="9000"; python app.py
```

## Web PYQ search

There is **no official public "CBSE PYQ API"**, so the app combines two sources:

1. **Local question bank** — `pyq_db*.json` files seeded with well-known CBSE
   board questions (Class 9–12). Add your own by appending entries or dropping
   a new `pyq_db_*.json` file (any file matching `pyq_db*.json` is loaded).

2. **Internet search** — searches the web for PYQs on your extracted topics, then
   uses the LLM to **identify the most repeated questions/topics** across sources
   (with frequency + source URLs). Provider is configurable in **Settings**:
   - **DuckDuckGo** — free, no key (default)
   - **Tavily** — needs an API key (https://tavily.com)
   - **SerpAPI / Google** — needs an API key (https://serpapi.com)

## Universities

Switch the level toggle to **🎓 University** and enter the university/college,
course/program, semester and subject. The analysis and web PYQ search adapt to
that context (e.g. "Delhi University · B.Tech CSE · Semester 4 · Operating Systems").

## Robust backend

- Threaded HTTP server with a **bounded concurrency pool** (24 concurrent POSTs).
- LLM calls capped at **8 simultaneous** requests with **retry + backoff**.
- Request body size cap (8 MB) and per-connection timeouts.

## Project structure

```
ExamPrepAI/
├── app.py             # HTTP server (stdlib, hardened)
├── groq_service.py    # LLM calls + study-pack + web-pattern analysis
├── web_search.py      # web search (DuckDuckGo / Tavily / SerpAPI)
├── pyq_search.py      # local PYQ database matcher
├── extract.py         # text extraction from .txt/.md/.docx/.pdf uploads
├── export_service.py  # Word (.docx) + PDF export
├── pyq_db.json        # local PYQ database (part 1)
├── pyq_db_extra.json  # local PYQ database (part 2)
├── static/
│   ├── index.html     # single-page UI
│   ├── style.css      # white theme styling
│   └── app.js         # frontend logic (settings, level toggle, web trends)
├── requirements.txt
├── .env.example
└── README.md
```

## Security / privacy

- Runs **entirely locally**. Notes are sent only to the LLM API (and, for web
  search, to the chosen search provider).
- API keys live in your browser's `localStorage` and/or local `.env` — never
  stored by the app itself.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "No API key available" | Add your LLM API key in ⚙ Settings, or set `GROQ_API_KEY` in `.env`. |
| `401` from the LLM API | The key is invalid/expired — check https://console.groq.com/keys |
| `429` rate limit | Wait a moment, or switch to the fast `allam-2-7b` model in Settings. |
| Web search returns nothing | DuckDuckGo may be rate-limiting; retry, or add a Tavily/SerpAPI key in Settings. |
| Port already in use | Run with a different `PORT`, e.g. `$env:PORT="9000"; python app.py` |
