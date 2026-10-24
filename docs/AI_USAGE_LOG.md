# AI usage log (how AI tools were used to build this project)

Keep this log honest and up to date. Interviewers value "what I asked, what was wrong, what I fixed".
Rows 1 to 4 describe the initial build; add your own rows as you change the project.

| # | Date | Tool | What I asked / what it produced | What I checked or changed |
|---|---|---|---|---|
| 1 | 2026-10-24 | Claude (chat) | Project idea selection from the job description; first project structure, engine code (loader, analysis, scoring, to-be), Streamlit app, docs | Read every module; ran the unit tests (23 passed on a hand-calculated mini log); ran a 430,000-event speed test |
| 2 | 2026-10-24 | Claude (chat) | XES parser, waiting-time definition, scoring rules | Re-derived the expected numbers on paper (see `tests/helpers.py` table) and compared |
| 3 | 2026-10-24 | Claude (chat) | AI layer: Gemini call, number guard, retrieval for "Ask the report" | Tested with a fake HTTP response; confirmed that an invented number is flagged |
| 4 | 2026-10-24 | Claude (chat) | BRD, FSD, use cases, test cases | Compared requirement IDs with code and tests |
| 5 | | | | |

## What I learned / what I would tell an interviewer
- Where the AI assistant was wrong or too confident, and how I found out: _write your own notes here after running the project on the real log_
- Which decisions are mine (thresholds, assumption of 50% reduction, which steps are decision steps): _write here_
