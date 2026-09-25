from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .scenario import build_scenario, scenario_from_dict
from .simulator import run_comparison


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "static"


def generate_payload(
    threat_count: int = 20,
    interceptor_count: int = 12,
    seed: int = 42,
    duration_s: int = 190,
    enable_events: bool = True,
) -> dict:
    return run_comparison(
        build_scenario(
            threat_count=threat_count,
            interceptor_count=interceptor_count,
            seed=seed,
            duration_s=duration_s,
            enable_events=enable_events,
        )
    )


def _bounded_int(query: dict[str, list[str]], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = query.get(name, [str(default)])[0]
    value = int(raw)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


class SwarmShieldHandler(BaseHTTPRequestHandler):
    server_version = "SwarmShield/1.0"

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            self._send(200, "application/json", b'{"status":"ok","version":"1.0"}')
            return
        if path == "/api/run":
            try:
                query = parse_qs(parsed.query)
                payload = generate_payload(
                    threat_count=_bounded_int(query, "threats", 20, 1, 200),
                    interceptor_count=_bounded_int(query, "interceptors", 12, 0, 120),
                    seed=_bounded_int(query, "seed", 42, 0, 1_000_000),
                    duration_s=_bounded_int(query, "duration", 190, 30, 600),
                    enable_events=query.get("events", ["1"])[0] not in {"0", "false", "off"},
                )
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self._send(200, "application/json", body)
            except (ValueError, TypeError) as error:
                body = json.dumps({"error": str(error)}).encode("utf-8")
                self._send(400, "application/json", body)
            return
        file_path = STATIC_ROOT / ("index.html" if path == "/" else path.lstrip("/"))
        try:
            resolved = file_path.resolve()
            resolved.relative_to(STATIC_ROOT.resolve())
        except (ValueError, OSError):
            self._send(403, "text/plain", b"Forbidden")
            return
        if not resolved.is_file():
            self._send(404, "text/plain", b"Not found")
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self._send(200, content_type, resolved.read_bytes())

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/run":
            self._send(404, "application/json", b'{"error":"Not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("Scenario JSON must be between 1 byte and 2 MB")
            raw = json.loads(self.rfile.read(length))
            scenario = scenario_from_dict(raw)
            payload = run_comparison(scenario)
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._send(200, "application/json", body)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            body = json.dumps({"error": str(error)}).encode("utf-8")
            self._send(400, "application/json", body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[web] {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SwarmShield dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), SwarmShieldHandler)
    print(f"SwarmShield ready at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
