# Test cases and traceability

**30 test cases: 23 automated (`pytest`), 7 manual.** Automated tests use a tiny hand-made log in `tests/helpers.py`
whose expected numbers were calculated on paper (the table is in that file). That mini log is only a test fixture;
the app itself never analyses made-up data.

Run all automated tests: `python -m pytest -q`

## Test cases

| ID | Type | Requirement | Test / steps | Expected result |
|---|---|---|---|---|
| TC-01 | Auto | FR-01 | `test_parse_xes_reads_cases_and_events` | XES with namespace parsed; trace without id gets a generated name |
| TC-02 | Auto | FR-01, FR-03 | `test_load_log_handles_gzip_and_converts_to_utc` | `.xes.gz` read; +02:00 timestamps converted to UTC |
| TC-03 | Auto | FR-01 | `test_bad_file_gives_friendly_error` | Invalid file raises a readable error mentioning XES |
| TC-04 | Auto | FR-01, FR-02 | `test_csv_with_semicolons_and_column_guess` | Semicolon CSV read; columns guessed |
| TC-05 | Auto | FR-02 | `test_missing_required_column_message` | Missing case id / activity / timestamp reported by role |
| TC-06 | Auto | FR-04 | `test_instances_merge_start_complete_and_ignore_schedule` | START+COMPLETE merged (work 3 h, wait 1 h); SCHEDULE ignored and counted; 24 events become 22 steps |
| TC-07 | Auto | FR-07, FR-08 | `test_waits_of_check_step_and_durations` | Waits of one step are 1,2,2,2,3,4; median case duration 9.0 h; no negative wait |
| TC-08 | Auto | FR-08, FR-10 | `test_activity_metrics_match_hand_calculation` | Median waits (2.0 and 9.0 h), counts, rework rate 0.2 as calculated by hand |
| TC-09 | Auto | FR-05, FR-07 | `test_edges_reconcile_and_variants` | Transitions = steps - cases (16); starts and ends = cases; 5 distinct paths, top path 2 cases |
| TC-10 | Auto | FR-11 | `test_outcomes` | Outcome steps detected; 3 approved, 1 declined, 1 cancelled, 1 without outcome; "step before end" correct |
| TC-11 | Auto | FR-11 | `test_reassign_outcomes_custom_map` | User-defined outcome mapping is applied |
| TC-12 | Auto | FR-10 | `test_rework_and_loops` | Extra run and rework hours (4.0 h) found; immediate repeat detected |
| TC-13 | Auto | FR-12, FR-13 | `test_automation_rules` | Candidates / human judgement / monitor classes as per rules; stricter threshold changes the class |
| TC-14 | Auto | FR-14 | `test_to_be_estimate_by_hand` | 23.0 h saved; median 9.0 h to 6.75 h |
| TC-15 | Auto | FR-14 | `test_no_double_counting_of_same_run` | A run affected by two changes is counted once (4.5 h) |
| TC-16 | Auto | FR-14 | `test_rank_improvements_orders_by_hours_saved` | Improvements sorted by hours saved |
| TC-17 | Auto | FR-09, FR-20 | `test_slow_cases_and_checks` | Slow-case threshold correct; all self-checks pass |
| TC-18 | Auto | FR-05, FR-06, FR-15 | `test_flow_dot_and_mermaid_are_well_formed` | DOT and Mermaid text well formed; highlight class present; coverage between 0 and 1 |
| TC-19 | Auto | FR-16, FR-21 | `test_facts_and_offline_narrative` | Facts built; offline text has all four sections |
| TC-20 | Auto | FR-17 | `test_number_guard_flags_invented_numbers` | Invented number flagged; formatted numbers (13,087 / 3.20) accepted |
| TC-21 | Auto | FR-18 | `test_retrieval_finds_relevant_snippet` | Relevant fact retrieved; unrelated question answered with "not in the analysis results" |
| TC-22 | Auto | FR-16, FR-17 | `test_llm_client_with_fake_http_and_guard` | Gemini request built correctly (key header, system instruction); invented number flagged; API failure falls back to rule-based text |
| TC-23 | Auto | FR-19 | `test_export_all_writes_files` | report.md, facts.json, diagrams and CSV tables written |
| TC-24 | Manual | FR-01 | Start the app with an empty `data/real/` | Friendly start guide with download steps; no error, no sample data |
| TC-25 | Manual | FR-02 | Upload a CSV whose columns are named differently | Column mapping panel opens; after choosing columns the analysis runs |
| TC-26 | Manual | FR-13 | Move *Step is in at least X% of cases* from 30 to 90 | Automation tab, To-be tab and report facts change; fewer candidates |
| TC-27 | Manual | FR-16 | Click *Generate findings* with no `.env` | Rule-based text; label says "rules (offline)" |
| TC-28 | Manual | FR-18 | Ask "what is the weather in Dhaka?" | "This is not in the analysis results." |
| TC-29 | Manual | FR-20 | Load the BPI 2012 log, open *Checks* | Every check shows a green tick |
| TC-30 | Manual | NFR-1 | Load the BPI 2012 log on your laptop | Analysis ready in well under 30 seconds |

## Traceability matrix

| Business objective | Requirements | Use cases | Test cases |
|---|---|---|---|
| BO-1 as-is process | FR-01 to FR-07 | UC-01, UC-02 | TC-01 to TC-07, TC-09, TC-18, TC-24, TC-25 |
| BO-2 where time is lost | FR-08, FR-09 | UC-02 | TC-07, TC-08, TC-17 |
| BO-3 rework | FR-10 | UC-02 | TC-08, TC-12 |
| BO-4 automation vs human judgement | FR-11, FR-12, FR-13 | UC-02, UC-03, UC-05 | TC-10, TC-11, TC-13, TC-26 |
| BO-5 benefit estimate | FR-14, FR-15 | UC-03, UC-05 | TC-14, TC-15, TC-16, TC-18, TC-26 |
| BO-6 trust and explainability | FR-16 to FR-21 | UC-04 | TC-17, TC-19 to TC-23, TC-27 to TC-30 |
