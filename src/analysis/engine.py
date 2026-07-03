"""Dataset ingestion + on-disk storage for the analysis engine."""
from pathlib import Path

import pandas as pd

from config.settings import get_settings


def _store_root() -> Path:
    return Path(get_settings().dataset_store).resolve()


def store_upload(dataset_id: str, filename: str, content: bytes) -> str:
    """Persist uploaded bytes under ./data/datasets/<dataset_id>/<filename>.

    Returns the absolute on-disk storage path.
    """
    safe_name = Path(filename).name or "dataset.csv"
    target_dir = _store_root() / dataset_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / safe_name
    path.write_bytes(content)
    return str(path)


def load_csv(path: str) -> pd.DataFrame:
    """Load a CSV file from disk into a pandas DataFrame."""
    return pd.read_csv(path)


def table_name_for(name: str, taken: set[str]) -> str:
    """Derive a SQL/identifier-safe table name from a dataset name.

    Strips the extension, lowercases, replaces non-alphanumerics with ``_``,
    and disambiguates collisions with a numeric suffix so several datasets in
    one session never map to the same table name.
    """
    import re

    stem = Path(name).stem or "table"
    safe = re.sub(r"[^0-9a-zA-Z]+", "_", stem).strip("_").lower()
    if not safe or not safe[0].isalpha():
        safe = f"t_{safe}" if safe else "table"
    candidate = safe
    i = 2
    while candidate in taken:
        candidate = f"{safe}_{i}"
        i += 1
    taken.add(candidate)
    return candidate


def load_tables(specs: list[tuple[str, str]]) -> dict[str, pd.DataFrame]:
    """Load several CSVs into an ordered ``{table_name: DataFrame}`` map.

    ``specs`` is a list of ``(table_name, storage_path)`` pairs (already
    de-duplicated by :func:`table_name_for`).
    """
    return {tname: load_csv(path) for tname, path in specs}
