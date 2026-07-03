"""Coverage for the in-app local file browser + load-by-path (`src/api/local_files.py`).

Real PostgreSQL (the load path persists a dataset row). No LLM needed. All
fixtures live UNDER the user's home folder so the home-confinement checks are
exercised against real paths.
"""
from pathlib import Path
from uuid import uuid4

import pytest

CUSTOMERS_CSV = "customer_id,segment\n1,Premium\n2,Standard\n"


@pytest.fixture
def home_dir_with_csv():
    """Create a throwaway folder + CSV + non-CSV UNDER the real home dir; clean up."""
    root = Path.home().resolve() / f".pytest_local_files_{uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "customers.csv"
    csv_path.write_text(CUSTOMERS_CSV, encoding="utf-8")
    txt_path = root / "notes.txt"
    txt_path.write_text("not a csv", encoding="utf-8")
    try:
        yield {"root": root, "csv": csv_path, "txt": txt_path}
    finally:
        for p in (csv_path, txt_path):
            p.unlink(missing_ok=True)
        try:
            root.rmdir()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# GET /local/browse
# --------------------------------------------------------------------------- #
def test_browse_lists_csvs_and_hides_non_csv(api_client, home_dir_with_csv):
    r = api_client.get("/local/browse", params={"path": str(home_dir_with_csv["root"])})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    names = {f["name"] for f in data["files"]}
    assert "customers.csv" in names
    assert "notes.txt" not in names  # only .csv files are listed
    # each listed file carries an absolute path + size
    csv_entry = next(f for f in data["files"] if f["name"] == "customers.csv")
    assert Path(csv_entry["path"]).is_file()
    assert csv_entry["size"] > 0


def test_browse_defaults_to_home_when_no_path(api_client):
    r = api_client.get("/local/browse")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert Path(data["cwd"]).resolve() == Path.home().resolve()
    assert data["parent"] is None  # at home root, parent is hidden
    assert any(s["label"] == "Home" for s in data["shortcuts"])


def test_browse_outside_home_rejected_403(api_client):
    # home's parent is outside the home folder — must be forbidden.
    outside = Path.home().resolve().parent
    r = api_client.get("/local/browse", params={"path": str(outside)})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "FORBIDDEN"


def test_browse_non_folder_rejected_400(api_client, home_dir_with_csv):
    r = api_client.get("/local/browse", params={"path": str(home_dir_with_csv["csv"])})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "BAD_REQUEST"


# --------------------------------------------------------------------------- #
# POST /datasets/local
# --------------------------------------------------------------------------- #
def test_load_by_path_works(api_client, home_dir_with_csv):
    r = api_client.post("/datasets/local", json={"path": str(home_dir_with_csv["csv"])})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["name"] == "customers.csv"
    assert data["row_count"] == 2
    assert data["column_count"] == 2
    assert data["session_id"] and data["dataset_id"]
    assert "columns" in data["profile"]


def test_load_path_outside_home_rejected_403(api_client):
    outside = Path.home().resolve().parent / "definitely_outside.csv"
    r = api_client.post("/datasets/local", json={"path": str(outside)})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "FORBIDDEN"


def test_load_non_csv_rejected_400(api_client, home_dir_with_csv):
    r = api_client.post("/datasets/local", json={"path": str(home_dir_with_csv["txt"])})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "BAD_REQUEST"
