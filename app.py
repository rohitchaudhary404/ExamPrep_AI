#!/usr/bin/env python3
"""
ExamPrep AI — AI-powered study assistant for schools (CBSE/ICSE/State) and universities.

A self-contained web app. Run it with:

    python app.py

then open http://127.0.0.1:8000 in your browser.

Endpoints:
  GET  /                -> the single-page UI (static/index.html)
  GET  /static/<file>   -> static assets (css/js)
  GET  /api/health      -> liveness/health check
  POST /api/analyze     -> analyse notes -> key points, important questions,
                           important topics, local PYQs + web PYQ trends.
  POST /api/extract     -> extract text from .txt/.md/.docx/.pdf uploads
  POST /api/export      -> export the study pack to .docx / .pdf
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv

from groq_service import analyze_notes, ALLOWED_MODELS
from pyq_search import get_db_stats
from extract import extract_text
from export_service import build_docx, build_pdf

load_dotenv()  # reads .env (GROQ_API_KEY, GROQ_MODEL, PORT) if present

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "127.0.0.1")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

MAX_BODY = 8 * 1024 * 1024  # 8 MB cap on request bodies
_POST_SEM = threading.BoundedSemaphore(24)  # bound concurrent POST requests


class Handler(BaseHTTPRequestHandler):
    server_version = "ExamPrepAI/1.1"
    daemon_threads = True  # don't block shutdown on stuck connections
    timeout = 300          # per-connection socket timeout (seconds)

    # ---- helpers -----------------------------------------------------------
    def _send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, content_type):
        if not os.path.isfile(path):
            self._send_json({"error": "not found"}, status=404)
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text, status=200, content_type="text/plain; charset=utf-8"):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---- routing -----------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            return self._send_file(os.path.join(STATIC_DIR, "index.html"), CONTENT_TYPES[".html"])

        if path == "/api/health":
            return self._send_json({
                "status": "ok",
                "app": "ExamPrep AI",
                "models": ALLOWED_MODELS,
                "pyq_database": get_db_stats(),
            })

        if path.startswith("/static/"):
            # prevent path traversal: resolve and ensure it stays under STATIC_DIR
            rel = path[len("/static/"):]
            full = os.path.normpath(os.path.join(STATIC_DIR, rel))
            if not full.startswith(os.path.normpath(STATIC_DIR)):
                return self._send_json({"error": "forbidden"}, status=403)
            ext = os.path.splitext(full)[1].lower()
            return self._send_file(full, CONTENT_TYPES.get(ext, "application/octet-stream"))

        self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path not in ("/api/analyze", "/api/extract", "/api/export"):
            return self._send_json({"error": "not found"}, status=404)

        with _POST_SEM:  # bound concurrency so a flood of requests can't overwhelm us
            if path == "/api/analyze":
                return self._handle_analyze()
            if path == "/api/extract":
                return self._handle_extract()
            return self._handle_export(parsed)

    # ---- POST handlers -----------------------------------------------------
    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            raise ValueError("empty request body")
        if length > MAX_BODY:
            raise ValueError("request body too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _handle_analyze(self):
        try:
            payload = self._read_json_body()
        except (ValueError, json.JSONDecodeError) as exc:
            return self._send_json({"error": f"invalid JSON body: {exc}"}, status=400)
        result = analyze_notes(payload)
        status = 400 if "error" in result else 200
        self._send_json(result, status=status)

    def _handle_extract(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return self._send_json({"error": "empty file"}, status=400)
            if length > MAX_BODY:
                return self._send_json({"error": "file too large (max 8 MB)"}, status=413)
            data = self.rfile.read(length)
            filename = self.headers.get("X-Filename", "") or "notes.txt"
            text = extract_text(data, filename)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:  # noqa: BLE001 — surface a clean message
            return self._send_json({"error": f"Could not read file: {exc}"}, status=400)
        self._send_json({"text": text, "filename": filename})

    def _handle_export(self, parsed):
        qs = parse_qs(parsed.query)
        fmt = (qs.get("format", ["md"])[0]).lower()
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, json.JSONDecodeError):
            return self._send_json({"error": "invalid JSON body"}, status=400)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload

        if fmt == "docx":
            content = build_docx(data)
            ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fname = "study-pack.docx"
        elif fmt == "pdf":
            content = build_pdf(data)
            ctype = "application/pdf"
            fname = "study-pack.pdf"
        else:
            return self._send_json({"error": f"unsupported format '{fmt}'"}, status=400)

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        # concise single-line request log
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("=" * 62)
    print("  ExamPrep AI  —  AI study assistant for schools & universities")
    print("=" * 62)
    print(f"  Serving on : http://{HOST}:{PORT}")
    print(f"  Health check: http://{HOST}:{PORT}/api/health")
    print("  Press Ctrl+C to stop.")
    print("=" * 62, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
