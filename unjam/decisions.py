"""Outcomes, automation scoring and the to-be estimate.

The rules are deliberately simple and written out in docs/FSD.md, so they can be explained
to a loan officer or an operations manager without any machine learning.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

UNKNOWN_OUTCOME = "No final outcome"

# --------------------------------------------------------------------------- outcomes

DEFAULT_OUTCOME_KEYWORDS = {"Approved": "APPROVED", "Declined": "DECLINED", "Cancelled": "CANCELLED"}


def auto_outcome_map(activities, keywords: dict | None = None) -> dict[str, list[str]]:
    """Find which activities mean 'approved / declined / cancelled'.

    Prefers the application-level step 'A_<KEYWORD>' when it exists (as in BPI Challenge 2012),
    otherwise every activity whose name contains the keyword.
    """
    keywords = keywords or DEFAULT_OUTCOME_KEYWORDS
    acts = list(activities)
    result: dict[str, list[str]] = {}
    for label, kw in keywords.items():
        exact = [a for a in acts if a.upper() == f"A_{kw}"]
        found = exact or [a for a in acts if kw in a.upper()]
        if found:
            result[label] = found
    return result


def assign_outcomes(inst: pd.DataFrame, outcome_map: dict[str, list[str]]) -> pd.Series:
    """Case outcome = label of the last outcome step in the case (else 'No final outcome')."""
    lookup = {a: label for label, acts in outcome_map.items() for a in acts}
    if not lookup:
        return pd.Series(UNKNOWN_OUTCOME, index=inst["case_id"].unique(), name="outcome")
    hit = inst[inst["activity"].isin(lookup)]
    last = hit.groupby("case_id", sort=False).tail(1)
    out = pd.Series(UNKNOWN_OUTCOME, index=inst["case_id"].unique(), name="outcome")
    out.loc[last["case_id"].values] = last["activity"].map(lookup).values
    return out


def outcome_summary(cases: pd.DataFrame) -> pd.DataFrame:
    g = cases.groupby("outcome")
    t = pd.DataFrame(
        {
            "cases": g.size(),
            "median_duration_h": g["duration_h"].median(),
            "p90_duration_h": g["duration_h"].quantile(0.9),
            "avg_steps": g["n_steps"].mean(),
        }
    )
    t["share"] = t["cases"] / len(cases)
    return t.sort_values("cases", ascending=False)


def stuck_points(inst: pd.DataFrame, cases: pd.DataFrame, outcome_map: dict, label: str, top: int = 8) -> pd.DataFrame:
    """Where do cases of a given outcome 'sit' just before they end?

    For a real outcome (e.g. Cancelled) = the step right before the outcome step.
    For 'No final outcome' = the last step the case reached.
    """
    ids = cases.index[cases["outcome"] == label]
    sub = inst[inst["case_id"].isin(ids)]
    if sub.empty:
        return pd.DataFrame(columns=["step_before_end", "cases", "share", "median_wait_before_h"])
    if label == UNKNOWN_OUTCOME:
        rows = sub.groupby("case_id", sort=False).tail(1)
        key_col, wait = "activity", rows["wait_h"]
    else:
        out_acts = set(outcome_map.get(label, []))
        rows = sub[sub["activity"].isin(out_acts)].groupby("case_id", sort=False).tail(1)
        key_col, wait = "prev_activity", rows["wait_h"]
    rows = rows.assign(_wait=wait.values)
    g = rows.groupby(key_col)
    t = pd.DataFrame({"cases": g.size(), "median_wait_before_h": g["_wait"].median()})
    t.index.name = "step_before_end"
    t["share"] = t["cases"] / len(ids)
    return t.sort_values("cases", ascending=False).head(top).reset_index()


# --------------------------------------------------------------------------- automation scoring


@dataclass
class AutomationConfig:
    min_case_share: float = 0.30   # step is touched by at least this share of cases
    min_wait_h: float = 1.0        # median wait at least this long (otherwise not worth it)
    max_spread: float = 8.0        # p90 / median wait; above this, timing is too unpredictable
    decision_keywords: tuple = (
        "APPROVED", "DECLINED", "REJECT", "CANCEL", "ACCEPT", "DECISION", "DENY", "ASSESS", "SIGN",
    )


AUTOMATE = "Automation candidate"
HUMAN = "Needs human judgement"
MONITOR = "Monitor"


def score_activities(metrics: pd.DataFrame, cfg: AutomationConfig | None = None) -> pd.DataFrame:
    """Score every step: volume x repetition x waiting time, then classify with explicit rules."""
    cfg = cfg or AutomationConfig()
    m = metrics.copy()
    vol_n = m["count"] / m["count"].max()
    rep = 1.0 + m["rework_rate"]
    rep_n = rep / rep.max()
    wait_max = m["median_wait_h"].max()
    wait_n = m["median_wait_h"] / wait_max if wait_max > 0 else m["median_wait_h"] * 0.0
    m["score"] = (100.0 * vol_n * rep_n * wait_n).round(2)
    m["spread"] = np.where(m["median_wait_h"] > 0, m["p90_wait_h"] / m["median_wait_h"].replace(0, np.nan), np.nan)

    classes, reasons = [], []
    for act, r in m.iterrows():
        is_decision = any(k in act.upper() for k in cfg.decision_keywords)
        waits = r["median_wait_h"] >= cfg.min_wait_h
        predictable = (not np.isnan(r["spread"])) and r["spread"] <= cfg.max_spread
        busy = r["case_share"] >= cfg.min_case_share
        facts = (
            f"in {r['case_share'] * 100:.0f}% of cases, median wait {r['median_wait_h']:.1f} h, "
            f"p90/median {('%.1f' % r['spread']) if not np.isnan(r['spread']) else 'n/a'}, "
            f"repeated in {r['rework_rate'] * 100:.0f}% of its cases"
        )
        if is_decision:
            cls, why = HUMAN, "name looks like a decision step; " + facts
        elif busy and waits and predictable:
            cls, why = AUTOMATE, "busy, slow and predictable; " + facts
        elif waits and not predictable:
            cls, why = HUMAN, "slow but timing varies a lot (case specific); " + facts
        else:
            cls, why = MONITOR, "low volume or little waiting; " + facts
        classes.append(cls)
        reasons.append(why)
    m["class"] = classes
    m["reason"] = reasons
    return m.sort_values("score", ascending=False)


# --------------------------------------------------------------------------- to-be estimate


@dataclass
class Assumptions:
    wait_reduction: float = 0.5   # automated steps wait this share less (0.5 = half)


@dataclass
class Change:
    activity: str
    kind: str  # "automate" or "rework"

    @property
    def label(self) -> str:
        return f"{'Automate' if self.kind == 'automate' else 'Cut rework in'} {self.activity}"


def row_savings(inst: pd.DataFrame, changes: list[Change], a: Assumptions) -> pd.Series:
    """Hours saved per case for a set of changes. A step run is never counted twice."""
    saved = np.zeros(len(inst))
    wait = inst["wait_h"].fillna(0.0).to_numpy()
    work = inst["work_h"].fillna(0.0).to_numpy()
    repeat = (inst["occurrence"] >= 2).to_numpy()
    acts = inst["activity"].to_numpy()
    for ch in changes:
        mask = acts == ch.activity
        if ch.kind == "automate":
            val = np.where(mask, wait * a.wait_reduction, 0.0)
        else:  # remove repeated runs completely (their waiting and working time)
            val = np.where(mask & repeat, wait + work, 0.0)
        saved = np.maximum(saved, val)
    return pd.Series(saved, index=inst.index).groupby(inst["case_id"].values).sum()


def estimate(cases: pd.DataFrame, saved_per_case: pd.Series) -> dict:
    before = cases["duration_h"]
    saved = saved_per_case.reindex(before.index).fillna(0.0)
    after = (before - saved).clip(lower=0.0)
    return {
        "median_before_h": float(before.median()),
        "median_after_h": float(after.median()),
        "p90_before_h": float(before.quantile(0.9)),
        "p90_after_h": float(after.quantile(0.9)),
        "mean_before_h": float(before.mean()),
        "mean_after_h": float(after.mean()),
        "cases_affected_share": float((saved > 0).mean()),
        "total_saved_h": float(saved.sum()),
    }


def rank_improvements(inst: pd.DataFrame, cases: pd.DataFrame, scored: pd.DataFrame,
                      rework: pd.DataFrame, a: Assumptions, top: int = 10) -> pd.DataFrame:
    """Try every sensible single change and rank by hours saved (assumption-based)."""
    options = [Change(act, "automate") for act in scored.index[scored["class"] == AUTOMATE]]
    options += [Change(act, "rework") for act in rework.index if rework.loc[act, "rework_hours"] > 0]
    total_wait = float(inst["wait_h"].fillna(0).sum())
    rows = []
    for ch in options:
        saved = row_savings(inst, [ch], a)
        est = estimate(cases, saved)
        rows.append(
            {
                "change": ch.label,
                "activity": ch.activity,
                "kind": ch.kind,
                "saved_total_h": est["total_saved_h"],
                "share_of_all_waiting": est["total_saved_h"] / total_wait if total_wait else 0.0,
                "median_case_saving_h": est["median_before_h"] - est["median_after_h"],
                "cases_affected_share": est["cases_affected_share"],
            }
        )
    if not rows:
        return pd.DataFrame(columns=["change", "activity", "kind", "saved_total_h", "share_of_all_waiting",
                                     "median_case_saving_h", "cases_affected_share"])
    return pd.DataFrame(rows).sort_values("saved_total_h", ascending=False).head(top).reset_index(drop=True)


def changes_from_table(table: pd.DataFrame, n: int = 3) -> list[Change]:
    return [Change(r.activity, r.kind) for r in table.head(n).itertuples(index=False)]
