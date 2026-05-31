from __future__ import annotations

import argparse
import errno
import json
import mimetypes
import os
import shutil
import subprocess
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from audio_stems.cli import (
    AUDIO_EXTENSIONS,
    PRESETS,
    PRESET_ORDER,
    SEPARATOR_MODEL_CHOICES,
    build_command,
    build_separate_namespace,
    collect_runtime_status,
    media_index,
    resolve_separator_model,
    shell_quote,
)


@dataclass
class SeparationJob:
    id: str
    command: list[str]
    status: str = "queued"
    output: list[str] = field(default_factory=list)
    returncode: int | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None


JOBS: dict[str, SeparationJob] = {}
JOBS_LOCK = threading.Lock()


def run_web_app(host: str, port: int, open_browser: bool) -> int:
    url = frontend_url_if_running(host, port)
    if url:
        print(f"stems web app already running: {url}", flush=True)
        if open_browser:
            webbrowser.open(url)
        return 0

    static_dir = ensure_static_dir()
    if static_dir is None:
        print("React app build not found.", flush=True)
        print("Run from the source checkout with npm installed, then try: stems ui", flush=True)
        return 2

    try:
        server = ThreadingHTTPServer((host, port), make_handler(static_dir))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            url = frontend_url_if_running(host, port)
            if url:
                print(f"stems web app already running: {url}", flush=True)
                if open_browser:
                    webbrowser.open(url)
                return 0
            print(f"Port {port} is already in use, but it does not look like stems.", flush=True)
            print(f"Try another port: stems ui --port {port + 1}", flush=True)
            return 98
        raise

    url = frontend_url(host, server.server_port)
    print(f"stems web app: {url}", flush=True)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web app.", flush=True)
    finally:
        server.server_close()
    return 0


def frontend_url_if_running(host: str = "127.0.0.1", port: int = 8765) -> str | None:
    url = frontend_url(host, port)
    try:
        with urlopen(f"{url}/api/health", timeout=0.25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError):
        return None
    if payload.get("app") != "audio-stems":
        return None
    return url


def frontend_url(host: str, port: int) -> str:
    browser_host = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}"


def ensure_static_dir() -> Path | None:
    static_dir = find_static_dir()
    if static_dir is not None:
        return static_dir

    web_source_dir = find_web_source_dir()
    npm = shutil.which("npm")
    if web_source_dir is None or npm is None:
        return None

    print("Building React web app...", flush=True)
    if not (web_source_dir / "node_modules").exists():
        install = subprocess.run([npm, "install"], cwd=web_source_dir, check=False)
        if install.returncode != 0:
            return None

    build = subprocess.run([npm, "run", "build"], cwd=web_source_dir, check=False)
    if build.returncode != 0:
        return None

    return find_static_dir()


def find_static_dir() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "web" / "dist"
        if (candidate / "index.html").exists():
            return candidate
    return None


def find_web_source_dir() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "web"
        if (candidate / "package.json").exists():
            return candidate
    return None


def make_handler(static_dir: Path) -> type[BaseHTTPRequestHandler]:
    class StemsWebHandler(BaseHTTPRequestHandler):
        server_version = "audio-stems-web/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self.write_json(health_payload())
                return
            if parsed.path == "/api/presets":
                self.write_json(presets_payload())
                return
            if parsed.path == "/api/runtime":
                self.write_json(runtime_payload())
                return
            if parsed.path == "/api/search":
                params = parse_qs(parsed.query)
                query = params.get("query", [""])[0]
                self.write_json(search_payload(query))
                return
            if parsed.path == "/api/browse":
                params = parse_qs(parsed.query)
                path = params.get("path", [None])[0]
                try:
                    self.write_json(browse_payload(path))
                except ValueError as exc:
                    self.write_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            if parsed.path == "/api/jobs":
                self.write_json(jobs_payload())
                return
            if parsed.path.startswith("/api/jobs/"):
                self.write_job(parsed.path.removeprefix("/api/jobs/"))
                return

            self.serve_static(parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/command-preview":
                self.handle_command_preview()
                return
            if parsed.path == "/api/jobs":
                self.handle_create_job()
                return
            self.write_error(HTTPStatus.NOT_FOUND, "Endpoint not found.")

        def handle_command_preview(self) -> None:
            try:
                payload = self.read_json()
                namespace = payload_to_namespace(payload, dry_run=True)
                command = build_command(namespace)
            except (KeyError, TypeError, ValueError) as exc:
                self.write_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self.write_json(command_payload(command))

        def handle_create_job(self) -> None:
            try:
                payload = self.read_json()
                namespace = payload_to_namespace(payload, dry_run=False)
                validation_errors = validate_run_inputs(namespace)
                if validation_errors:
                    self.write_error(HTTPStatus.BAD_REQUEST, "\n".join(validation_errors))
                    return
                command = build_command(namespace)
            except (KeyError, TypeError, ValueError) as exc:
                self.write_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            job = create_job(command)
            self.write_json(job_payload(job), status=HTTPStatus.CREATED)

        def write_job(self, job_id: str) -> None:
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if job is None:
                self.write_error(HTTPStatus.NOT_FOUND, "Job not found.")
                return
            self.write_json(job_payload(job))

        def serve_static(self, path: str) -> None:
            relative = path.lstrip("/") or "index.html"
            candidate = (static_dir / relative).resolve()
            if not path_is_relative_to(candidate, static_dir) or not candidate.exists():
                candidate = static_dir / "index.html"

            if not candidate.is_file():
                self.write_error(HTTPStatus.NOT_FOUND, "File not found.")
                return

            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            data = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8") if raw else "{}")
            if not isinstance(data, dict):
                raise TypeError("Expected a JSON object.")
            return data

        def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def write_error(self, status: HTTPStatus, message: str) -> None:
            self.write_json({"error": message}, status=status)

        def log_message(self, format: str, *args: object) -> None:
            return

    return StemsWebHandler


def health_payload() -> dict[str, Any]:
    return {"app": "audio-stems", "status": "ok"}


def presets_payload() -> dict[str, Any]:
    return {
        "presets": [
            {
                "name": name,
                "engine": PRESETS[name].engine,
                "model": PRESETS[name].model,
                "description": PRESETS[name].description,
                "twoStems": PRESETS[name].two_stems,
            }
            for name in PRESET_ORDER
        ],
        "separatorModels": [
            {"alias": alias, "filename": filename, "description": description}
            for alias, filename, description in SEPARATOR_MODEL_CHOICES
        ],
        "devices": ["auto", "cuda", "cpu"],
        "formats": ["WAV", "FLAC", "MP3"],
        "audioExtensions": sorted(AUDIO_EXTENSIONS),
    }


def runtime_payload() -> dict[str, Any]:
    status = collect_runtime_status()
    return {
        "pythonReady": True,
        "ffmpeg": status.ffmpeg,
        "gpu": status.gpu_summary,
        "nvidiaSmi": status.nvidia_smi,
        "demucs": status.demucs,
        "audioSeparator": status.audio_separator,
        "uv": status.uv,
        "setupScript": str(status.setup_script) if status.setup_script else None,
        "ready": bool(status.ffmpeg and status.demucs),
    }


def search_payload(query: str) -> dict[str, Any]:
    if not query.strip():
        return {"results": []}

    results = []
    for path in media_index().search(query):
        results.append(
            {
                "path": str(path),
                "name": path.name or str(path),
                "directory": str(Path(path).parent),
            }
        )
    return {"results": results}


def browse_payload(raw_path: str | None) -> dict[str, Any]:
    if raw_path:
        path = Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()
    else:
        path = Path.home().resolve()

    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Path is not a folder: {path}")

    entries: list[dict[str, Any]] = []
    try:
        children = list(path.iterdir())
    except OSError as exc:
        raise ValueError(f"Cannot open folder: {path}") from exc

    for child in sorted(children, key=browse_sort_key):
        is_dir = child.is_dir()
        if not is_dir and child.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        entries.append(
            {
                "name": child.name,
                "path": str(child),
                "kind": "directory" if is_dir else "file",
                "selectable": not is_dir,
            }
        )

    parent = str(path.parent) if path.parent != path else None
    return {
        "path": str(path),
        "parent": parent,
        "entries": entries,
        "roots": browse_roots(),
    }


def browse_sort_key(path: Path) -> tuple[int, str]:
    return (0 if path.is_dir() else 1, path.name.lower())


def browse_roots() -> list[dict[str, str]]:
    candidates = [Path.home(), Path.cwd(), Path("/mnt"), Path("/media")]
    roots = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        roots.append({"label": str(candidate), "path": str(resolved)})
    return roots


def jobs_payload() -> dict[str, Any]:
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda job: job.started_at, reverse=True)
    return {"jobs": [job_payload(job) for job in jobs]}


def job_payload(job: SeparationJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "command": job.command,
        "commandLine": command_line(job.command),
        "output": job.output,
        "returncode": job.returncode,
        "startedAt": job.started_at,
        "finishedAt": job.finished_at,
        "error": job.error,
    }


def command_payload(command: list[str]) -> dict[str, Any]:
    return {"command": command, "commandLine": command_line(command)}


def command_line(command: list[str]) -> str:
    return "+ " + " ".join(shell_quote(part) for part in command)


def payload_to_namespace(payload: dict[str, Any], dry_run: bool) -> argparse.Namespace:
    inputs = payload.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("Choose at least one input file.")

    input_paths = []
    for value in inputs:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Input paths must be non-empty strings.")
        input_paths.append(Path(os.path.expandvars(os.path.expanduser(value))).resolve())

    preset = payload.get("preset", "demucs")
    if not isinstance(preset, str) or preset not in PRESETS:
        raise ValueError("Choose a valid preset.")

    out = payload.get("out", "separated")
    if not isinstance(out, str) or not out.strip():
        raise ValueError("Choose an output directory.")

    device = payload.get("device", "auto")
    if device not in {"auto", "cuda", "cpu"}:
        raise ValueError("Choose a valid device.")

    output_format = payload.get("format", "WAV")
    if output_format not in {"WAV", "FLAC", "MP3"}:
        raise ValueError("Choose a valid output format.")

    separator_model = payload.get("separatorModel")
    if separator_model is not None:
        if not isinstance(separator_model, str) or not separator_model.strip():
            raise ValueError("Choose a valid separator model.")
        separator_model = resolve_separator_model(separator_model)

    return build_separate_namespace(
        inputs=input_paths,
        preset=preset,
        out=Path(os.path.expandvars(os.path.expanduser(out))).resolve(),
        device=str(device),
        separator_model=separator_model,
        output_format=str(output_format),
        dry_run=dry_run,
    )


def validate_run_inputs(namespace: argparse.Namespace) -> list[str]:
    errors = []
    for path in namespace.inputs:
        if not path.exists():
            errors.append(f"Input file not found: {path}")
        elif not path.is_file():
            errors.append(f"Input path must be a file: {path}")
        elif path.suffix.lower() not in AUDIO_EXTENSIONS:
            errors.append(f"Expected an audio/video file: {path}")
    return errors


def create_job(command: list[str]) -> SeparationJob:
    job = SeparationJob(id=uuid.uuid4().hex, command=command)
    with JOBS_LOCK:
        JOBS[job.id] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return job


def run_job(job: SeparationJob) -> None:
    update_job(job.id, status="running")
    try:
        process = subprocess.Popen(
            job.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        update_job(
            job.id,
            status="failed",
            returncode=127,
            finished_at=time.time(),
            error=f"Missing executable: {exc.filename}",
        )
        return

    assert process.stdout is not None
    for line in process.stdout:
        append_job_output(job.id, line.rstrip())

    returncode = process.wait()
    update_job(
        job.id,
        status="completed" if returncode == 0 else "failed",
        returncode=returncode,
        finished_at=time.time(),
    )


def append_job_output(job_id: str, line: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.output.append(line)


def update_job(job_id: str, **changes: Any) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        for name, value in changes.items():
            setattr(job, name, value)


def path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
