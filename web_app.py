"""Loopback-only browser UI; .env and all API calls remain on the server.

Run: python web_app.py --open
No web framework or Node toolchain is required. This is a local single-user
experiment server, not a public hosting service.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from demo_book import OBJECTIVE, TITLE, make_demo
from gamebook_jev import (
    DEFAULT_AON_XML, Decision, GamebookEnv, JevController,
    OpenRouterJevController, ProjectAonBook, RandomController,
    download_official_xml,
)

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
MAX_STEPS = 200
SESSION_TTL = 3600
LOG = logging.getLogger("gamebook.web")


class AppError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Run:
    book_id: str
    book: ProjectAonBook
    title: str
    objective: str
    goal: str
    profile: str
    seed: int
    current: str = "1"
    path: list[str] = field(default_factory=lambda: ["1"])
    trace: list[dict] = field(default_factory=list)
    revision: int = 0
    touched: float = field(default_factory=time.monotonic)
    created: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    rng: RandomController = field(init=False)

    def __post_init__(self):
        self.rng = RandomController(self.seed)

    @property
    def status(self) -> str:
        section = self.book.sections.get(self.current)
        if section is None:
            return "missing_section"
        if section.deadend:
            return "deadend"
        if self.current == self.goal:
            return "success"
        if not section.choices:
            return "no_choice_terminal"
        if self.path.count(self.current) >= 6:
            return "loop"
        if len(self.trace) >= MAX_STEPS:
            return "max_steps"
        return "live"

    def snapshot(self) -> dict:
        section = self.book.sections.get(self.current)
        return {
            "book": self.book_id, "title": self.title, "objective": self.objective,
            "goal": self.goal, "revision": self.revision, "current": self.current,
            "path": self.path[:], "steps": len(self.trace), "status": self.status,
            "mode": "navigation_only", "total_sections": len(self.book.sections),
            "section": asdict(section) if section else None,
            "last_decision": self.trace[-1] if self.trace else None,
            "max_steps": MAX_STEPS,
        }


class GamebookService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.runs: dict[str, Run] = {}
        self.lock = threading.Lock()
        self.download_lock = threading.Lock()
        self.aon_book: ProjectAonBook | None = None
        self.csrf = secrets.token_urlsafe(32)

    @property
    def xml_path(self) -> Path:
        return self.root / "01fftd.xml"

    @staticmethod
    def key(backend: str) -> str:
        name = "JEV_API_KEY" if backend == "jev" else "OPENROUTER_API_KEY"
        value = os.getenv(name, "").strip()
        if backend == "jev" and not value:
            value = os.getenv("TYPESAFE_API_KEY", "").strip()
        return value

    def status(self) -> dict:
        return {
            "csrf": self.csrf,
            "keys": {"jev": bool(self.key("jev")), "openrouter": bool(self.key("openrouter"))},
            "books": [
                {"id": "demo", "title": TITLE, "ready": True, "original": True},
                {"id": "aon", "title": "Flight from the Dark", "ready": self.xml_path.is_file(), "original": False},
            ],
            "mode": "navigation_only", "max_steps": MAX_STEPS,
        }

    def new_run(self, data: dict) -> dict:
        book_id = data.get("book", "demo")
        if book_id == "demo":
            book, title, goal, objective = make_demo(), TITLE, "12", OBJECTIVE
        elif book_id == "aon":
            if not self.xml_path.is_file():
                raise AppError("Project Aon XML is not installed. Read the license and use Download in Settings.", 409)
            try:
                if self.aon_book is None:
                    self.aon_book = ProjectAonBook.from_file(self.xml_path)
                book = self.aon_book
            except Exception:
                raise AppError("The local Project Aon XML could not be parsed.", 422) from None
            title, goal = "Flight from the Dark", "350"
            objective = "Reach Holmgard and warn the King of the invasion."
        else:
            raise AppError("Unknown book.")
        profile = data.get("profile", "")
        if not isinstance(profile, str) or len(profile) > 8000:
            raise AppError("Profile must be text, at most 8000 characters.")
        seed = data.get("seed", 17)
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise AppError("Seed must be an integer between 0 and 4294967295.")
        run = Run(book_id, book, title, objective, goal, profile, seed)
        with self.lock:
            now = time.monotonic()
            # Never evict an active in-flight request.
            for sid, old in list(self.runs.items()):
                if now - old.touched > SESSION_TTL and not old.lock.locked():
                    del self.runs[sid]
            if len(self.runs) >= 64:
                raise AppError("Too many open runs. Restart the local server to clear them.", 429)
            run_id = secrets.token_urlsafe(24)
            self.runs[run_id] = run
        return {"run_id": run_id, **run.snapshot()}

    def get_run(self, run_id: str) -> Run:
        with self.lock:
            run = self.runs.get(run_id)
        if run is None:
            raise AppError("Run expired. Start a new run.", 404)
        run.touched = time.monotonic()
        return run

    def step(self, run_id: str, data: dict) -> dict:
        run = self.get_run(run_id)
        if not run.lock.acquire(blocking=False):
            raise AppError("A step is already in progress.", 409)
        try:
            if type(data.get("revision")) is not int or data["revision"] != run.revision:
                raise AppError("Stale step. Refresh the run before trying again.", 409)
            if run.status != "live":
                raise AppError("This run has ended. Start a new run.", 409)
            section = run.book.sections[run.current]
            choices = {c.key: c for c in section.choices}
            manual = data.get("choice")
            backend = data.get("backend", "random")
            if not isinstance(backend, str) or backend not in {"random", "jev", "openrouter"}:
                raise AppError("Unknown controller.")
            if manual is not None:
                if not isinstance(manual, str) or manual not in choices:
                    raise AppError("That choice is not present in this passage.")
                decision = Decision(manual, 0.0, {}, 0.0)
                source = "manual"
            elif len(choices) == 1:
                # A forced continuation is an engine action, not model confidence.
                decision = Decision(next(iter(choices)), 0.0, {}, 0.0)
                source = "forced"
            else:
                source = backend
                if backend == "random":
                    controller = run.rng
                else:
                    key = self.key(backend)
                    if not key:
                        raise AppError(f"Set {'JEV_API_KEY' if backend == 'jev' else 'OPENROUTER_API_KEY'} in .env and restart the server.", 409)
                    controller = (
                        JevController(key, model=os.getenv("JEV_MODEL", "jev-latest"))
                        if backend == "jev" else
                        OpenRouterJevController(key, model=os.getenv("OPENROUTER_MODEL", "typesafe/jev-1.13"))
                    )
                env = GamebookEnv(run.book, profile=run.profile or "No special items or skills supplied.")
                # Actual observed choice history, never future passages or solution routes.
                recent = [{"section": t["section"], "action": t["choice_text"]} for t in run.trace[-12:]]
                state = (f"BOOK: {run.title}\nOBJECTIVE: {run.objective}\n"
                         + env.build_state(section, run.path)
                         + "\nOBSERVED ACTIONS: " + json.dumps(recent, ensure_ascii=False))
                try:
                    decision = controller.choose(state, section.choices)
                except requests.HTTPError as exc:
                    code = exc.response.status_code if exc.response is not None else 502
                    raise AppError(f"Provider returned HTTP {code}. Check the key, credits and model access. No retry was made.", 502) from None
                except requests.RequestException:
                    raise AppError("Provider could not be reached. Check the connection; the current passage was preserved.", 502) from None
                except (ValueError, KeyError, TypeError):
                    raise AppError("Provider returned an unexpected decision format.", 502) from None
            if decision.choice_key not in choices:
                raise AppError("Provider selected an unknown action; the passage was not changed.", 502)
            chosen = choices[decision.choice_key]
            if chosen.target not in run.book.sections:
                raise AppError("The selected destination is missing from this book.", 422)
            trace = {
                "step": len(run.trace) + 1, "section": run.current,
                "source": source, "choice": chosen.key, "choice_text": chosen.text,
                "target": chosen.target, "options": [asdict(c) for c in section.choices],
                "confidence": decision.confidence if source in {"jev", "openrouter", "random"} else None,
                "probabilities": decision.probabilities,
                "latency_ms": decision.latency_ms, "timestamp": time.time(),
            }
            # Reject non-finite values rather than send invalid JSON/paint misleading bars.
            import math
            if not math.isfinite(trace["latency_ms"]) or trace["latency_ms"] < 0:
                raise AppError("Provider returned invalid timing.", 502)
            if trace["confidence"] is not None and not (math.isfinite(trace["confidence"]) and 0 <= trace["confidence"] <= 1):
                raise AppError("Provider returned invalid confidence.", 502)
            if any(k not in choices or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
                   for k, v in trace["probabilities"].items()):
                raise AppError("Provider returned invalid probabilities.", 502)
            if source in {"jev", "openrouter"}:
                probabilities = trace["probabilities"]
                if set(probabilities) != set(choices) or abs(sum(probabilities.values()) - 1.0) > .005:
                    raise AppError("Provider returned an incomplete probability distribution.", 502)
            run.trace.append(trace)
            run.current = chosen.target
            run.path.append(chosen.target)
            run.revision += 1
            run.touched = time.monotonic()
            return {"run_id": run_id, **run.snapshot()}
        finally:
            run.lock.release()

    def export(self, run_id: str) -> dict:
        run = self.get_run(run_id)
        with run.lock:
            return {"format": "jev-gamebook-run/v1", "mode": "navigation_only",
                    "book": run.book_id, "title": run.title, "seed": run.seed,
                    "started_at": run.created, "status": run.status,
                    "path": run.path[:], "trace": run.trace[:],
                    "limitations": "No combat, inventory mutation, prerequisite enforcement or dice simulation."}

    def download_aon(self, data: dict) -> dict:
        if data.get("license_reviewed") is not True:
            raise AppError("Read the Project Aon license before downloading.")
        if not self.download_lock.acquire(blocking=False):
            raise AppError("A download is already in progress.", 409)
        temp = self.xml_path.with_suffix(".download")
        try:
            if not self.xml_path.is_file():
                try:
                    download_official_xml(DEFAULT_AON_XML, temp)
                    book = ProjectAonBook.from_file(temp)
                    if "1" not in book.sections or "350" not in book.sections:
                        raise ValueError("wrong book")
                    temp.replace(self.xml_path)
                    self.aon_book = book
                except Exception:
                    temp.unlink(missing_ok=True)
                    raise AppError("Could not download/parse the official XML. Place 01fftd.xml beside web_app.py instead.", 502) from None
            return self.status()
        finally:
            self.download_lock.release()


class Handler(BaseHTTPRequestHandler):
    server: "LocalServer"

    def log_message(self, fmt, *args):
        # Do not log opaque session IDs, profiles, or raw upstream responses.
        LOG.info("%s %s", self.command, args[1] if len(args) > 1 else "request")

    def reply(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self' https://cdn.jsdelivr.net; media-src 'self' blob:; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json_reply(self, data: dict, status: int = 200):
        self.reply(status, json.dumps(data, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8")

    def guard(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host", "") not in allowed:
            raise AppError("Local Host required.", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise AppError("Cross-site requests are not permitted.", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in allowed}:
            raise AppError("Origin not permitted.", 403)
        if self.command == "POST":
            if not secrets.compare_digest(self.headers.get("X-Gamebook-Token", ""), self.server.service.csrf):
                raise AppError("Missing session token. Reload the page.", 403)
            if self.headers.get_content_type() != "application/json":
                raise AppError("JSON content type required.", 415)

    def do_GET(self):
        try:
            self.guard()
            path = unquote(urlsplit(self.path).path)
            if path == "/api/status":
                return self.json_reply(self.server.service.status())
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "export":
                return self.json_reply(self.server.service.export(parts[2]))
            if len(parts) == 3 and parts[:2] == ["api", "runs"]:
                run = self.server.service.get_run(parts[2])
                with run.lock:
                    return self.json_reply({"run_id": parts[2], **run.snapshot()})
            name = "index.html" if path == "/" else path.removeprefix("/static/")
            if path != "/" and not path.startswith("/static/"):
                raise AppError("Not found.", 404)
            file = (WEB / name).resolve()
            if WEB not in file.parents or file.suffix not in {".html", ".css", ".js", ".svg"} or not file.is_file():
                raise AppError("Not found.", 404)
            mime = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml"}[file.suffix]
            self.reply(200, file.read_bytes(), mime + "; charset=utf-8")
        except AppError as exc:
            self.json_reply({"error": str(exc)}, exc.status)
        except Exception:
            LOG.error("Unhandled local GET error")
            self.json_reply({"error": "Local server error."}, 500)

    def do_POST(self):
        try:
            self.guard()
            length = self.headers.get("Content-Length", "")
            if not length.isdecimal() or not 0 < int(length) <= 32768:
                raise AppError("Request size must be between 1 and 32768 bytes.", 413)
            try:
                data = json.loads(self.rfile.read(int(length)))
            except (ValueError, UnicodeDecodeError):
                raise AppError("Invalid JSON.") from None
            if not isinstance(data, dict):
                raise AppError("Expected a JSON object.")
            path = urlsplit(self.path).path
            parts = path.strip("/").split("/")
            if path == "/api/runs":
                result = self.server.service.new_run(data)
            elif path == "/api/books/aon/download":
                result = self.server.service.download_aon(data)
            elif len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "step":
                result = self.server.service.step(parts[2], data)
            else:
                raise AppError("Not found.", 404)
            self.json_reply(result)
        except AppError as exc:
            self.json_reply({"error": str(exc)}, exc.status)
        except Exception:
            LOG.error("Unhandled local POST error")
            self.json_reply({"error": "Local server error. No automatic retry was made."}, 500)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int, service: GamebookService | None = None):
        self.service = service or GamebookService()
        super().__init__(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="The Decision Library — local gamebook UI")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="Open the local UI in your browser")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    server = LocalServer(args.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"\nThe Decision Library: {url}\nLocal only. Press Ctrl+C to stop.\n", flush=True)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
