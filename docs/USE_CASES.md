# Use cases

Actors: **Analyst** (business analyst / data analyst), **Ops manager**, **Process owner**.

## UC-01 Load an event log
- **Actor:** Analyst. **Trigger:** wants to analyse a process. **Preconditions:** a log file exists.
- **Main flow:** 1) Analyst opens the app. 2) Chooses a file from `data/real/` or uploads one. 3) For CSV, checks the suggested column mapping. 4) System cleans the log and shows data-quality figures. 5) System runs the analysis and shows the Overview tab.
- **Alternative flows:** A1 no file available: start guide with download steps. A2 required column missing: message and mapping panel. A3 file not readable: readable error.
- **Postcondition:** analysis is ready in all tabs. **Requirements:** FR-01 to FR-04, FR-07.

## UC-02 Find bottlenecks and rework
- **Actor:** Analyst, Ops manager.
- **Main flow:** 1) Open *As-is map* and read the colour/width encoding. 2) Open *Bottlenecks*, rank by total, median or p90 wait. 3) Read the slowest-10%-of-cases comparison. 4) Open *Rework* and read repeated steps and hours spent. 5) Open *Outcomes* to see where cancelled or unfinished cases stop.
- **Alternative flow:** log has no outcome steps: user selects them in the sidebar.
- **Postcondition:** analyst can name the 3 biggest sources of delay and rework. **Requirements:** FR-05, FR-08 to FR-11.

## UC-03 Review automation candidates and the to-be estimate
- **Actor:** Process owner, Analyst.
- **Main flow:** 1) Open *Automation*. 2) Read class and reason for each step. 3) Open *To-be*, review ranked improvements. 4) Select the changes to include. 5) Read median and p90 before/after and the stated assumption. 6) Open the to-be map.
- **Alternative flow:** no candidate under current thresholds: system suggests lowering thresholds or checking rework.
- **Postcondition:** a shortlist of changes with estimated benefit. **Requirements:** FR-12, FR-14, FR-15.

## UC-04 Generate findings, ask questions and export
- **Actor:** Analyst. **Preconditions:** analysis done. API key optional.
- **Main flow:** 1) Open *Report & Ask*. 2) Click *Generate findings*. 3) System shows findings, recommendations, FSD draft and limits, and states who wrote them (rules or Gemini). 4) Any unverified number is flagged. 5) Analyst asks a question; system answers from retrieved facts. 6) Analyst downloads the report and Mermaid diagrams (or runs `python export_report.py`).
- **Alternative flows:** A1 no API key: rule-based text. A2 AI call fails: rule-based text and a warning. A3 question not covered: "This is not in the analysis results."
- **Requirements:** FR-06, FR-16 to FR-19, FR-21.

## UC-05 Change thresholds and assumptions
- **Actor:** Process owner.
- **Main flow:** 1) Change *step is in at least X% of cases*, *median wait at least*, *max p90/median* or *automated steps wait Y% less* in the sidebar. 2) System re-scores steps, re-ranks improvements and updates the to-be estimate and report facts.
- **Postcondition:** all views consistent with the new settings. **Requirements:** FR-13, FR-14.
