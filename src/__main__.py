import sys
from pathlib import Path

import uvicorn

# Ensure the flat src/ package dir is importable (bare imports: `from api import ...`).
_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if __name__ == "__main__":
    # Bound to localhost only — nothing leaves the machine.
    uvicorn.run("api:app", host="127.0.0.1", port=8001, reload=False)
