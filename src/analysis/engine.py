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
