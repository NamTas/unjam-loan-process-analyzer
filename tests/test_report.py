import json
import os
import tempfile
from pathlib import Path

from helpers import C, make_events
from unjam import llm
from unjam.decisions import Assumptions, AutomationConfig
from unjam.flow import build_flow, to_dot, to_mermaid
from unjam.pipeline import analyse
from unjam.report import answer_question, build_facts, export_all, facts_text, make_narrative, offline_narrative


def make():
    events, q = make_events()
    return analyse(events, q, name="fixture")


def test_flow_dot_and_mermaid_are_well_formed():
    a = make()
    flow = build_flow(a.metrics, a.edges, a.starts, a.ends, len(a.cases), max_nodes=10, min_edge_share=0.0)
    dot = to_dot(flow, highlight={C: "#c7f9cc"})
    assert dot.startswith("digraph") and dot.rstrip().endswith("}") and "start ->" in dot and "-> end" in dot
    mm = to_mermaid(flow, highlight={C})
    assert mm.splitlines()[0] == "flowchart TD" and "classDef auto" in mm
    assert 0 < flow.edge_coverage <= 1


def test_facts_and_offline_narrative():
    a = make()
    facts = build_facts(a, AutomationConfig(), Assumptions(0.5))
    assert facts["dataset"]["cases"] == "6"
    assert facts["top_improvements"][0]["change"].endswith(C)
    text = offline_narrative(facts)
    for heading in ("## Key findings", "## Recommendations", "## FSD draft", "## Assumptions and limits"):
        assert heading in text
    narrative, info = make_narrative(facts, use_llm=False)
    assert info["source"].startswith("rules")


def test_number_guard_flags_invented_numbers():
    facts = {"a": "median wait 3.2 hours", "b": "13,087 cases"}
    ft = facts_text(facts)
    assert llm.unverified_numbers("Wait is 3.2 hours over 13,087 cases (top 3)", ft) == []
    assert llm.unverified_numbers("Wait is 4.7 hours", ft) == ["4.7"]


def test_retrieval_finds_relevant_snippet():
    a = make()
    facts = build_facts(a, AutomationConfig(), Assumptions(0.5))
    answer, snippets, info = answer_question("which step has the longest median wait", facts, use_llm=False)
    assert snippets and "wait" in snippets[0].lower()
    none_answer, none_snips, _ = answer_question("zzzz qqqq", facts, use_llm=False)
    assert none_answer == "This is not in the analysis results." and none_snips == []


def test_llm_client_with_fake_http_and_guard():
    old_post, old_key = llm._post, os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = "test-key"
    seen = {}

    def fake_post(url, headers, body, timeout):
        seen["url"], seen["headers"], seen["body"] = url, headers, body
        return {"candidates": [{"content": {"parts": [{"text": "Median is 9.0 hours and 77 cases."}]}}]}

    llm._post = fake_post
    try:
        text = llm.generate("hello", system="be brief")
        assert text.startswith("Median") and "generateContent" in seen["url"]
        assert seen["headers"]["x-goog-api-key"] == "test-key" and "systemInstruction" in seen["body"]
        facts = {"x": "9 hours"}
        narrative, info = make_narrative(build_facts(make(), AutomationConfig(), Assumptions(0.5)), use_llm=True)
        assert "Gemini" in info["source"] and info["unverified_numbers"] == ["9.0", "77"] or "77" in info["unverified_numbers"]

        def boom(*a, **k):
            raise llm.LLMError("network down")
        llm._post = boom
        narrative, info = make_narrative(build_facts(make(), AutomationConfig(), Assumptions(0.5)), use_llm=True)
        assert info["error"] == "network down" and narrative.startswith("## Key findings")  # safe fallback
    finally:
        llm._post = old_post
        if old_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = old_key


def test_export_all_writes_files():
    a = make()
    with tempfile.TemporaryDirectory() as d:
        res = export_all(a, AutomationConfig(), Assumptions(0.5), Path(d), use_llm=False)
        for name in ("report.md", "facts.json", "as_is.mmd", "to_be.mmd", "step_metrics.csv", "automation_scores.csv", "improvements.csv"):
            assert name in res["files"], name
        report = (Path(d) / "report.md").read_text(encoding="utf-8")
        assert "# UnJam report: fixture" in report and "### Self-checks" in report
        assert json.loads((Path(d) / "facts.json").read_text(encoding="utf-8"))["dataset"]["name"] == "fixture"
