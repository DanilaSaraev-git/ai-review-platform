from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers.get("content-length", "0"))
        request = json.loads(self.rfile.read(size))
        serialized = json.dumps(request)
        fixture = (
            "dialogue-response.json"
            if "finding-dialogue-input.v1" in serialized
            else "review-response.json"
        )
        content = (ROOT / fixture).read_text(encoding="utf-8")
        body = json.dumps(
            {
                "id": "compose-fake-request",
                "model": "synthetic-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("x-model-version", "synthetic-checkpoint")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


ThreadingHTTPServer(("0.0.0.0", 9000), Handler).serve_forever()  # noqa: S104
