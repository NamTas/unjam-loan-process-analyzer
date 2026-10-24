"""Process map (as-is / to-be): filtered flow graph -> Graphviz DOT and Mermaid text."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .utils import fmt_hours


@dataclass
class Flow:
    nodes: pd.DataFrame  # index = activity, from activity_metrics (filtered)
    edges: pd.DataFrame  # source, target, count, ...
    starts: dict
    ends: dict
    edge_coverage: float  # share of all transitions that are drawn
    n_cases: int


def build_flow(metrics, edges, starts, ends, n_cases, max_nodes: int = 15, min_edge_share: float = 0.02) -> Flow:
    """Keep the busiest `max_nodes` steps and edges used by at least `min_edge_share` of cases."""
    keep = list(metrics.sort_values("count", ascending=False).head(max_nodes).index)
    mask = (
        edges["source"].isin(keep)
        & edges["target"].isin(keep)
        & (edges["count"] >= min_edge_share * n_cases)
    )
    e = edges[mask].copy()
    touched = set(e["source"]) | set(e["target"]) | {a for a in starts.index if a in keep} | {a for a in ends.index if a in keep}
    nodes = metrics.loc[[a for a in keep if a in touched]]
    total = edges["count"].sum()
    coverage = float(e["count"].sum() / total) if total else 0.0
    return Flow(
        nodes=nodes,
        edges=e,
        starts={a: int(c) for a, c in starts.items() if a in nodes.index},
        ends={a: int(c) for a, c in ends.items() if a in nodes.index},
        edge_coverage=coverage,
        n_cases=n_cases,
    )


def heat_color(t: float) -> str:
    """0 -> pale, 1 -> strong red/orange. Used to colour steps by waiting time."""
    t = max(0.0, min(1.0, float(t)))
    lo, hi = (255, 245, 235), (230, 85, 60)
    rgb = [round(l + (h - l) * t) for l, h in zip(lo, hi)]
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _esc(text: str) -> str:
    return str(text).replace("\\", "/").replace('"', "'")


def to_dot(flow: Flow, rankdir: str = "TB", heat_col: str = "median_wait_h",
           highlight: dict | None = None, show_edge_wait: bool = False) -> str:
    """Graphviz DOT text. Step colour = waiting time (heat), edge width = number of cases."""
    highlight = highlight or {}
    ids = {a: f"n{i}" for i, a in enumerate(flow.nodes.index)}
    max_heat = float(flow.nodes[heat_col].max()) if len(flow.nodes) else 0.0
    max_edge = float(flow.edges["count"].max()) if len(flow.edges) else 1.0
    lines = [
        "digraph UnJam {",
        f"rankdir={rankdir};",
        'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#555555"];',
        'edge [fontname="Helvetica", fontsize=9, color="#666666"];',
        'start [label="Start", shape=circle, fillcolor="#d8f3dc", style=filled];',
        'end [label="End", shape=doublecircle, fillcolor="#e9ecef", style=filled];',
    ]
    for act, row in flow.nodes.iterrows():
        fill = highlight.get(act) or heat_color(row[heat_col] / max_heat if max_heat > 0 else 0)
        label = f"{_esc(act)}\\n{int(row['count']):,} steps\\nwait {fmt_hours(row['median_wait_h'])}"
        lines.append(f'{ids[act]} [label="{label}", fillcolor="{fill}"];')
    max_start = max(flow.starts.values(), default=1)
    for act, c in flow.starts.items():
        lines.append(f'start -> {ids[act]} [label="{c:,}", penwidth={0.8 + 4 * c / max_start:.2f}];')
    for r in flow.edges.itertuples(index=False):
        label = f"{int(r.count):,}"
        if show_edge_wait:
            label += f"\\n~{fmt_hours(r.median_wait_h)}"
        lines.append(f'{ids[r.source]} -> {ids[r.target]} [label="{label}", penwidth={0.8 + 5 * r.count / max_edge:.2f}];')
    max_end = max(flow.ends.values(), default=1)
    for act, c in flow.ends.items():
        lines.append(f'{ids[act]} -> end [label="{c:,}", penwidth={0.8 + 4 * c / max_end:.2f}];')
    lines.append("}")
    return "\n".join(lines)


def to_mermaid(flow: Flow, highlight: set | None = None, title: str | None = None) -> str:
    """Mermaid flowchart text (paste into docs, GitHub README or mermaid.live)."""
    highlight = highlight or set()
    ids = {a: f"n{i}" for i, a in enumerate(flow.nodes.index)}
    lines = []
    if title:
        lines += ["---", f"title: {_esc(title)}", "---"]
    lines += ["flowchart TD", "  start((Start))", "  finish(((End)))"]
    for act, row in flow.nodes.iterrows():
        lines.append(f'  {ids[act]}["{_esc(act)}<br/>{int(row["cases"]):,} cases · wait {fmt_hours(row["median_wait_h"])}"]')
    for act, c in flow.starts.items():
        lines.append(f"  start -->|{c:,}| {ids[act]}")
    for r in flow.edges.itertuples(index=False):
        lines.append(f"  {ids[r.source]} -->|{int(r.count):,}| {ids[r.target]}")
    for act, c in flow.ends.items():
        lines.append(f"  {ids[act]} -->|{c:,}| finish")
    if highlight:
        lines.append("  classDef auto fill:#c7f9cc,stroke:#2d6a4f,stroke-width:2px;")
        members = ",".join(ids[a] for a in flow.nodes.index if a in highlight)
        if members:
            lines.append(f"  class {members} auto;")
    return "\n".join(lines)
