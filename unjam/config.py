"""Small helpers for configuration (no extra dependency needed)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "real"
OUTPUT_DIR = ROOT / "outputs"
LOG_SUFFIXES = (".xes", ".xes.gz", ".csv", ".csv.gz", ".zip")

BPI_NOTE = (
    "Proxy process: this is a real, anonymised loan/overdraft application log from a "
    "Dutch financial institution (BPI Challenge 2012), not a Bangladeshi bank."
)
GENERIC_NOTE = "Real event log supplied by the user. Check the data source and its terms of use."


def load_env(path: Path | None = None) -> None:
    """Read KEY=VALUE lines from .env into os.environ (existing variables win)."""
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def gemini_key() -> str:
    load_env()
    return os.environ.get("GEMINI_API_KEY", "").strip()


def gemini_model() -> str:
    load_env()
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"


def data_note(dataset_name: str) -> str:
    return BPI_NOTE if "BPI" in dataset_name.upper() else GENERIC_NOTE


def list_local_logs() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    files = [p for p in DATA_DIR.iterdir() if p.is_file() and p.name.lower().endswith(LOG_SUFFIXES)]
    return sorted(files, key=lambda p: p.name.lower())
