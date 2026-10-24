"""Core analysis: step metrics, edges, variants, durations, rework, slow cases.

Everything here is plain pandas, so every number can be re-checked by hand.
Time unit is hours throughout; the UI converts to minutes/days for display.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- step (activity) metrics


def activity_metrics(inst: pd.DataFrame, n_cases: int) -> pd.DataFrame:
    """One row per activity: volume, waiting time (median / p90 / total), work time, rework rate."""
    g = inst.groupby("activity")
    m = pd.DataFrame(
        {
            "count": g.size(),
            "cases": g["case_id"].nunique(),
            "median_wait_h": g["wait_h"].median(),
            "p90_wait_h": g["wait_h"].quantile(0.9),
            "mean_wait_h": g["wait_h"].mean(),
            "total_wait_h": g["wait_h"].sum(),
            "median_work_h": g["work_h"].median(),
        }
    )
    per_case = inst.groupby(["activity", "case_id"]).size()
    m["rework_rate"] = (per_case > 1).groupby(level=0).mean()
    m["avg_exec_per_case"] = m["count"] / m["cases"]
    m["case_share"] = m["cases"] / max(n_cases, 1)
    for col in ("median_wait_h", "p90_wait_h", "mean_wait_h", "median_work_h"):
        m[col] = m[col].fillna(0.0)
    return m.sort_values("count", ascending=False)


def edge_table(inst: pd.DataFrame) -> pd.DataFrame:
    """Directly-follows relation: how often step A is followed by step B, and how long B waits."""
    d = inst.dropna(subset=["next_activity"])
    if d.empty:
        return pd.DataFrame(columns=["source", "target", "count", "cases", "median_wait_h", "p90_wait_h", "total_wait_h"])
    g = d.groupby(["activity", "next_activity"])
    e = pd.DataFrame(
        {
            "count": g.size(),
            "cases": g["case_id"].nunique(),
            "median_wait_h": g["next_wait_h"].median(),
            "p90_wait_h": g["next_wait_h"].quantile(0.9),
            "total_wait_h": g["next_wait_h"].sum(),
        }
    ).reset_index()
    e = e.rename(columns={"activity": "source", "next_activity": "target"})
    return e.sort_values("count", ascending=False).reset_index(drop=True)


def start_end_counts(inst: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    starts = inst.loc[inst["step"] == 1, "activity"].value_counts()
    ends = inst.loc[inst["next_activity"].isna(), "activity"].value_counts()
    return starts, ends


# --------------------------------------------------------------------------- variants and durations


def variant_table(cases: pd.DataFrame) -> pd.DataFrame:
    vc = cases["variant"].value_counts()
    df = vc.rename_axis("variant").reset_index(name="cases")
    df["share"] = df["cases"] / len(cases)
    df["cum_share"] = df["share"].cumsum()
    df["rank"] = np.arange(1, len(df) + 1)
    df["n_steps"] = df["variant"].map(len)
    df["path"] = df["variant"].map(lambda t: " → ".join(t))
    return df


def duration_stats(cases: pd.DataFrame) -> dict:
    d = cases["duration_h"]
    return {
        "median_h": float(d.median()),
        "p90_h": float(d.quantile(0.9)),
        "p95_h": float(d.quantile(0.95)),
        "mean_h": float(d.mean()),
        "max_h": float(d.max()),
    }


def slow_case_analysis(inst: pd.DataFrame, cases: pd.DataFrame, q: float = 0.9, min_slow_cases: int = 5):
    """Compare the slowest (1-q) share of cases with the rest.

    Returns (activity comparison table, top variants among slow cases, threshold in hours).
    """
    threshold = float(cases["duration_h"].quantile(q))
    slow_ids = cases.index[cases["duration_h"] >= threshold]
    if len(slow_ids) < min_slow_cases:
        return pd.DataFrame(), pd.DataFrame(), threshold
    counts = inst.groupby(["case_id", "activity"]).size().unstack(fill_value=0)
    is_slow = counts.index.isin(slow_ids)
    slow, rest = counts[is_slow], counts[~is_slow]
    comp = pd.DataFrame(
        {
            "in_slow_cases": (slow > 0).mean(),
            "in_other_cases": (rest > 0).mean(),
            "avg_runs_slow": slow.mean(),
            "avg_runs_other": rest.mean(),
        }
    )
    comp["extra_runs_in_slow"] = comp["avg_runs_slow"] - comp["avg_runs_other"]
    comp["runs_ratio"] = comp["avg_runs_slow"] / comp["avg_runs_other"].replace(0, np.nan)
    comp = comp.sort_values("extra_runs_in_slow", ascending=False)

    slow_variants = (
        cases.loc[slow_ids, "variant"].value_counts().head(5).rename_axis("variant").reset_index(name="slow_cases")
    )
    slow_variants["path"] = slow_variants["variant"].map(lambda t: " → ".join(t))
    return comp, slow_variants, threshold


# --------------------------------------------------------------------------- rework


def rework_table(inst: pd.DataFrame, n_cases: int) -> pd.DataFrame:
    """Which steps are repeated inside the same case, and what the repeats cost."""
    rep = inst[inst["occurrence"] >= 2]
    if rep.empty:
        return pd.DataFrame(
            columns=["cases_repeating", "share_of_cases", "extra_runs", "rework_hours", "avg_extra_runs_per_repeating_case"]
        )
    g = rep.groupby("activity")
    t = pd.DataFrame(
        {
            "cases_repeating": g["case_id"].nunique(),
            "extra_runs": g.size(),
            "rework_hours": g["wait_h"].sum() + g["work_h"].sum(),
        }
    )
    t["share_of_cases"] = t["cases_repeating"] / max(n_cases, 1)
    t["avg_extra_runs_per_repeating_case"] = t["extra_runs"] / t["cases_repeating"]
    return t.sort_values("rework_hours", ascending=False)


def loop_patterns(inst: pd.DataFrame, top: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Immediate repeats (A → A) and ping-pong returns (A → B → A)."""
    g = inst.groupby("case_id", sort=False)["activity"]
    a1 = g.shift(-1)
    a2 = g.shift(-2)
    a0 = inst["activity"]
    self_mask = a0 == a1
    self_loops = (
        a0[self_mask].value_counts().head(top).rename_axis("step").reset_index(name="immediate_repeats")
    )
    ping_mask = (a0 == a2) & a1.notna() & (a1 != a0)
    ping = (
        pd.DataFrame({"from": a0[ping_mask], "via": a1[ping_mask]})
        .value_counts()
        .head(top)
        .rename("returns")
        .reset_index()
    )
    return self_loops, ping
