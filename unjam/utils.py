from __future__ import annotations

import pandas as pd


def fmt_hours(h, digits: int = 1) -> str:
    """Human friendly duration from hours: '35 min', '3.2 hours', '4.1 days'."""
    if h is None or pd.isna(h):
        return "n/a"
    h = float(h)
    if abs(h) < 1:
        return f"{h * 60:.0f} min"
    if abs(h) < 48:
        return f"{h:.{digits}f} hours"
    return f"{h / 24:.{digits}f} days"


def fmt_pct(x, digits: int = 1) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"{float(x) * 100:.{digits}f}%"


def fmt_int(n) -> str:
    if n is None or pd.isna(n):
        return "n/a"
    return f"{int(n):,}"


def md_table(rows: list[dict]) -> str:
    """Tiny markdown table writer (avoids the 'tabulate' dependency)."""
    if not rows:
        return "_No data._"
    cols = list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c in cols) + " |")
    return "\n".join(out)


def dataset_title(file_name: str) -> str:
    """'BPI_Challenge_2012.xes.gz' -> 'BPI Challenge 2012'."""
    base = file_name
    for suffix in (".gz", ".zip", ".xes", ".csv"):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
    return base.replace("_", " ").strip() or "event log"
