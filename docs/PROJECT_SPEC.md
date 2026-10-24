# UnJam: complete project brief

> Written so that a person (or another AI assistant or account) can understand the whole project without any
> earlier conversation. Read this first, then `docs/FSD.md` for the detailed requirements.

## 1. In one paragraph
UnJam takes a **real event log of a bank loan process** (who did which step when) and shows where applications
wait, which steps are repeated, how applications end (approved / declined / cancelled), and which steps are routine
enough for rule-based automation. It estimates the benefit of the top improvements under a visible assumption and
writes plain-language findings plus an FSD draft. A small optional AI layer (Gemini) only explains numbers that the
code computed, and a guard flags any number it invents. **No model is trained.**

## 2. Why this project exists
- Target role: a banking / IT-services role that prepares BRD, FSD, use cases and process flows, finds opportunities
  to automate repetitive activities, uses AI tools (LLM, prompt engineering, RAG, API-based AI), and tests solutions.
- Target skills: banking operations, retail banking, process automation, AI basics, ethics in AI, AI programming.
- Portfolio gap this fills: the author's other projects are ML, ETL and LLM tools; this one shows business analysis
  on real data (process flow, evidence-based recommendation, documentation, testing).

## 3. Data (real only)
- **BPI Challenge 2012**: event log of a loan / overdraft application process of a Dutch financial institution,
  about 13,000 applications, anonymised, `.xes.gz` (3.3 MB). 4TU.ResearchData, licence "4TU General Terms of Use"
  (citation required). DOI 10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f.
- It is a **proxy process** (not a Bangladeshi bank). Every output says so.
- The app never creates or analyses synthetic data. Without a file it shows a start guide.

## 4. What the user can do
Load a log -> see the as-is process map -> see bottlenecks (median / p90 / total wait) -> see rework -> see outcomes
and where cases stop -> see automation candidates with reasons -> pick improvements and read before/after
estimate -> generate findings (rules or Gemini) -> ask questions -> export report, tables and Mermaid diagrams.

## 5. Key design decisions (and why)
| Decision | Reason |
|---|---|
| Own XES parser and pandas analysis instead of a process-mining library | No heavy install, every number reproducible, easy to explain |
| Wait = real gap on the case timeline | Waits can never be negative or exceed the case duration; checked automatically |
| Rule-based automation classes with written reasons | Explainable to an ops manager; thresholds adjustable |
| Savings shown only as assumption-based estimates | Honest; avoids claiming measured benefit |
| LLM explains facts only, with a number guard and offline fallback | Hallucination control; works without API key or internet |
| "Ask the report" = TF-IDF retrieval over the computed facts | Small, testable RAG-style step without a vector database |
| Decision steps never automated | Governance and fairness |

## 6. Deliverables
- Code: `unjam/` package, `app.py` (Streamlit), `export_report.py` (CLI), `tests/` (23 automated tests).
- Documents: BRD, FSD, use cases (5), process flows, test cases (30) with traceability, AI limitations, AI usage log, stakeholder questions.
- Generated after running on real data: `docs/RESULTS.md`, `docs/PROCESS_MAPS.md`, `outputs/*`.

## 7. Definition of done
1. `python -m pytest -q` passes.
2. App loads BPI 2012 and the *Checks* tab is all green.
3. `python export_report.py` writes the results and process maps.
4. README results section reviewed by the author against the real numbers.
5. AI usage log filled in honestly.

## 8. Suggested 8-day plan
| Day | Work |
|---|---|
| 1 | Download data, read licence, run the app, understand the log (activities, lifecycle, outcomes); read BRD and FSD |
| 2 | Read `loader.py`; check as-is map against raw counts in the Checks tab |
| 3 | Bottlenecks and rework: write down the top 3 findings in your own words |
| 4 | Outcomes and automation scoring: test different thresholds, note what changes |
| 5 | To-be estimate and its assumption; discuss with a friend acting as process owner |
| 6 | Enable Gemini, compare AI text with rule-based text, note unverified numbers |
| 7 | Run `export_report.py`; update README with real numbers; fill the AI usage log; run the manual test cases |
| 8 | Clean repository, record a 1-minute demo, write CV bullets |

## 9. Honest limitations
Proxy data; waiting time includes nights and weekends; savings are assumptions; keyword-based decision-step detection;
only process timing is analysed (no amounts, customer attributes or fairness metrics in v1).
