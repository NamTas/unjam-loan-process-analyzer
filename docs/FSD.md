# Functional Specification Document (FSD): UnJam

Traces to BRD.md. Requirement IDs are used in USE_CASES.md and TEST_CASES.md.

## 1. System overview

UnJam is a local Streamlit application and a command line exporter built on one Python package (`unjam/`).

```
file (XES/CSV) -> loader -> step instances -> analysis (map, waits, rework, outcomes)
                                           -> automation scoring -> to-be estimate
                                           -> facts -> rule-based text | optional Gemini text -> number guard
                                           -> Streamlit tabs | report.md + CSV + Mermaid
```

## 2. Functional requirements

| ID | Requirement | Module |
|---|---|---|
| FR-01 | The user can load an event log from `data/real/` or by upload. Supported: `.xes`, `.xes.gz`, `.csv`, `.csv.gz`, `.zip`. With no file the app shows a friendly start guide, never an error and never sample data. | loader, app |
| FR-02 | For CSV files the system guesses the case id, activity, timestamp, lifecycle and resource columns and lets the user change the mapping. Missing required columns give a readable message. | loader, app |
| FR-03 | The system cleans the log (drops rows without case, activity or valid timestamp; converts to UTC) and reports data-quality figures. | loader |
| FR-04 | START and COMPLETE events of the same task are merged into one *step* with start, end and work time. Other lifecycle values (e.g. SCHEDULE) are ignored and counted. | loader |
| FR-05 | The system draws the as-is process map with step counts, transition counts and waiting-time colour, with filters (max steps, minimum path share, direction) and shows how much of all transitions is displayed. | flow, app |
| FR-06 | The map can be exported as Mermaid and Graphviz DOT. | flow, app |
| FR-07 | The system shows case duration (median, 90th percentile), its distribution and the most common paths with cumulative coverage. | analysis, app |
| FR-08 | For each step: times run, share of cases, median / p90 / total waiting time and median work time. For each transition: count and waiting time. Steps can be ranked by median, p90 or total wait. | analysis |
| FR-09 | The system compares the slowest 10% of cases with the others (presence and average runs per step) and lists their most common paths. | analysis |
| FR-10 | Rework: per step the share of cases repeating it, extra runs and hours spent on repeats; immediate repeats (A to A) and ping-pong returns (A to B to A). | analysis |
| FR-11 | Outcomes: approved / declined / cancelled steps are detected automatically (user can override). Per outcome: share, duration, and where cases sit just before they end. Cases without a final outcome are shown separately. | decisions, app |
| FR-12 | Automation score = 100 x volume x repetition x waiting time (each scaled 0 to 1 by the maximum over all steps; repetition = 1 + rework rate). Each step is classed *Automation candidate*, *Needs human judgement* or *Monitor* with a written reason. | decisions |
| FR-13 | Thresholds (minimum share of cases, minimum median wait, maximum p90/median) are adjustable and all dependent views refresh. | app |
| FR-14 | To-be estimate: each automation candidate (reduce waiting by X%) and each step with rework (remove repeated runs) is tried alone and ranked by hours saved. The user selects changes; the tool shows median and p90 case duration before and after, cases affected and total hours saved. A run is never counted twice. | decisions |
| FR-15 | A to-be process map highlights automated steps and rework removal; exportable as Mermaid. | flow, app |
| FR-16 | Findings text (key findings, recommendations, FSD draft, limits) is generated from the computed facts. Without an API key it is written by rules. With a key, Gemini may phrase it. If the AI call fails the rule-based text is used. | report, llm |
| FR-17 | Number guard: every number in AI-written text that is not in the facts (small counting numbers excepted) is listed as unverified. | llm |
| FR-18 | "Ask the report": the closest facts are retrieved (TF-IDF) and the answer is limited to them. If nothing matches the system answers "This is not in the analysis results." | llm, report |
| FR-19 | The report (markdown), facts (JSON), tables (CSV) and diagrams (Mermaid) can be exported from the app or with `python export_report.py`. | report |
| FR-20 | Self-checks are shown: top-10 path coverage, map reconciliation (transitions = steps - cases), raw events reconcile with steps, median vs p90 agreement, waiting-time consistency, outcome coverage. | pipeline |
| FR-21 | Reports state the data note (proxy process for BPI Challenge 2012) and that results need human validation. | config, report |

## 3. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Performance: about 430,000 events load and analyse in well under 30 seconds on a normal laptop. |
| NFR-2 | Privacy: raw events never leave the PC. If Gemini is enabled only the aggregated facts JSON is sent. |
| NFR-3 | Reproducibility: same file and settings give the same numbers; no randomness. |
| NFR-4 | Explainability: every rule and threshold is written in this document and shown in the app. |
| NFR-5 | Testability: core maths covered by automated tests on a hand-calculated mini log. |
| NFR-6 | Usability: all errors are readable sentences (no stack traces for user mistakes). |

## 4. Data definitions

| Term | Definition |
|---|---|
| Case | One loan application (one case id). |
| Event | One row in the log. |
| Step (instance) | One execution of an activity: end = COMPLETE time, start = matching START time or the end time if none. |
| Wait (hours) | `max(0, start - latest end of all earlier steps in the case)`; the first step of a case has no wait. |
| Work (hours) | `end - start`. |
| Case duration | Last end minus first start in the case. |
| Rework rate of a step | Share of the cases containing the step in which it runs more than once. |
| Spread | p90 wait divided by median wait of the step (low = predictable timing). |
| Outcome | Label of the last approved / declined / cancelled step in the case, otherwise "No final outcome". |

## 5. Rules and formulas

1. **Volume** = times the step ran / maximum over steps. **Repetition** = (1 + rework rate) / maximum over steps. **Waiting** = median wait / maximum over steps. **Score** = 100 x product.
2. **Classification** (in order):
   1. name contains a decision keyword -> *Needs human judgement*
   2. share of cases >= minimum AND median wait >= minimum AND spread <= maximum -> *Automation candidate*
   3. median wait >= minimum but spread above maximum -> *Needs human judgement* (timing depends on the case)
   4. otherwise -> *Monitor*
3. **Automate change:** saved hours of a run = wait x reduction. **Cut rework change:** saved hours of every run after the first = wait + work.
4. **Case saving** = sum of saved hours of its runs (a run takes the larger of its applicable savings). **After duration** = max(0, before - saving).

## 6. Limitations written into the specification

- Waiting time includes nights, weekends and queueing; no working-calendar adjustment.
- Reducing a wait by X% is an assumption; real automation also has set-up cost and failure cases.
- Overlapping tasks are handled by measuring gaps on the case timeline, which can hide parallel work.
- Only timing and sequence are used; no customer or amount attributes in v1.
