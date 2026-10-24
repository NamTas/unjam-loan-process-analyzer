# Process flows

## 1. As-is: how process improvement is done today (assumed, without UnJam)

```mermaid
flowchart TD
    A[Ops manager feels applications are slow] --> B[Analyst asks IT for a data extract]
    B --> C[Manual spreadsheet analysis, days to weeks]
    C --> D[Workshop: opinions about where the delay is]
    D --> E[Automation chosen by opinion or by loudest team]
    E --> F[Benefit not quantified]
```

## 2. To-be: with UnJam

```mermaid
flowchart TD
    A[Export event log from the loan system] --> B[Load log into UnJam]
    B --> C[Self-checks pass?]
    C -->|No| B2[Fix data or column mapping] --> B
    C -->|Yes| D[Review as-is map, bottlenecks, rework, outcomes]
    D --> E[Review automation candidates and decision steps]
    E --> F[Select changes, read before/after estimate]
    F --> G[Export report, FSD draft and diagrams]
    G --> H{Process owner validates?}
    H -->|No| E
    H -->|Yes| I[Pilot one change, measure real result]
```

## 3. The discovered process of the loan log (generated, not hand-drawn)

The as-is and to-be maps of the loan process are **generated from the real log**, so they appear only after you run:

```
python export_report.py --log data/real/BPI_Challenge_2012.xes.gz
```

This writes `docs/PROCESS_MAPS.md` (as-is discovered process and to-be with the top automation steps highlighted,
both as Mermaid diagrams that GitHub renders) and `docs/RESULTS.md` (the full findings report).
For a picture file, paste the Mermaid text from `outputs/as_is.mmd` into https://mermaid.live and export PNG or SVG.
