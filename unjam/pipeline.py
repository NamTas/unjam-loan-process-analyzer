"""One call that runs the whole heavy analysis, plus the 'checks' that prove the numbers add up."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .analysis import (
    activity_metrics, duration_stats, edge_table, loop_patterns, rework_table,
    slow_case_analysis, start_end_counts, variant_table,
)
from .decisions import UNKNOWN_OUTCOME, assign_outcomes, auto_outcome_map, outcome_summary
from .loader import LogFormatError, build_cases, prepare_instances


@dataclass
class Analysis:
    name: str
    quality: dict
    inst_stats: dict
    inst: pd.DataFrame
    cases: pd.DataFrame
    metrics: pd.DataFrame
    edges: pd.DataFrame
    starts: pd.Series
    ends: pd.Series
    variants: pd.DataFrame
    rework: pd.DataFrame
    outcome_map: dict
    outcomes: pd.DataFrame
    durations: dict


def analyse(events: pd.DataFrame, quality: dict, name: str = "event log") -> Analysis:
    inst, stats = prepare_instances(events)
    cases = build_cases(inst)
    if cases.empty:
        raise LogFormatError("No cases found.")
    n = len(cases)
    metrics = activity_metrics(inst, n)
    edges = edge_table(inst)
    starts, ends = start_end_counts(inst)
    variants = variant_table(cases)
    omap = auto_outcome_map(metrics.index)
    cases["outcome"] = assign_outcomes(inst, omap).reindex(cases.index).fillna(UNKNOWN_OUTCOME)
    return Analysis(
        name=name, quality=quality, inst_stats=stats, inst=inst, cases=cases, metrics=metrics,
        edges=edges, starts=starts, ends=ends, variants=variants, rework=rework_table(inst, n),
        outcome_map=omap, outcomes=outcome_summary(cases), durations=duration_stats(cases),
    )


def reassign_outcomes(a: Analysis, outcome_map: dict) -> Analysis:
    """Return a copy of the analysis with a user-chosen outcome mapping."""
    cases = a.cases.copy()
    cases["outcome"] = assign_outcomes(a.inst, outcome_map).reindex(cases.index).fillna(UNKNOWN_OUTCOME)
    return Analysis(**{**a.__dict__, "cases": cases, "outcome_map": outcome_map, "outcomes": outcome_summary(cases)})


# --------------------------------------------------------------------------- checks (Evaluation tab)


def run_checks(a: Analysis) -> list[dict]:
    """Self-checks that make the numbers trustworthy. Each row: check, result, detail, passed."""
    rows = []
    n_cases, n_inst = len(a.cases), len(a.inst)

    # 1. Top-10 paths coverage
    top10 = float(a.variants["cum_share"].iloc[min(9, len(a.variants) - 1)])
    rows.append({"check": "Top 10 paths cover cases", "result": f"{top10 * 100:.1f}% of cases",
                 "detail": f"{len(a.variants):,} distinct paths in total", "passed": True})

    # 2. Map reconciliation: edges + starts + ends must add up
    edge_sum = int(a.edges["count"].sum())
    ok = edge_sum == n_inst - n_cases and int(a.starts.sum()) == n_cases and int(a.ends.sum()) == n_cases
    rows.append({"check": "Process map adds up", "result": "OK" if ok else "MISMATCH",
                 "detail": f"transitions {edge_sum:,} = steps {n_inst:,} - cases {n_cases:,}; "
                           f"starts {int(a.starts.sum()):,}, ends {int(a.ends.sum()):,}",
                 "passed": ok})

    # 3. Raw events vs step instances
    ign = sum(a.inst_stats["ignored_lifecycle"].values())
    raw = a.inst_stats["events_in"]
    merged = raw - ign - n_inst - a.inst_stats["unmatched_starts"]
    ok = merged >= 0
    rows.append({"check": "Raw events reconcile with steps", "result": "OK" if ok else "MISMATCH",
                 "detail": f"{raw:,} raw events = {n_inst:,} steps + {merged:,} merged START events "
                           f"+ {ign:,} ignored lifecycle events + {a.inst_stats['unmatched_starts']:,} unmatched START",
                 "passed": ok})

    # 4. Median vs p90 agreement on the slowest steps
    m = a.metrics[a.metrics["count"] >= max(5, 0.001 * n_inst)]
    if len(m) >= 3:
        k = min(5, len(m))
        by_med = set(m.sort_values("median_wait_h", ascending=False).head(k).index)
        by_p90 = set(m.sort_values("p90_wait_h", ascending=False).head(k).index)
        overlap = len(by_med & by_p90)
        rho = m["median_wait_h"].rank().corr(m["p90_wait_h"].rank())
        rows.append({"check": "Bottlenecks: median vs 90th percentile",
                     "result": f"{overlap} of top {k} steps agree; rank correlation {rho:.2f}",
                     "detail": "Two different metrics should point at similar steps. Disagreement means a few extreme cases drive the p90.",
                     "passed": overlap >= max(1, k // 2)})

    # 5. Waiting is never negative and always inside the case duration
    neg = int((a.inst["wait_h"].dropna() < 0).sum())
    over = float(a.inst.groupby("case_id")["wait_h"].sum().reindex(a.cases.index).fillna(0).sub(a.cases["duration_h"]).gt(1e-6).mean())
    rows.append({"check": "Waiting time is consistent", "result": f"{neg} negative waits; {over * 100:.1f}% of cases wait longer than they last",
                 "detail": "Wait is measured as real gaps on the case timeline, so both numbers must be 0.", "passed": neg == 0 and over == 0})

    # 6. Outcomes
    unknown = float((a.cases["outcome"] == UNKNOWN_OUTCOME).mean())
    rows.append({"check": "Outcome coverage", "result": f"{(1 - unknown) * 100:.1f}% of cases have a final outcome",
                 "detail": "Cases without an approved/declined/cancelled step are shown as 'No final outcome' (often still open at the end of the log).",
                 "passed": True})
    return rows
