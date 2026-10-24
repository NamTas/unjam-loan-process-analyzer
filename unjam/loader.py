"""Read an event log (XES or CSV) and turn it into clean 'step instances'.

Pipeline:  file -> raw table -> standard events -> step instances (+ waiting times)

Standard event columns : case_id, activity, timestamp, lifecycle, resource, seq
Step instance columns  : case_id, activity, start, end, resource, ... (see prepare_instances)

No process-mining library is needed: the XES parser below is a small streaming XML reader.
"""
from __future__ import annotations

import gzip
import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd


class LogFormatError(ValueError):
    """Raised when the file cannot be understood as an event log."""


# --------------------------------------------------------------------------- XES

_ATTR_TAGS = {"string", "date", "int", "float", "boolean", "id"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_xes(fileobj) -> pd.DataFrame:
    """Stream-parse an XES file into a flat table (one row per event)."""
    rows: list[tuple] = []
    stack: list[str] = []
    case_id: str | None = None
    event: dict | None = None
    trace_no = 0
    try:
        for action, elem in ET.iterparse(fileobj, events=("start", "end")):
            tag = _local(elem.tag)
            if action == "start":
                stack.append(tag)
                if tag == "trace":
                    trace_no += 1
                    case_id = f"trace_{trace_no}"
                elif tag == "event":
                    event = {}
                continue

            stack.pop()
            parent = stack[-1] if stack else None
            if tag in _ATTR_TAGS and parent in ("event", "trace"):
                key, value = elem.get("key"), elem.get("value")
                if parent == "event" and event is not None:
                    event[key] = value
                elif parent == "trace" and key == "concept:name" and value:
                    case_id = value
                elem.clear()
            elif tag == "event":
                if event is not None and case_id is not None:
                    rows.append(
                        (
                            case_id,
                            event.get("concept:name"),
                            event.get("time:timestamp"),
                            event.get("lifecycle:transition", ""),
                            event.get("org:resource", ""),
                        )
                    )
                event = None
                elem.clear()
            elif tag == "trace":
                case_id = None
                elem.clear()
    except ET.ParseError as exc:
        raise LogFormatError(f"This does not look like a valid XES file: {exc}") from exc

    if not rows:
        raise LogFormatError("The XES file has no events (no <trace>/<event> elements found).")
    return pd.DataFrame(rows, columns=["case_id", "activity", "timestamp", "lifecycle", "resource"])


# --------------------------------------------------------------------------- opening files

def _open_binary(source, name: str | None):
    """Return (binary file object, lower-case inner file name). Handles .gz and .zip."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        name = name or path.name
        raw = open(path, "rb")
    else:  # file-like (e.g. Streamlit upload) or bytes
        if isinstance(source, (bytes, bytearray)):
            raw = io.BytesIO(source)
        elif hasattr(source, "getvalue"):
            raw = io.BytesIO(source.getvalue())
        else:
            raw = source
        name = name or getattr(source, "name", "uploaded")
    lower = str(name).lower()
    if lower.endswith(".gz"):
        return gzip.GzipFile(fileobj=raw), lower[:-3]
    if lower.endswith(".zip"):
        zf = zipfile.ZipFile(raw)
        members = [m for m in zf.namelist() if not m.endswith("/")]
        if not members:
            raise LogFormatError("The zip file is empty.")
        inner = members[0]
        return zf.open(inner), inner.lower()
    return raw, lower


def _read_csv(fileobj) -> pd.DataFrame:
    data = fileobj.read()
    last_error: Exception | None = None
    for sep in (",", ";", "\t", "|"):
        try:
            df = pd.read_csv(io.BytesIO(data), sep=sep, dtype=str, keep_default_na=True)
        except Exception as exc:  # noqa: BLE001 - try next separator
            last_error = exc
            continue
        if df.shape[1] > 1:
            return df
    raise LogFormatError(f"Could not read the CSV (tried , ; tab |). {last_error or ''}".strip())


def read_raw(source, name: str | None = None) -> tuple[pd.DataFrame, str]:
    """Read a file into a raw table. Returns (table, kind) where kind is 'xes' or 'csv'."""
    fileobj, inner = _open_binary(source, name)
    try:
        if inner.endswith(".xes") or inner.endswith(".xml"):
            return parse_xes(fileobj), "xes"
        if inner.endswith(".csv") or inner.endswith(".txt") or inner.endswith(".tsv"):
            return _read_csv(fileobj), "csv"
    finally:
        try:
            fileobj.close()
        except Exception:  # noqa: BLE001
            pass
    raise LogFormatError("Unsupported file type. Use .xes, .xes.gz, .csv, .csv.gz or .zip.")


# --------------------------------------------------------------------------- column mapping

_CANDIDATES = {
    "case_id": ["case_id", "case id", "case:concept:name", "caseid", "case", "trace", "application_id"],
    "activity": ["activity", "concept:name", "event", "task", "activity_name", "event_name", "step"],
    "timestamp": ["timestamp", "time:timestamp", "time", "datetime", "date", "end_time", "complete_timestamp"],
    "lifecycle": ["lifecycle", "lifecycle:transition", "transition"],
    "resource": ["resource", "org:resource", "user", "agent", "employee"],
}


def guess_columns(columns) -> dict[str, str | None]:
    """Guess which CSV column plays which role. Users can override in the UI."""
    lowered = {str(c).strip().lower(): c for c in columns}
    result: dict[str, str | None] = {}
    for role, names in _CANDIDATES.items():
        result[role] = next((lowered[n] for n in names if n in lowered), None)
    return result


STANDARD_ROLES = ("case_id", "activity", "timestamp", "lifecycle", "resource")


def standardize(raw: pd.DataFrame, mapping: dict[str, str | None] | None = None) -> tuple[pd.DataFrame, dict]:
    """Map a raw table to standard event columns and report data quality."""
    mapping = dict(mapping or guess_columns(raw.columns))
    missing = [r for r in ("case_id", "activity", "timestamp") if not mapping.get(r) or mapping[r] not in raw.columns]
    if missing:
        raise LogFormatError(
            "Could not find the required column(s): " + ", ".join(missing)
            + ". Pick them in the sidebar column mapping."
        )

    ts = pd.to_datetime(raw[mapping["timestamp"]], utc=True, errors="coerce").dt.tz_convert(None)
    lifecycle = raw[mapping["lifecycle"]] if mapping.get("lifecycle") in raw.columns else ""
    resource = raw[mapping["resource"]] if mapping.get("resource") in raw.columns else ""
    df = pd.DataFrame(
        {
            "case_id": raw[mapping["case_id"]],
            "activity": raw[mapping["activity"]],
            "timestamp": ts,
            "lifecycle": lifecycle,
            "resource": resource,
        }
    )
    rows_in = len(df)
    bad_ts = int(df["timestamp"].isna().sum())
    df = df.dropna(subset=["case_id", "activity", "timestamp"]).copy()
    for col in ("case_id", "activity"):
        df[col] = df[col].astype(str).str.strip()
    df["lifecycle"] = df["lifecycle"].fillna("").astype(str).str.upper().str.strip()
    df["resource"] = df["resource"].fillna("").astype(str).str.strip()
    df = df[(df["case_id"] != "") & (df["activity"] != "")].reset_index(drop=True)
    df["seq"] = range(len(df))

    if df.empty:
        raise LogFormatError("No usable events after cleaning (check the timestamp column and its format).")

    quality = {
        "rows_in": rows_in,
        "rows_dropped": rows_in - len(df),
        "unparseable_timestamps": bad_ts,
        "events": len(df),
        "cases": int(df["case_id"].nunique()),
        "activities": int(df["activity"].nunique()),
        "first_event": df["timestamp"].min(),
        "last_event": df["timestamp"].max(),
        "lifecycle_values": df["lifecycle"].replace("", "(none)").value_counts().to_dict(),
        "has_resource": bool((df["resource"] != "").any()),
    }
    return df, quality


def load_log(source, name: str | None = None, mapping: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """File (path / upload / bytes) -> (standard events, quality report)."""
    raw, kind = read_raw(source, name)
    if kind == "xes":
        mapping = {r: r for r in STANDARD_ROLES}  # parse_xes already uses standard names
    events, quality = standardize(raw, mapping)
    quality["source_kind"] = kind
    return events, quality


# --------------------------------------------------------------------------- step instances

_START = {"START"}
_COMPLETE = {"COMPLETE", "COMPLETED", ""}


def prepare_instances(events: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Merge START/COMPLETE events into one 'step instance' and compute waiting times.

    Rules (also written in docs/FSD.md):
      * COMPLETE (or no lifecycle info) ends an instance. A matching earlier START of the same
        activity in the same case gives its start time; otherwise start = end.
      * Other lifecycle values (SCHEDULE, ASSIGN, SUSPEND ...) are ignored and counted.
      * wait_h = start of this instance - latest end of all earlier instances in the case
        (never negative; the first instance has no wait). So waits are real gaps on the case timeline.
      * work_h = end - start.
    """
    ev = events.sort_values(["case_id", "timestamp", "seq"], kind="mergesort")
    ignored: dict[str, int] = {}
    unmatched_starts = 0

    out_case, out_act, out_start, out_end, out_res, out_seq = [], [], [], [], [], []
    current = None
    pending: dict[str, list] = {}

    def flush_pending() -> int:
        return sum(len(v) for v in pending.values())

    for case_id, act, ts, life, res, seq in ev[
        ["case_id", "activity", "timestamp", "lifecycle", "resource", "seq"]
    ].itertuples(index=False, name=None):
        if case_id != current:
            unmatched_starts += flush_pending()
            pending = {}
            current = case_id
        if life in _START:
            pending.setdefault(act, []).append((ts, res))
        elif life in _COMPLETE:
            queue = pending.get(act)
            if queue:
                start_ts, start_res = queue.pop(0)
                res = res or start_res
            else:
                start_ts = ts
            out_case.append(case_id)
            out_act.append(act)
            out_start.append(start_ts)
            out_end.append(ts)
            out_res.append(res)
            out_seq.append(seq)
        else:
            ignored[life] = ignored.get(life, 0) + 1
    unmatched_starts += flush_pending()

    inst = pd.DataFrame(
        {
            "case_id": out_case,
            "activity": out_act,
            "start": pd.to_datetime(out_start),
            "end": pd.to_datetime(out_end),
            "resource": out_res,
            "seq": out_seq,
        }
    )
    if inst.empty:
        raise LogFormatError("No completed steps found in the log (only ignored lifecycle events).")

    inst = inst.sort_values(["case_id", "end", "start", "seq"], kind="mergesort").reset_index(drop=True)
    t0 = inst["start"].min()
    inst["t_start"] = (inst["start"] - t0).dt.total_seconds() / 3600.0
    inst["t_end"] = (inst["end"] - t0).dt.total_seconds() / 3600.0

    by_case = inst.groupby("case_id", sort=False)
    inst["step"] = by_case.cumcount() + 1
    prev_max_end = by_case["t_end"].cummax().groupby(inst["case_id"], sort=False).shift(1)
    inst["wait_h"] = (inst["t_start"] - prev_max_end).clip(lower=0)
    inst["work_h"] = (inst["t_end"] - inst["t_start"]).clip(lower=0)
    inst["occurrence"] = inst.groupby(["case_id", "activity"], sort=False).cumcount() + 1
    inst["prev_activity"] = by_case["activity"].shift(1)
    inst["next_activity"] = by_case["activity"].shift(-1)
    inst["next_wait_h"] = by_case["wait_h"].shift(-1)

    stats = {
        "events_in": len(events),
        "instances": len(inst),
        "ignored_lifecycle": ignored,
        "unmatched_starts": int(unmatched_starts),
    }
    return inst, stats


def build_cases(inst: pd.DataFrame) -> pd.DataFrame:
    """One row per case: start, end, duration, number of steps and the path (variant)."""
    g = inst.groupby("case_id", sort=False)
    cases = pd.DataFrame(
        {
            "start": g["start"].min(),
            "end": g["end"].max(),
            "t0": g["t_start"].min(),
            "t1": g["t_end"].max(),
            "n_steps": g.size(),
            "variant": g["activity"].agg(tuple),
        }
    )
    cases["duration_h"] = cases["t1"] - cases["t0"]
    return cases
