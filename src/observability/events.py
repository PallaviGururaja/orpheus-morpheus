import json

import structlog

# The four SSE event types emitted by GET /ask/stream (see spec/api.md).
STREAM_EVENTS = ("step", "token", "done", "error")


def sse_frame(event_type: str, data: dict) -> str:
    """Format one Server-Sent-Events frame: ``event: <type>\\ndata: <json>\\n\\n``."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), log_level, 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    return structlog.get_logger(name)
