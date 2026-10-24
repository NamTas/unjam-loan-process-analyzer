# Business Requirements Document (BRD): UnJam

| Item | Value |
|---|---|
| Product | UnJam: loan process bottleneck and automation finder |
| Document owner | Namira Tasnim (business analyst / developer role in this project) |
| Status | Version 1.0 |
| Related documents | FSD.md, USE_CASES.md, PROCESS_FLOWS.md, TEST_CASES.md |

> **How these requirements were gathered.** There was no access to a real bank team. The requirements below are
> derived from (a) the public description of the BPI Challenge 2012 loan process, (b) common retail-banking
> operations practice and (c) the interview guide in `STAKEHOLDER_QUESTIONS.md`. They are *assumed* stakeholder
> needs, not results of real interviews. Validate them with real stakeholders before using the tool in a bank.

## 1. Problem statement

Retail loan and overdraft applications pass through many manual and system steps. Operations managers know that
some applications are slow, but usually cannot say **which step** loses the most time, **which steps are repeated**
(rework), and **which steps are routine enough to automate**. Decisions about automation are then made on opinion
instead of evidence, and the expected benefit is not quantified.

## 2. Business goal and measurable objectives

**Goal:** reduce loan application cycle time by automating the right steps first.

| ID | Objective | Measure (how we know the tool delivered) |
|---|---|---|
| BO-1 | Show the real process as it happens, not as documented | As-is map built from the event log; top-10 paths coverage reported |
| BO-2 | Locate where time is lost | Steps ranked by median, 90th percentile and total waiting time |
| BO-3 | Quantify rework | Share of cases repeating a step and hours spent on repeats per step |
| BO-4 | Separate "rule-based automation" steps from "human judgement" steps | Every step has a class and a written reason |
| BO-5 | Estimate the benefit of the top improvements with stated assumptions | Median and 90th percentile case duration before and after |
| BO-6 | Make results trustworthy and explainable | Self-checks pass; every AI-written number is verified against computed facts |

## 3. Stakeholders

| Stakeholder | Interest | Needs from the tool |
|---|---|---|
| Operations manager | Faster cycle time, lower cost | Ranked bottlenecks, savings estimate, plain-language summary |
| Loan officer | Less repetitive work, fewer returns of the same file | Which repeated steps cost the most; what stays manual |
| Process owner / business analyst | Accurate as-is and to-be documentation | Process maps (Mermaid), BRD/FSD draft text |
| IT / developers | Clear automation requirements | Prioritised candidate list with acceptance criteria |
| Risk and compliance | Controlled automation, no unfair or opaque decisions | Decision steps kept manual, human validation, audit trail of how numbers were produced |
| Data / AI team | Reusable, explainable analysis | Tested code, documented rules, limits of AI use |

## 4. Scope

**In scope**
- Reading event logs (XES, XES.GZ, CSV, ZIP) of a loan or similar approval process.
- As-is process discovery, waiting-time and rework analysis, outcome analysis.
- Rule-based automation scoring and an assumption-based to-be estimate.
- Plain-language findings, FSD draft text and a question-answering box limited to computed results.
- Export of report, tables and Mermaid diagrams.

**Out of scope**
- Training prediction models (credit scoring, outcome prediction).
- Real-time monitoring or integration with a core banking system.
- Automatically changing any bank process. UnJam only recommends.
- Processing personal customer data. Event logs must be anonymised.

## 5. Business rules

| ID | Rule |
|---|---|
| BR-1 | Waiting time of a step is the gap between the end of the latest earlier work in the same case and the start of the step. It is never negative. |
| BR-2 | A step whose name indicates a decision (approve, decline, cancel, accept, assess, sign...) is never classed as "automation candidate". |
| BR-3 | A step is an automation candidate only if it is busy (share of cases), slow (median wait) and predictable (p90/median wait). The three thresholds are user-adjustable. |
| BR-4 | Savings are estimates under a visible assumption. They must never be presented as measured results. |
| BR-5 | AI-written text may only explain numbers computed by the tool. Any other number must be flagged. |

## 6. Assumptions, constraints, dependencies

- The log contains a case id, an activity name and a timestamp for every event.
- The reference dataset (BPI Challenge 2012) is a **proxy process** from a Dutch financial institution, not a Bangladeshi bank. Its licence ("4TU General Terms of Use") requires citing the author.
- Python 3.10+, local PC. Internet is only needed for the optional Gemini call; only aggregated facts (never raw events) are sent.

## 7. Success criteria

1. The tool runs on the BPI Challenge 2012 log in under 30 seconds and all self-checks pass.
2. A reviewer can re-compute any reported number from the raw log (the automated tests do this on a hand-checked mini log).
3. A non-technical manager can read the findings and understand what to automate first and why.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Proxy data does not represent a Bangladeshi bank | README and every report state this; method is portable to a local log |
| Waiting time includes non-working hours and weekends | Documented limitation; no calendar adjustment in v1 |
| AI text invents numbers | Number guard flags unverified numbers; offline mode available |
| Over-trust in recommendations | Human validation statement in every report; decision steps stay manual |
