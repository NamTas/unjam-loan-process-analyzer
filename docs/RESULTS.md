# UnJam report: BPI Challenge 2012

_Proxy process: this is a real, anonymised loan/overdraft application log from a Dutch financial institution (BPI Challenge 2012), not a Bangladeshi bank._

**Cases:** 13,087  |  **Steps:** 164,506  |  **Period:** 2011-09-30 to 2012-03-14  |  **Median case duration:** 19.4 hours

> Findings below were written by: rules (offline). Numbers come from the analysis code.

## Key findings
- 13,087 cases were analysed (2011-09-30 to 2012-03-14). Median case duration is 19.4 hours; the slowest 10% take 30.5 days or more.
- Longest typical wait: **O_SENT_BACK** (median 3.7 days, p90 6.9 days).
- Most waiting in total: **W_Nabellen offertes** (52959.7 days summed over all cases).
- Most expensive repeat: **W_Nabellen offertes** is repeated in 32.7% of cases (42079.9 days spent on repeats).
- Outcomes: Declined 58.3%, Cancelled 21.4%, Approved 17.2%.
- The top 10 paths cover 49.3% of cases, so the process is highly varied.

## Recommendations
1. **Cut rework in W_Nabellen offertes**: estimated 42079.9 days saved in total (37.5% of all waiting); median case saves 4.1 hours.
2. **Cut rework in W_Completeren aanvraag**: estimated 17904.6 days saved in total (16.0% of all waiting); median case saves 7.4 hours.
3. **Cut rework in W_Nabellen incomplete dossiers**: estimated 6024.9 days saved in total (5.4% of all waiting); median case saves 21 min.

## FSD draft: automation requirements
- No automation requirement can be drafted from the current results.

## Assumptions and limits
- Proxy process: this is a real, anonymised loan/overdraft application log from a Dutch financial institution (BPI Challenge 2012), not a Bangladeshi bank.
- Savings are estimates that depend on the stated assumption; they are not measured results.
- A process owner must validate every recommendation before anything is automated.

## Tables

### Slowest steps (waiting time)

| Step | Cases % | Median wait | P90 wait | Total wait |
|---|---|---|---|---|
| O_SENT_BACK | 25% | 3.7 days | 6.9 days | 13046.5 days |
| W_Nabellen offertes | 38% | 4.0 hours | 7.3 days | 52959.7 days |
| W_Nabellen incomplete dossiers | 13% | 1.7 hours | 43.0 hours | 6062.8 days |
| W_Completeren aanvraag | 56% | 1.3 hours | 29.9 hours | 19060.4 days |
| A_ACCEPTED | 39% | 48 min | 16.9 hours | 1236.6 days |
| W_Beoordelen fraude | 1% | 31 min | 2.5 days | 162.9 days |
| W_Valideren aanvraag | 25% | 12 min | 3.2 days | 6590.5 days |
| O_ACCEPTED | 17% | 8 min | 2.2 days | 1288.3 days |
| O_DECLINED | 6% | 5 min | 3.2 days | 634.1 days |
| A_DECLINED | 58% | 1 min | 11.9 hours | 1484.9 days |

### Rework

| Step | Cases repeating | Extra runs | Hours on repeats |
|---|---|---|---|
| W_Nabellen offertes | 32.7% | 17,965 | 42079.9 days |
| W_Completeren aanvraag | 33.8% | 16,600 | 17904.6 days |
| W_Nabellen incomplete dossiers | 11.3% | 9,760 | 6024.9 days |
| W_Valideren aanvraag | 15.4% | 4,686 | 1402.1 days |
| O_SELECTED | 11.0% | 2,015 | 1261.1 days |
| O_CANCELLED | 5.7% | 995 | 899.6 days |
| O_SENT_BACK | 1.5% | 200 | 348.5 days |
| W_Beoordelen fraude | 0.6% | 162 | 58.8 days |
| W_Afhandelen leads | 5.9% | 1,143 | 26.5 days |
| O_CREATED | 11.0% | 2,015 | 2.0 hours |

### Outcomes

| Step | Cases | Share | Median duration | P90 duration |
|---|---|---|---|---|
| Declined | 7,635 | 58.3% | 11 min | 7.9 days |
| Cancelled | 2,807 | 21.4% | 16.8 days | 31.8 days |
| Approved | 2,246 | 17.2% | 14.5 days | 28.7 days |
| No final outcome | 399 | 3.0% | 16.1 days | 29.9 days |

### Automation opportunity scores

| Step | Score | Class | Why |
|---|---|---|---|
| O_SENT_BACK | 8.1 | Monitor | low volume or little waiting; in 25% of cases, median wait 89.4 h, p90/median 1.9, repeated in 6% of its cases |
| W_Nabellen offertes | 4.2 | Needs human judgement | slow but timing varies a lot (case specific); in 38% of cases, median wait 4.0 h, p90/median 43.7, repeated in 85% of its cases |
| W_Completeren aanvraag | 1.2 | Needs human judgement | slow but timing varies a lot (case specific); in 56% of cases, median wait 1.3 h, p90/median 22.5, repeated in 60% of its cases |
| W_Nabellen incomplete dossiers | 0.9 | Needs human judgement | slow but timing varies a lot (case specific); in 13% of cases, median wait 1.7 h, p90/median 25.3, repeated in 89% of its cases |
| A_ACCEPTED | 0.1 | Needs human judgement | name looks like a decision step; in 39% of cases, median wait 0.8 h, p90/median 21.2, repeated in 0% of its cases |
| W_Valideren aanvraag | 0.1 | Monitor | low volume or little waiting; in 25% of cases, median wait 0.2 h, p90/median 376.8, repeated in 63% of its cases |
| O_ACCEPTED | 0.0 | Needs human judgement | name looks like a decision step; in 17% of cases, median wait 0.1 h, p90/median 422.4, repeated in 0% of its cases |
| W_Beoordelen fraude | 0.0 | Monitor | low volume or little waiting; in 1% of cases, median wait 0.5 h, p90/median 116.8, repeated in 75% of its cases |
| A_DECLINED | 0.0 | Needs human judgement | name looks like a decision step; in 58% of cases, median wait 0.0 h, p90/median 712.3, repeated in 0% of its cases |
| A_PARTLYSUBMITTED | 0.0 | Monitor | low volume or little waiting; in 100% of cases, median wait 0.0 h, p90/median 4.0, repeated in 0% of its cases |
| A_SUBMITTED | 0.0 | Monitor | low volume or little waiting; in 100% of cases, median wait 0.0 h, p90/median n/a, repeated in 0% of its cases |
| O_CREATED | 0.0 | Monitor | low volume or little waiting; in 38% of cases, median wait 0.0 h, p90/median 1.9, repeated in 29% of its cases |

### Self-checks

| Check | Result | Passed |
|---|---|---|
| Top 10 paths cover cases | 49.3% of cases | yes |
| Process map adds up | OK | yes |
| Raw events reconcile with steps | OK | yes |
| Bottlenecks: median vs 90th percentile | 2 of top 5 steps agree; rank correlation 0.63 | yes |
| Waiting time is consistent | 0 negative waits; 0.0% of cases wait longer than they last | yes |
| Outcome coverage | 97.0% of cases have a final outcome | yes |

_Assumption used for the to-be estimate: automated steps wait 50% less._
