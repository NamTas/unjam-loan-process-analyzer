# AI limitations and responsible use

## What the AI does here, and what it does not
| Part | Uses AI? | Notes |
|---|---|---|
| Loading, cleaning, process map, waits, rework, outcomes, scoring, to-be numbers | **No** | Plain pandas code. Every number can be re-computed. |
| Findings / recommendations / FSD draft wording | Optional (Gemini) | Without a key, rules write the text from the same facts. |
| "Ask the report" | Retrieval is plain TF-IDF; wording optional (Gemini) | Answer is limited to retrieved facts. |
| Deciding to automate something | **Never** | Only a human process owner decides. |

## Hallucination guard
1. The prompt contains only the computed facts and says: copy numbers exactly, never calculate, say when unknown.
2. After the answer, every number is compared with the numbers in the facts. Numbers not found (small counting numbers up to 10 excepted) are shown as **unverified** in the app and in the exported report.
3. If the AI call fails, the rule-based text is shown instead. The tool never shows invented text as a result.
4. The guard checks numbers, not claims. A wrong *interpretation* with correct numbers is still possible, so a human must read the findings.

## Data and privacy
- Event logs must be anonymised (BPI Challenge 2012 is). Do not load logs with customer names or national ids.
- Raw events stay on the local PC. With Gemini enabled only the aggregated facts JSON (step names, durations, shares) is sent. Shown in the app under *Facts used*.
- The API key is read from `.env`, which is excluded from git.

## Limits of the analysis
- Proxy data: BPI Challenge 2012 is a Dutch financial institution, not a Bangladeshi bank. Process, volumes and regulation differ.
- Waiting time includes nights and weekends; there is no working-calendar correction.
- Savings are estimates from an assumption (default: automated steps wait 50% less). Real benefit needs a pilot.
- Names of decision steps are matched with keywords; unusual naming needs manual review in the sidebar.
- Timing-based rules cannot see legal, risk or customer-experience reasons to keep a step manual.

## Fairness and ethics
- UnJam does not score or decide on customers. It analyses process timing only.
- Decision steps (approve, decline, cancel, accept, assess, sign) are never proposed for automation.
- Before any automation of a step that touches customer outcomes, a fairness and compliance review is required (outside this tool).
- Every automatic decision in a recommended design must be logged and overridable by an officer (written into the generated FSD draft).

## Human validation checklist
- [ ] Self-checks tab shows all checks passed
- [ ] Top 3 recommendations reviewed by someone who knows the process
- [ ] Assumption (waiting reduction) agreed with the process owner
- [ ] Unverified numbers list is empty, or each item was checked by hand
