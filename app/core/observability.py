import json
import logging
import re
import time
from collections import Counter
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

request_counts: Counter[str] = Counter()
uuid_pattern = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            root.setLevel(logging.INFO)
            return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


async def observe(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        request_counts[f"{request.method} {request.url.path} 500"] += 1
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    path = uuid_pattern.sub("{id}", request.url.path)
    key = f"{request.method} {path} {response.status_code}"
    if key in request_counts or len(request_counts) < 1000:
        request_counts[key] += 1
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


def metrics() -> dict[str, dict[str, int]]:
    result: dict[str, int] = {}
    for key, count in request_counts.items():
        result[key] = count
    return {"requests": result}
