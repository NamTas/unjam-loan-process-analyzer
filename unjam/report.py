"""Facts -> findings. Facts are computed by code; text is written from facts only."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import llm
from .analysis import slow_case_analysis
from .config import data_note
from .decisions import (
    AUTOMATE, HUMAN, UNKNOWN_OUTCOME, Assumptions, AutomationConfig, changes_from_table,
    estimate, rank_improvements, row_savings, score_activities, stuck_points,
)
from .flow import build_flow, to_mermaid
from .pipeline import Analysis, run_checks
from .utils import fmt_hours, fmt_int, fmt_pct, md_table

SYSTEM_PROMPT = (
    "You are a business analyst assistant in a bank's operations team. "
    "Use ONLY the facts given in the user message. Copy numbers exactly as written; never calculate, "
    "round, convert units or invent numbers. If something is not in the facts, say it is not available. "
    "State once that the data is a proxy process if the facts say so. Write plain English for a manager."
)

NARRATIVE_PROMPT = """FACTS (JSON):
{facts}

Write markdown with exactly these sections:
## Key findings
5 short bullets, each quoting at least one number from the facts.
## Recommendations
3 numbered recommendations. Each must name the step, the evidence number, and what to change.
## FSD draft: automation requirements
3 to 5 requirements written as 'FR-A1 ...' with one acceptance criterion each.
## Assumptions and limits
3 bullets: proxy data, estimates are assumption-based, human validation needed.
"""

QA_PROMPT = """Answer the question using ONLY the snippets below. If the snippets do not contain the answer,
say 'This is not in the analysis results.' Copy numbers exactly. Keep it under 120 words.

SNIPPETS:
{snippets}

QUESTION: {question}"""


# --------------------------------------------------------------------------- facts


def build_facts(a: Analysis, cfg: AutomationConfig, assume: Assumptions, top_changes: int = 3) -> dict:
    scored = score_activities(a.metrics, cfg)
    n_cases = len(a.cases)
    d = a.durations
    q = a.quality

    def step_row(act, r):
        return {
            "step": act,
            "cases_touching_it": fmt_pct(r["case_share"], 0),
            "median_wait": fmt_hours(r["median_wait_h"]),
            "p90_wait": fmt_hours(r["p90_wait_h"]),
            "total_wait": fmt_hours(r["total_wait_h"]),
        }

    big = a.metrics[a.metrics["count"] >= max(5, 0.01 * n_cases)]
    by_median = [step_row(k, r) for k, r in big.sort_values("median_wait_h", ascending=False).head(5).iterrows()]
    by_total = [step_row(k, r) for k, r in a.metrics.sort_values("total_wait_h", ascending=False).head(5).iterrows()]

    rework = [
        {"step": k, "share_of_cases_repeating": fmt_pct(r["share_of_cases"]),
         "extra_runs": fmt_int(r["extra_runs"]), "hours_spent_on_repeats": fmt_hours(r["rework_hours"])}
        for k, r in a.rework.head(5).iterrows()
    ]

    outcomes = [
        {"outcome": k, "share_of_cases": fmt_pct(r["share"]), "cases": fmt_int(r["cases"]),
         "median_duration": fmt_hours(r["median_duration_h"]), "p90_duration": fmt_hours(r["p90_duration_h"])}
        for k, r in a.outcomes.iterrows()
    ]
    stuck = {}
    for label in [k for k in a.outcomes.index if k in ("Cancelled", "Declined", UNKNOWN_OUTCOME)][:3]:
        st = stuck_points(a.inst, a.cases, a.outcome_map, label, top=3)
        stuck[label] = [
            {"step_before_end": r.step_before_end, "share_of_those_cases": fmt_pct(r.share),
             "median_wait_before": fmt_hours(r.median_wait_before_h)} for r in st.itertuples(index=False)
        ]

    candidates = [
        {"step": k, "score": f"{r['score']:.1f}", "why": r["reason"]}
        for k, r in scored[scored["class"] == AUTOMATE].head(5).iterrows()
    ]
    human = [k for k in scored[scored["class"] == HUMAN].sort_values("median_wait_h", ascending=False).head(5).index]

    table = rank_improvements(a.inst, a.cases, scored, a.rework, assume)
    chosen = changes_from_table(table, top_changes)
    est = estimate(a.cases, row_savings(a.inst, chosen, assume)) if chosen else None
    improvements = [
        {"change": r.change, "estimated_hours_saved_in_total": fmt_hours(r.saved_total_h),
         "share_of_all_waiting_removed": fmt_pct(r.share_of_all_waiting),
         "median_case_saving": fmt_hours(r.median_case_saving_h)}
        for r in table.head(top_changes).itertuples(index=False)
    ]

    comp, _, slow_thr = slow_case_analysis(a.inst, a.cases)
    slow_pattern = []
    if not comp.empty:
        for k, r in comp.head(3).iterrows():
            slow_pattern.append({"step": k, "runs_per_slow_case": f"{r['avg_runs_slow']:.1f}",
                                 "runs_per_other_case": f"{r['avg_runs_other']:.1f}"})

    facts = {
        "dataset": {
            "name": a.name,
            "note": data_note(a.name),
            "cases": fmt_int(n_cases),
            "raw_events": fmt_int(a.inst_stats["events_in"]),
            "steps_after_merging_start_and_complete": fmt_int(len(a.inst)),
            "distinct_steps": fmt_int(len(a.metrics)),
            "distinct_paths": fmt_int(len(a.variants)),
            "first_event": str(q["first_event"])[:10],
            "last_event": str(q["last_event"])[:10],
        },
        "case_duration": {
            "median": fmt_hours(d["median_h"]), "p90": fmt_hours(d["p90_h"]), "mean": fmt_hours(d["mean_h"]),
            "slowest_10_percent_start_at": fmt_hours(slow_thr),
            "top_10_paths_cover": fmt_pct(a.variants["cum_share"].iloc[min(9, len(a.variants) - 1)]),
        },
        "slowest_steps_by_median_wait": by_median,
        "steps_with_most_total_waiting": by_total,
        "rework": rework,
        "outcomes": outcomes,
        "where_cases_get_stuck": stuck,
        "slow_case_pattern": slow_pattern,
        "automation_candidates": candidates,
        "steps_needing_human_judgement": human,
        "top_improvements": improvements,
        "to_be_estimate": (
            {
                "assumption": f"automated steps wait {fmt_pct(assume.wait_reduction, 0)} less; repeated runs removed fully",
                "median_case_duration_before": fmt_hours(est["median_before_h"]),
                "median_case_duration_after": fmt_hours(est["median_after_h"]),
                "p90_before": fmt_hours(est["p90_before_h"]),
                "p90_after": fmt_hours(est["p90_after_h"]),
                "cases_affected": fmt_pct(est["cases_affected_share"]),
            } if est else {"assumption": "no automation candidate found with the current thresholds"}
        ),
    }
    return facts


def facts_text(facts: dict) -> str:
    return json.dumps(facts, indent=1, ensure_ascii=False)


# --------------------------------------------------------------------------- narrative


def offline_narrative(facts: dict) -> str:
    """Rule-based findings. Used when no API key is set, and as the safe fallback."""
    ds, dur = facts["dataset"], facts["case_duration"]
    out = ["## Key findings",
           f"- {ds['cases']} cases were analysed ({ds['first_event']} to {ds['last_event']}). "
           f"Median case duration is {dur['median']}; the slowest 10% take {dur['slowest_10_percent_start_at']} or more."]
    if facts["slowest_steps_by_median_wait"]:
        s = facts["slowest_steps_by_median_wait"][0]
        out.append(f"- Longest typical wait: **{s['step']}** (median {s['median_wait']}, p90 {s['p90_wait']}).")
    if facts["steps_with_most_total_waiting"]:
        s = facts["steps_with_most_total_waiting"][0]
        out.append(f"- Most waiting in total: **{s['step']}** ({s['total_wait']} summed over all cases).")
    if facts["rework"]:
        r = facts["rework"][0]
        out.append(f"- Most expensive repeat: **{r['step']}** is repeated in {r['share_of_cases_repeating']} of cases "
                   f"({r['hours_spent_on_repeats']} spent on repeats).")
    oc = [o for o in facts["outcomes"] if o["outcome"] != UNKNOWN_OUTCOME]
    if oc:
        out.append("- Outcomes: " + ", ".join(f"{o['outcome']} {o['share_of_cases']}" for o in oc) + ".")
    out.append(f"- The top 10 paths cover {dur['top_10_paths_cover']} of cases, so the process is "
               + ("fairly standard." if float(dur["top_10_paths_cover"].rstrip("%")) >= 50 else "highly varied."))

    out += ["", "## Recommendations"]
    if facts["top_improvements"]:
        for i, imp in enumerate(facts["top_improvements"], 1):
            out.append(f"{i}. **{imp['change']}**: estimated {imp['estimated_hours_saved_in_total']} saved in total "
                       f"({imp['share_of_all_waiting_removed']} of all waiting); median case saves {imp['median_case_saving']}.")
    else:
        out.append("1. No step passed the automation rules with the current thresholds; lower the thresholds or review rework first.")

    out += ["", "## FSD draft: automation requirements"]
    for i, c in enumerate(facts["automation_candidates"][:4], 1):
        out.append(f"- FR-A{i}: The system shall automatically process or route **{c['step']}** using explicit rules. "
                   f"Acceptance: median waiting before this step is lower than today's baseline; every automatic decision is logged and can be overridden by an officer.")
    if not facts["automation_candidates"]:
        out.append("- No automation requirement can be drafted from the current results.")

    out += ["", "## Assumptions and limits",
            f"- {ds['note']}",
            "- Savings are estimates that depend on the stated assumption; they are not measured results.",
            "- A process owner must validate every recommendation before anything is automated."]
    return "\n".join(out)


def make_narrative(facts: dict, use_llm: bool) -> tuple[str, dict]:
    """Returns (markdown, info). info: source, warnings (unverified numbers), error."""
    info = {"source": "rules (offline)", "unverified_numbers": [], "error": None}
    if use_llm and llm.is_configured():
        try:
            text = llm.generate(NARRATIVE_PROMPT.format(facts=facts_text(facts)), system=SYSTEM_PROMPT)
            info["source"] = "Gemini (explains the computed facts)"
            info["unverified_numbers"] = llm.unverified_numbers(text, facts_text(facts))
            return text, info
        except llm.LLMError as exc:
            info["error"] = str(exc)
    return offline_narrative(facts), info


def answer_question(question: str, facts: dict, use_llm: bool) -> tuple[str, list[str], dict]:
    """'Ask the report': retrieve the closest facts, then (optionally) let the LLM phrase the answer."""
    hits = llm.retrieve(question, llm.facts_to_chunks(facts), k=4)
    snippets = [c for _, c in hits]
    info = {"source": "retrieved facts only", "unverified_numbers": [], "error": None}
    if not snippets:
        return "This is not in the analysis results.", [], info
    if use_llm and llm.is_configured():
        try:
            text = llm.generate(QA_PROMPT.format(snippets="\n".join(f"- {s}" for s in snippets), question=question),
                                system=SYSTEM_PROMPT)
            info["source"] = "Gemini (answers from the retrieved facts)"
            info["unverified_numbers"] = llm.unverified_numbers(text, "\n".join(snippets))
            return text, snippets, info
        except llm.LLMError as exc:
            info["error"] = str(exc)
    return "Closest results in the analysis:\n" + "\n".join(f"- {s}" for s in snippets), snippets, info


# --------------------------------------------------------------------------- markdown report


def _rows(df: pd.DataFrame, cols: dict, n: int = 10) -> list[dict]:
    out = []
    for idx, r in df.head(n).iterrows():
        row = {"Step": idx}
        for title, (col, fn) in cols.items():
            row[title] = fn(r[col])
        out.append(row)
    return out


def report_markdown(a: Analysis, cfg: AutomationConfig, assume: Assumptions, facts: dict, narrative: str, info: dict) -> str:
    scored = score_activities(a.metrics, cfg)
    ds = facts["dataset"]
    lines = [
        f"# UnJam report: {a.name}", "",
        f"_{ds['note']}_", "",
        f"**Cases:** {ds['cases']}  |  **Steps:** {ds['steps_after_merging_start_and_complete']}  |  "
        f"**Period:** {ds['first_event']} to {ds['last_event']}  |  **Median case duration:** {facts['case_duration']['median']}",
        "", f"> Findings below were written by: {info['source']}. Numbers come from the analysis code.",
    ]
    if info.get("unverified_numbers"):
        lines.append(f"> WARNING: these numbers in the AI text are not in the analysis facts and must be checked: "
                     + ", ".join(info["unverified_numbers"]))
    lines += ["", narrative, "", "## Tables", "", "### Slowest steps (waiting time)", "",
              md_table(_rows(a.metrics[a.metrics["count"] >= 5].sort_values("median_wait_h", ascending=False),
                             {"Cases %": ("case_share", lambda x: fmt_pct(x, 0)),
                              "Median wait": ("median_wait_h", fmt_hours), "P90 wait": ("p90_wait_h", fmt_hours),
                              "Total wait": ("total_wait_h", fmt_hours)})),
              "", "### Rework", "",
              md_table(_rows(a.rework, {"Cases repeating": ("share_of_cases", fmt_pct),
                                        "Extra runs": ("extra_runs", fmt_int), "Hours on repeats": ("rework_hours", fmt_hours)})),
              "", "### Outcomes", "",
              md_table(_rows(a.outcomes, {"Cases": ("cases", fmt_int), "Share": ("share", fmt_pct),
                                          "Median duration": ("median_duration_h", fmt_hours),
                                          "P90 duration": ("p90_duration_h", fmt_hours)})),
              "", "### Automation opportunity scores", "",
              md_table(_rows(scored, {"Score": ("score", lambda x: f"{x:.1f}"), "Class": ("class", str),
                                      "Why": ("reason", str)}, n=12)),
              "", "### Self-checks", "",
              md_table([{"Check": c["check"], "Result": c["result"], "Passed": "yes" if c["passed"] else "NO"}
                        for c in run_checks(a)]),
              "", f"_Assumption used for the to-be estimate: automated steps wait {fmt_pct(assume.wait_reduction, 0)} less._", ""]
    return "\n".join(lines)


def export_all(a: Analysis, cfg: AutomationConfig, assume: Assumptions, outdir: Path, use_llm: bool = False) -> dict:
    """Write report.md, facts.json, as_is.mmd, to_be.mmd and CSV tables to `outdir`."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    facts = build_facts(a, cfg, assume)
    narrative, info = make_narrative(facts, use_llm)
    (outdir / "report.md").write_text(report_markdown(a, cfg, assume, facts, narrative, info), encoding="utf-8")
    (outdir / "facts.json").write_text(facts_text(facts), encoding="utf-8")

    scored = score_activities(a.metrics, cfg)
    flow = build_flow(a.metrics, a.edges, a.starts, a.ends, len(a.cases))
    (outdir / "as_is.mmd").write_text(to_mermaid(flow, title="As-is process (discovered from the log)"), encoding="utf-8")
    table = rank_improvements(a.inst, a.cases, scored, a.rework, assume)
    chosen = {c.activity for c in changes_from_table(table, 3) if c.kind == "automate"}
    (outdir / "to_be.mmd").write_text(to_mermaid(flow, highlight=chosen, title="To-be: top automation steps highlighted"),
                                      encoding="utf-8")
    a.metrics.to_csv(outdir / "step_metrics.csv")
    scored.to_csv(outdir / "automation_scores.csv")
    a.rework.to_csv(outdir / "rework.csv")
    a.outcomes.to_csv(outdir / "outcomes.csv")
    table.to_csv(outdir / "improvements.csv", index=False)
    return {"facts": facts, "narrative_source": info["source"], "files": sorted(p.name for p in outdir.iterdir())}
