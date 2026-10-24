from helpers import A, APPR, B, C, CANC, DECL, W, make_events
from unjam.analysis import activity_metrics, edge_table, loop_patterns, rework_table, slow_case_analysis, start_end_counts, variant_table
from unjam.decisions import (
    AUTOMATE, HUMAN, MONITOR, UNKNOWN_OUTCOME, Assumptions, AutomationConfig, Change, auto_outcome_map,
    estimate, rank_improvements, row_savings, score_activities, stuck_points,
)
from unjam.pipeline import analyse, reassign_outcomes, run_checks


def make():
    events, q = make_events()
    return analyse(events, q, name="fixture")


def test_activity_metrics_match_hand_calculation():
    a = make()
    b = a.metrics.loc[B]
    assert b["count"] == 6 and b["cases"] == 5
    assert b["median_wait_h"] == 2.0
    assert abs(b["rework_rate"] - 0.2) < 1e-9
    c = a.metrics.loc[C]
    assert c["median_wait_h"] == 9.0 and c["count"] == 4


def test_edges_reconcile_and_variants():
    a = make()
    assert a.edges["count"].sum() == len(a.inst) - len(a.cases) == 16
    assert a.starts.sum() == 6 and a.ends.sum() == 6
    assert a.variants.iloc[0]["cases"] == 2  # c1 and c4 share a path
    assert len(a.variants) == 5


def test_outcomes():
    a = make()
    assert auto_outcome_map(a.metrics.index) == {"Approved": [APPR], "Declined": [DECL], "Cancelled": [CANC]}
    o = a.cases["outcome"]
    assert (o == "Approved").sum() == 3 and (o == "Declined").sum() == 1
    assert (o == "Cancelled").sum() == 1 and (o == UNKNOWN_OUTCOME).sum() == 1
    st = stuck_points(a.inst, a.cases, a.outcome_map, "Cancelled")
    assert st.iloc[0]["step_before_end"] == C and st.iloc[0]["median_wait_before_h"] == 1.0
    st2 = stuck_points(a.inst, a.cases, a.outcome_map, UNKNOWN_OUTCOME)
    assert st2.iloc[0]["step_before_end"] == B


def test_reassign_outcomes_custom_map():
    a = make()
    b = reassign_outcomes(a, {"Reviewed": [C]})
    assert (b.cases["outcome"] == "Reviewed").sum() == 4


def test_rework_and_loops():
    a = make()
    assert a.rework.loc[B, "extra_runs"] == 1 and a.rework.loc[B, "rework_hours"] == 4.0
    self_loops, ping = loop_patterns(a.inst)
    assert self_loops.iloc[0]["step"] == B  # c2: B -> B


def test_automation_rules():
    a = make()
    s = score_activities(a.metrics, AutomationConfig())
    assert s.loc[C, "class"] == AUTOMATE and s.loc[B, "class"] == AUTOMATE
    assert s.loc[APPR, "class"] == HUMAN       # decision step
    assert s.loc[A, "class"] == MONITOR        # never waits
    assert s.loc[W, "class"] == MONITOR        # too few cases
    assert s["score"].iloc[0] == s["score"].max() and s.loc[C, "score"] > s.loc[B, "score"]
    strict = score_activities(a.metrics, AutomationConfig(min_case_share=0.9))
    assert strict.loc[C, "class"] == MONITOR


def test_to_be_estimate_by_hand():
    a = make()
    est = estimate(a.cases, row_savings(a.inst, [Change(C, "automate")], Assumptions(0.5)))
    assert est["total_saved_h"] == 23.0
    assert est["median_before_h"] == 9.0 and est["median_after_h"] == 6.75


def test_no_double_counting_of_same_run():
    a = make()
    saved = row_savings(a.inst, [Change(B, "automate"), Change(B, "rework")], Assumptions(0.5))
    assert saved["c2"] == 4.5  # 0.5 (first B) + max(2, 4) for the repeated B


def test_rank_improvements_orders_by_hours_saved():
    a = make()
    s = score_activities(a.metrics, AutomationConfig())
    t = rank_improvements(a.inst, a.cases, s, a.rework, Assumptions(0.5))
    assert t.iloc[0]["activity"] == C and t["saved_total_h"].is_monotonic_decreasing


def test_slow_cases_and_checks():
    a = make()
    comp, variants, thr = slow_case_analysis(a.inst, a.cases, q=0.5, min_slow_cases=2)
    assert thr == 9.0 and not comp.empty
    checks = run_checks(a)
    assert all(c["passed"] for c in checks), [c for c in checks if not c["passed"]]
