"""Phantom Atlas local app: a small web server that only listens on this computer.

Start it with "Phantom Atlas.bat" (Windows) or:
    python app/server.py            # real generation (uses FAL_KEY, costs money)
    python app/server.py --fake     # test mode, no API calls
Then open http://127.0.0.1:8642
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
import traceback
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(ROOT / "gen"))

import pipeline  # noqa: E402

PORT = 8642
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
SETTINGS = {"fake": False, "quality": "high", "weird": 0.3}


def run_job(job_id: str) -> None:
    job = JOBS[job_id]

    def progress(msg: str) -> None:
        job["step"] = msg

    def on_prompt(item: dict) -> None:
        a = item["attributes"]
        job["summary"] = f"{a['setting_desc']}; {a['structures']}; {a['weather']}"
        job["surreal"] = a["surreal"]

    try:
        meta = pipeline.generate_place(SETTINGS["quality"], SETTINGS["weird"], SETTINGS["fake"],
                                       progress, on_prompt)
        job.update(status="done", place=meta, step="Done")
    except Exception as exc:  # report to the page instead of crashing the server
        traceback.print_exc()
        job.update(status="error", error=str(exc) or exc.__class__.__name__)


class Handler(BaseHTTPRequestHandler):
    server_version = "PhantomAtlas/1"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    # --- helpers -----------------------------------------------------------
    def _json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path):
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as f:
            while chunk := f.read(1 << 20):
                self.wfile.write(chunk)

    def _safe(self, base: Path, rel: str) -> Path | None:
        p = (base / rel).resolve()
        return p if base.resolve() in p.parents else None

    def _same_origin(self) -> bool:
        # Block other websites from triggering paid generations through this browser.
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")

    # --- routes ------------------------------------------------------------
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._file(STATIC / "index.html")
        if path == "/api/status":
            places = pipeline.list_gallery()
            return self._json({
                "fake": SETTINGS["fake"],
                "has_key": pipeline.has_key(),
                "quality": SETTINGS["quality"],
                "cost_per_place": 0.0 if SETTINGS["fake"] else pipeline.estimated_cost(SETTINGS["quality"]),
                "spent_total": round(sum(p.get("cost_estimate_usd", 0) for p in places), 2),
                "count": len(places),
            })
        if path == "/api/gallery":
            return self._json(pipeline.list_gallery())
        if path.startswith("/api/job/"):
            job = JOBS.get(path.rsplit("/", 1)[-1])
            return self._json(job) if job else self._json({"error": "unknown job"}, HTTPStatus.NOT_FOUND)
        if path.startswith("/gallery/"):
            p = self._safe(pipeline.GALLERY, path[len("/gallery/"):])
            return self._file(p) if p else self.send_error(HTTPStatus.FORBIDDEN)
        if path.startswith("/static/"):
            p = self._safe(STATIC, path[len("/static/"):])
            return self._file(p) if p else self.send_error(HTTPStatus.FORBIDDEN)
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._same_origin():
            return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        if path == "/api/new":
            if not SETTINGS["fake"] and not pipeline.has_key():
                return self._json({"error": "No fal.ai API key found. Add FAL_KEY=... to the .env file "
                                            "in the Phantom Atlas folder, then restart."}, HTTPStatus.BAD_REQUEST)
            with JOB_LOCK:
                running = [j for j in JOBS.values() if j["status"] == "running"]
                if running:
                    return self._json(running[0])
                job_id = uuid.uuid4().hex[:12]
                JOBS[job_id] = {"id": job_id, "status": "running", "step": "Starting"}
            threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
            return self._json(JOBS[job_id])
        self.send_error(HTTPStatus.NOT_FOUND)


def main() -> int:
    ap = argparse.ArgumentParser(description="Phantom Atlas local app")
    ap.add_argument("--fake", action="store_true", help="test mode: no API calls, no cost")
    ap.add_argument("--quality", choices=sorted(pipeline.GEN_COST), default=None)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    pipeline.load_env_file()
    SETTINGS["fake"] = args.fake
    SETTINGS["quality"] = args.quality or os.environ.get("PHANTOM_QUALITY", "high")
    if SETTINGS["quality"] not in pipeline.GEN_COST:
        SETTINGS["quality"] = "high"

    url = f"http://127.0.0.1:{PORT}"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} is busy. Phantom Atlas is probably already running; opening it.")
        if not args.no_browser:
            webbrowser.open(url)
        return 1
    print(f"Phantom Atlas is running at {url}")
    print("Mode:", "TEST (no API calls)" if args.fake else f"real generation, quality={SETTINGS['quality']}")
    if not args.fake and not pipeline.has_key():
        print("WARNING: no fal.ai key found. Add FAL_KEY=... to the .env file and restart.")
    print("Close this window to stop the app.")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
