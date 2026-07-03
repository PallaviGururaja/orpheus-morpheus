"""Phase 2 backend-stream test fixtures."""
import json

import pytest


@pytest.fixture
def parse_sse():
    """Parse an SSE response body into a list of (event_type, data) tuples."""

    def _parse(text: str) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            event_type = None
            data_lines: list[str] = []
            for line in block.splitlines():
                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
            if event_type is None:
                continue
            raw = "\n".join(data_lines)
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"_raw": raw}
            events.append((event_type, data))
        return events

    return _parse


@pytest.fixture
def upload(api_client):
    """Upload CSV bytes and return the dataset payload."""

    def _upload(csv_bytes: bytes, name: str = "sales.csv") -> dict:
        r = api_client.post("/datasets", files={"file": (name, csv_bytes, "text/csv")})
        assert r.status_code == 200, r.text
        return r.json()["data"]

    return _upload
