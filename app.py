"""UnJam: Streamlit app.  Run with:  streamlit run app.py"""
from __future__ import annotations

import hashlib

import pandas as pd
import plotly.express as px
import streamlit as st

from unjam import APP_NAME, TAGLINE, llm
from unjam.analysis import loop_patterns, slow_case_analysis
from unjam.config import DATA_DIR, list_local_logs
from unjam.decisions import (
    AUTOMATE, HUMAN, MONITOR, UNKNOWN_OUTCOME, Assumptions, AutomationConfig, Change,
    auto_outcome_map, estimate, rank_improvements, row_savings, score_activities, stuck_points,
)
from unjam.flow import build_flow, to_dot, to_mermaid
from unjam.loader import LogFormatError, STANDARD_ROLES, guess_columns, read_raw, standardize
from unjam.pipeline import analyse, reassign_outcomes, run_checks
from unjam.report import answer_question, build_facts, facts_text, make_narrative, report_markdown
from unjam.ui import apply_style, page_header
from unjam.utils import dataset_title, fmt_hours, fmt_int, fmt_pct

st.set_page_config(page_title=f"{APP_NAME} · loan process analyser", page_icon="🧶", layout="wide")
apply_style()

DATASET_URL = "https://data.4tu.nl/articles/dataset/BPI_Challenge_2012/12689204/1"


# =========================================================================== cached heavy steps


@st.cache_resource(show_spinner="Reading the file…", max_entries=2)
def cached_raw(key: str, _src, name: str):
    return read_raw(_src, name)


@st.cache_resource(show_spinner="Cleaning the log…", max_entries=2)
def cached_events(key: str, _raw: pd.DataFrame, mapping_items: tuple):
    return standardize(_raw, dict(mapping_items))


@st.cache_resource(show_spinner="Analysing the process…", max_entries=2)
def cached_analysis(key: str, _events: pd.DataFrame, _quality: dict, name: str):
    return analyse(_events, _quality, name)


@st.cache_data(show_spinner="Scoring automation opportunities…", max_entries=8)
def cached_scoring(key: str, _a, min_share: float, min_wait: float, max_spread: float, reduction: float):
    cfg = AutomationConfig(min_case_share=min_share, min_wait_h=min_wait, max_spread=max_spread)
    scored = score_activities(_a.metrics, cfg)
    table = rank_improvements(_a.inst, _a.cases, scored, _a.rework, Assumptions(reduction))
    return scored, table


@st.cache_data(show_spinner="Collecting the facts…", max_entries=8)
def cached_facts(key: str, _a, min_share: float, min_wait: float, max_spread: float, reduction: float):
    cfg = AutomationConfig(min_case_share=min_share, min_wait_h=min_wait, max_spread=max_spread)
    return build_facts(_a, cfg, Assumptions(reduction))


# =========================================================================== small helpers


def show(df: pd.DataFrame, **kw):
    st.dataframe(df, hide_index=True, **kw)


def hours_df(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        out[c] = out[c].astype(float).round(1)
    return out


def file_key(prefix: str, data: bytes | str, extra: str = "") -> str:
    h = hashlib.md5(data if isinstance(data, bytes) else data.encode()).hexdigest()[:12]
    return f"{prefix}:{h}:{extra}"


def empty_state():
    page_header()
    st.info("No event log loaded yet. UnJam only analyses real logs, so there is nothing to show until you add one.")
    st.markdown(
        f"""
**Get started in 3 steps**

1. Download a real loan-process event log. The recommended one is **BPI Challenge 2012**
   (`BPI_Challenge_2012.xes.gz`, about 3 MB) from [4TU.ResearchData]({DATASET_URL}).
   Read the licence on that page first and cite the author if you publish results.
2. Put the file in this folder: `{DATA_DIR}`
3. Reload this page and pick the file in the sidebar. You can also upload a file directly in the sidebar.

Any other event log works too if it has a case id, an activity name and a timestamp (CSV or XES).
"""
    )


# =========================================================================== sidebar: data


def pick_source():
    st.sidebar.header("1 · Event log")
    local = list_local_logs()
    upload_label = "Upload a file…"
    choice = st.sidebar.selectbox("Source", [p.name for p in local] + [upload_label])
    if choice == upload_label:
        up = st.sidebar.file_uploader("XES, XES.GZ, CSV or ZIP", type=["xes", "gz", "csv", "zip"])
        if up is None:
            if not local:
                st.sidebar.caption(f"Or place a file in `{DATA_DIR}` and reload.")
            return None
        data = up.getvalue()
        return {"src": data, "name": up.name, "key": file_key("upload", data, up.name)}
    path = DATA_DIR / choice
    stat = path.stat()
    return {"src": str(path), "name": choice, "key": f"path:{path}:{stat.st_mtime_ns}:{stat.st_size}"}


def mapping_ui(raw: pd.DataFrame, kind: str) -> dict:
    if kind == "xes":
        return {r: r for r in STANDARD_ROLES}
    guess = guess_columns(raw.columns)
    required_missing = any(not guess[r] for r in ("case_id", "activity", "timestamp"))
    labels = {"case_id": "Case id *", "activity": "Activity *", "timestamp": "Timestamp *",
              "lifecycle": "Lifecycle (optional)", "resource": "Resource (optional)"}
    mapping = {}
    with st.sidebar.expander("Column mapping", expanded=required_missing):
        options = ["(none)"] + list(raw.columns)
        for role in STANDARD_ROLES:
            idx = options.index(guess[role]) if guess[role] in options else 0
            picked = st.selectbox(labels[role], options, index=idx, key=f"map_{role}")
            mapping[role] = None if picked == "(none)" else picked
    return mapping


# =========================================================================== tabs


def tab_overview(a, scored):
    d, q = a.durations, a.quality
    c = st.columns(5)
    c[0].metric("Cases", fmt_int(len(a.cases)))
    c[1].metric("Steps", fmt_int(len(a.inst)), help="After merging START and COMPLETE events of the same task")
    c[2].metric("Median case duration", fmt_hours(d["median_h"]))
    c[3].metric("Slowest 10% take at least", fmt_hours(d["p90_h"]))
    c[4].metric("Distinct paths", fmt_int(len(a.variants)))
    st.caption(f"Period: {str(q['first_event'])[:10]} to {str(q['last_event'])[:10]} · "
               f"{fmt_int(q['events'])} raw events · {fmt_int(len(a.metrics))} distinct steps")

    plot = a.cases[a.cases["duration_h"] <= a.cases["duration_h"].quantile(0.99)].copy()
    plot["days"] = plot["duration_h"] / 24
    fig = px.histogram(plot, x="days", nbins=60, labels={"days": "Case duration (days)"},
                       title="How long do cases take? (cases above the 99th percentile are cut off for readability)")
    fig.add_vline(x=d["median_h"] / 24, line_dash="dash", annotation_text="median")
    fig.add_vline(x=d["p90_h"] / 24, line_dash="dot", annotation_text="90th percentile")
    st.plotly_chart(fig)

    st.subheader("Most common paths")
    v = a.variants.head(10)[["rank", "cases", "share", "cum_share", "n_steps", "path"]].copy()
    v["share"] = (v["share"] * 100).round(1)
    v["cum_share"] = (v["cum_share"] * 100).round(1)
    show(v.rename(columns={"share": "share %", "cum_share": "cumulative %", "n_steps": "steps"}))
    with st.expander("Data quality and how steps were built"):
        st.write({k: v for k, v in q.items() if k not in ("first_event", "last_event")})
        st.write(a.inst_stats)


def tab_map(a):
    st.subheader("As-is process: what really happens")
    c = st.columns(4)
    max_nodes = c[0].slider("Max steps shown", 5, 40, 15)
    min_share = c[1].slider("Hide paths used by fewer than (% of cases)", 0.0, 20.0, 2.0, 0.5) / 100
    direction = c[2].radio("Direction", ["Top to bottom", "Left to right"], horizontal=True)
    edge_wait = c[3].checkbox("Show waiting time on arrows", value=False)
    flow = build_flow(a.metrics, a.edges, a.starts, a.ends, len(a.cases), max_nodes, min_share)
    dot = to_dot(flow, "TB" if direction.startswith("Top") else "LR", show_edge_wait=edge_wait)
    st.graphviz_chart(dot)
    st.caption(f"Colour = median waiting time before the step (darker = longer). Arrow width = number of times the "
               f"transition happens. The map shows {fmt_pct(flow.edge_coverage, 0)} of all transitions; "
               f"lower the filters to see more.")
    c1, c2 = st.columns(2)
    c1.download_button("Download as Mermaid (for docs)", to_mermaid(flow, title="As-is process"), "as_is.mmd")
    c2.download_button("Download as Graphviz DOT", dot, "as_is.dot")


def tab_bottlenecks(a):
    st.subheader("Where does time get lost?")
    rank_by = st.radio("Rank steps by", ["Total waiting time", "Median wait", "90th percentile wait"], horizontal=True)
    col = {"Total waiting time": "total_wait_h", "Median wait": "median_wait_h", "90th percentile wait": "p90_wait_h"}[rank_by]
    min_cases = st.number_input("Ignore steps that happen fewer times than", 1, 100000, max(5, int(0.005 * len(a.cases))))
    m = a.metrics[a.metrics["count"] >= min_cases].sort_values(col, ascending=False)
    top = m.head(10).reset_index()
    if top.empty:
        st.info("No step matches the filter.")
    else:
        fig = px.bar(top, x=col, y="activity", orientation="h", labels={col: "hours", "activity": ""})
        fig.update_layout(yaxis={"autorange": "reversed"})
        st.plotly_chart(fig)
    t = m.reset_index()[["activity", "count", "case_share", "median_wait_h", "p90_wait_h", "total_wait_h", "median_work_h"]].copy()
    t["case_share"] = (t["case_share"] * 100).round(0)
    show(hours_df(t, ["median_wait_h", "p90_wait_h", "total_wait_h", "median_work_h"]).rename(columns={
        "count": "times run", "case_share": "% of cases", "median_wait_h": "median wait (h)",
        "p90_wait_h": "p90 wait (h)", "total_wait_h": "total wait (h)", "median_work_h": "median work (h)"}))
    st.caption("Wait = gap between the end of the previous work in the case and the start of this step. "
               "Work = time between START and COMPLETE (0 if the log only records completions).")

    st.subheader("Slowest transitions")
    e = a.edges[a.edges["count"] >= min_cases].sort_values("median_wait_h", ascending=False).head(15)
    show(hours_df(e, ["median_wait_h", "p90_wait_h", "total_wait_h"]).rename(columns={
        "median_wait_h": "median wait (h)", "p90_wait_h": "p90 wait (h)", "total_wait_h": "total wait (h)"}))

    st.subheader("What do the slowest 10% of cases have in common?")
    comp, slow_variants, thr = slow_case_analysis(a.inst, a.cases)
    if comp.empty:
        st.info("Not enough cases to compare the slowest group.")
        return
    st.caption(f"Slow cases = duration of at least {fmt_hours(thr)}. Positive 'extra runs' means the step is repeated more often in slow cases.")
    c = comp.head(8).reset_index().rename(columns={"activity": "step"})
    c["in_slow_cases"] = (c["in_slow_cases"] * 100).round(0)
    c["in_other_cases"] = (c["in_other_cases"] * 100).round(0)
    show(c[["step", "in_slow_cases", "in_other_cases", "avg_runs_slow", "avg_runs_other", "extra_runs_in_slow"]].round(2).rename(columns={
        "in_slow_cases": "% of slow cases", "in_other_cases": "% of other cases"}))
    st.write("Most common paths among slow cases")
    show(slow_variants[["slow_cases", "path"]])


def tab_rework(a):
    st.subheader("Rework: steps that are repeated in the same case")
    if a.rework.empty:
        st.success("No step is repeated inside a case in this log.")
        return
    r = a.rework.reset_index().rename(columns={"activity": "step"})
    top = r.head(10)
    fig = px.bar(top, x="rework_hours", y="step", orientation="h", labels={"rework_hours": "hours spent on repeats", "step": ""})
    fig.update_layout(yaxis={"autorange": "reversed"})
    st.plotly_chart(fig)
    r["share_of_cases"] = (r["share_of_cases"] * 100).round(1)
    show(r.round(1).rename(columns={"share_of_cases": "% of cases repeating", "extra_runs": "extra runs",
                                    "rework_hours": "hours on repeats", "cases_repeating": "cases repeating",
                                    "avg_extra_runs_per_repeating_case": "extra runs per repeating case"}))
    self_loops, ping = loop_patterns(a.inst)
    c1, c2 = st.columns(2)
    c1.write("Immediate repeats (A → A)")
    with c1:
        show(self_loops)
    c2.write("Ping-pong returns (A → B → A)")
    with c2:
        show(ping)
    st.caption("Hours on repeats = waiting + working time of every run after the first one of the same step in a case.")


def tab_outcomes(a, omap):
    st.subheader("Outcomes and the paths that lead to them")
    if not omap:
        st.warning("No approved / declined / cancelled steps were found automatically. Pick them in the sidebar under 'Outcome steps'.")
    o = a.outcomes.reset_index()
    fig = px.bar(o, x="outcome", y="cases", color="outcome", labels={"outcome": "", "cases": "cases"})
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig)
    t = o.copy()
    t["share"] = (t["share"] * 100).round(1)
    show(hours_df(t, ["median_duration_h", "p90_duration_h", "avg_steps"]).rename(columns={
        "share": "% of cases", "median_duration_h": "median duration (h)", "p90_duration_h": "p90 duration (h)"}))
    label = st.selectbox("Look closer at", list(a.outcomes.index), index=min(1, len(a.outcomes) - 1))
    st.write(f"**Where do '{label}' cases sit just before they end?**"
             if label != UNKNOWN_OUTCOME else "**Where do cases without a final outcome stop?**")
    sp = stuck_points(a.inst, a.cases, a.outcome_map, label)
    if sp.empty:
        st.info("Nothing to show.")
    else:
        sp["share"] = (sp["share"] * 100).round(1)
        show(sp.round(1).rename(columns={"share": "% of these cases", "median_wait_before_h": "median wait before (h)"}))
    st.write("Most common paths for this outcome")
    paths = a.cases[a.cases["outcome"] == label]["variant"].value_counts().head(5)
    show(pd.DataFrame({"cases": paths.values, "path": [" → ".join(p) for p in paths.index]}))


def tab_automation(a, scored):
    st.subheader("Automation opportunities")
    st.markdown(
        "**Score = volume × repetition × waiting time** (each scaled 0 to 1, then × 100). "
        "A step is an **automation candidate** only if it is busy, slow *and* predictable, and is not a decision step. "
        "Change the thresholds in the sidebar and everything updates."
    )
    pick = st.multiselect("Show classes", [AUTOMATE, HUMAN, MONITOR], default=[AUTOMATE, HUMAN, MONITOR])
    s = scored[scored["class"].isin(pick)].reset_index()
    top = s.head(10)
    if not top.empty:
        fig = px.bar(top, x="score", y="activity", color="class", orientation="h", labels={"activity": ""})
        fig.update_layout(yaxis={"autorange": "reversed"})
        st.plotly_chart(fig)
    s["case_share"] = (s["case_share"] * 100).round(0)
    show(s[["activity", "class", "score", "case_share", "median_wait_h", "spread", "rework_rate", "reason"]].round(2).rename(
        columns={"case_share": "% of cases", "median_wait_h": "median wait (h)", "spread": "p90/median",
                 "rework_rate": "rework rate"}))
    st.caption("Human check required: these are rule-based suggestions from timing data only. "
               "A process owner must confirm that a step can really be automated (policy, risk, regulation).")


def tab_tobe(a, scored, table, reduction, key):
    st.subheader("To-be: what could the top improvements save?")
    if table.empty:
        st.info("No improvement found with the current thresholds. Lower the thresholds in the sidebar or check the rework tab.")
        return
    show_t = table.copy()
    show_t["share_of_all_waiting"] = (show_t["share_of_all_waiting"] * 100).round(1)
    show_t["cases_affected_share"] = (show_t["cases_affected_share"] * 100).round(0)
    show(hours_df(show_t, ["saved_total_h", "median_case_saving_h"]).drop(columns=["activity", "kind"]).rename(columns={
        "saved_total_h": "hours saved (all cases)", "share_of_all_waiting": "% of all waiting",
        "median_case_saving_h": "median case saving (h)", "cases_affected_share": "% of cases affected"}))
    labels = list(table["change"])
    chosen_labels = st.multiselect("Changes to include in the to-be process", labels, default=labels[:3])
    chosen = [Change(r.activity, r.kind) for r in table.itertuples(index=False) if r.change in chosen_labels]
    if not chosen:
        st.info("Pick at least one change.")
        return
    est = estimate(a.cases, row_savings(a.inst, chosen, Assumptions(reduction)))
    c = st.columns(4)
    c[0].metric("Median case duration", fmt_hours(est["median_after_h"]),
                delta=f"-{fmt_hours(est['median_before_h'] - est['median_after_h'])}", delta_color="inverse",
                help=f"Before: {fmt_hours(est['median_before_h'])}")
    c[1].metric("90th percentile", fmt_hours(est["p90_after_h"]),
                delta=f"-{fmt_hours(est['p90_before_h'] - est['p90_after_h'])}", delta_color="inverse",
                help=f"Before: {fmt_hours(est['p90_before_h'])}")
    c[2].metric("Cases affected", fmt_pct(est["cases_affected_share"], 0))
    c[3].metric("Hours saved in total", fmt_int(est["total_saved_h"]))
    st.warning(f"Assumption: automated steps wait {fmt_pct(reduction, 0)} less than today; repeated runs of a step are removed "
               "completely. These are estimates from the log, not measured results.")

    saved = row_savings(a.inst, chosen, Assumptions(reduction)).reindex(a.cases.index).fillna(0)
    cmp_df = pd.DataFrame({"as-is": a.cases["duration_h"] / 24, "to-be": (a.cases["duration_h"] - saved).clip(lower=0) / 24})
    cmp_df = cmp_df[cmp_df["as-is"] <= cmp_df["as-is"].quantile(0.99)].melt(var_name="process", value_name="days")
    fig = px.histogram(cmp_df, x="days", color="process", barmode="overlay", nbins=60, opacity=0.6,
                       labels={"days": "Case duration (days)"})
    st.plotly_chart(fig)

    st.write("**To-be process map** (green = automated step, amber = rework removed)")
    colours = {c.activity: ("#b7e4c7" if c.kind == "automate" else "#ffe8a3") for c in chosen}
    flow = build_flow(a.metrics, a.edges, a.starts, a.ends, len(a.cases))
    st.graphviz_chart(to_dot(flow, "TB", highlight=colours))
    auto_set = {c.activity for c in chosen if c.kind == "automate"}
    st.download_button("Download to-be as Mermaid", to_mermaid(flow, highlight=auto_set, title="To-be process"), "to_be.mmd")


def tab_report(a, cfg_args, facts, use_llm, key):
    st.subheader("Findings, recommendations and FSD draft")
    st.caption("All numbers come from the analysis code. The text is written either by simple rules (offline) or by Gemini, "
               "which only explains the facts. Any number in AI text that is not in the facts is flagged.")
    if st.button("Generate findings"):
        with st.spinner("Writing…"):
            text, info = make_narrative(facts, use_llm)
        st.session_state["narrative"] = (key, text, info)
    stored = st.session_state.get("narrative")
    if stored and stored[0] == key:
        _, text, info = stored
        st.caption(f"Written by: {info['source']}")
        if info["error"]:
            st.warning(f"AI call failed, showing rule-based text instead. ({info['error']})")
        if info["unverified_numbers"]:
            st.error("These numbers in the AI text are NOT in the analysis facts, check them before using: "
                     + ", ".join(info["unverified_numbers"]))
        st.markdown(text)
        cfg = AutomationConfig(*cfg_args[:3])
        st.download_button("Download full report (.md)",
                          report_markdown(a, cfg, Assumptions(cfg_args[3]), facts, text, info), "unjam_report.md")
    with st.expander("Facts used (JSON)"):
        st.code(facts_text(facts), language="json")

    st.divider()
    st.subheader("Ask the report")
    st.caption("Looks up the closest facts first (a small retrieval step), then answers only from them.")
    q = st.text_input("Your question", placeholder="Which step has the longest wait?")
    if st.button("Ask") and q.strip():
        answer, snippets, info = answer_question(q, facts, use_llm)
        st.markdown(answer)
        st.caption(f"Source: {info['source']}")
        if info["error"]:
            st.warning(f"AI call failed: {info['error']}")
        if info["unverified_numbers"]:
            st.error("Numbers not found in the retrieved facts: " + ", ".join(info["unverified_numbers"]))
        with st.expander("Facts that were retrieved"):
            for s in snippets:
                st.write("- " + s)


def tab_checks(a):
    st.subheader("Self-checks: why you can trust the numbers")
    for c in run_checks(a):
        st.markdown(f"{'✅' if c['passed'] else '❌'} **{c['check']}**: {c['result']}")
        st.caption(c["detail"])
    st.info("Validation idea for interviews: re-compute any number in this app with plain pandas from the raw log "
            "(the test-suite does this on a hand-checked mini log).")


# =========================================================================== main


def main():
    source = pick_source()
    if source is None:
        empty_state()
        return
    try:
        raw, kind = cached_raw(source["key"], source["src"], source["name"])
        mapping = mapping_ui(raw, kind)
        map_items = tuple(sorted(mapping.items(), key=lambda kv: kv[0]))
        data_key = source["key"] + "|" + repr(map_items)
        events, quality = cached_events(data_key, raw, map_items)
    except LogFormatError as exc:
        page_header()
        st.error(str(exc))
        if "column" in str(exc).lower():
            st.info("Use 'Column mapping' in the sidebar to tell UnJam which column is the case id, activity and timestamp.")
        return
    except Exception as exc:  # noqa: BLE001 - show a readable message instead of a stack trace
        page_header()
        st.error(f"Could not read this file: {exc}")
        return

    name = dataset_title(source["name"])
    a = cached_analysis(data_key, events, quality, name)

    # ---- sidebar settings
    st.sidebar.header("2 · Outcome steps")
    with st.sidebar.expander("Which steps mean approved / declined / cancelled?"):
        auto = a.outcome_map
        omap = {}
        for label in ("Approved", "Declined", "Cancelled"):
            chosen = st.multiselect(label, list(a.metrics.index), default=auto.get(label, []), key=f"out_{label}")
            if chosen:
                omap[label] = chosen
    if omap != a.outcome_map:
        a = reassign_outcomes(a, omap)

    st.sidebar.header("3 · Automation rules")
    min_share = st.sidebar.slider("Step is in at least this % of cases", 0, 100, 30) / 100
    min_wait = st.sidebar.slider("Median wait at least (hours)", 0.0, 48.0, 1.0, 0.5)
    max_spread = st.sidebar.slider("Max p90/median wait (predictability)", 1.0, 30.0, 8.0, 0.5)
    st.sidebar.header("4 · To-be assumption")
    reduction = st.sidebar.slider("Automated steps wait this much less", 0, 100, 50) / 100
    st.sidebar.header("5 · AI wording (optional)")
    configured = llm.is_configured()
    use_llm = st.sidebar.toggle("Use Gemini to explain the facts", value=False, disabled=not configured)
    if not configured:
        st.sidebar.caption("No GEMINI_API_KEY found, so findings are written by rules. Copy `.env.example` to `.env` to enable AI wording.")

    state_key = f"{data_key}|{sorted(omap.items())}"
    scored, table = cached_scoring(data_key, a, min_share, min_wait, max_spread, reduction)
    cfg_args = (min_share, min_wait, max_spread, reduction)

    page_header(name)
    tabs = st.tabs(["Overview", "As-is map", "Bottlenecks", "Rework", "Outcomes", "Automation", "To-be", "Report & Ask", "Checks"])
    with tabs[0]:
        tab_overview(a, scored)
    with tabs[1]:
        tab_map(a)
    with tabs[2]:
        tab_bottlenecks(a)
    with tabs[3]:
        tab_rework(a)
    with tabs[4]:
        tab_outcomes(a, omap)
    with tabs[5]:
        tab_automation(a, scored)
    with tabs[6]:
        tab_tobe(a, scored, table, reduction, state_key)
    with tabs[7]:
        facts = cached_facts(state_key, a, *cfg_args)
        tab_report(a, cfg_args, facts, use_llm, f"{state_key}|{cfg_args}|{use_llm}")
    with tabs[8]:
        tab_checks(a)


main()
