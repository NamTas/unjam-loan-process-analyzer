"""Tiny hand-made event log used ONLY to unit-test the maths (never analysed by the app).

Time unit: hours after 2020-01-01 00:00 UTC. Expected numbers in the tests were worked out by hand:

 case  events (hour)                                            duration
 c1    SUBMITTED 0, CHECK 2, REVIEW 10, APPROVED 11              11
 c2    SUBMITTED 0, CHECK 1, CHECK 5 (rework), REVIEW 6, DECLINED 7   7
 c3    SUBMITTED 0, CHECK 3, REVIEW 30, CANCELLED 31             31
 c4    SUBMITTED 0, CHECK 2, REVIEW 12, APPROVED 13              13
 c5    SUBMITTED 0, W_TASK schedule 0.5, start 1, complete 4, APPROVED 5   5
 c6    SUBMITTED 0, CHECK 2 (no final outcome)                   2
"""
from __future__ import annotations

import pandas as pd

from unjam.loader import standardize

A, B, C = "A_SUBMITTED", "B_CHECK", "C_REVIEW"
APPR, DECL, CANC, W = "A_APPROVED", "A_DECLINED", "A_CANCELLED", "W_TASK"

T0 = pd.Timestamp("2020-01-01 00:00:00", tz="UTC")

ROWS = [
    ("c1", A, 0), ("c1", B, 2), ("c1", C, 10), ("c1", APPR, 11),
    ("c2", A, 0), ("c2", B, 1), ("c2", B, 5), ("c2", C, 6), ("c2", DECL, 7),
    ("c3", A, 0), ("c3", B, 3), ("c3", C, 30), ("c3", CANC, 31),
    ("c4", A, 0), ("c4", B, 2), ("c4", C, 12), ("c4", APPR, 13),
    ("c5", A, 0), ("c5", W, 0.5, "SCHEDULE"), ("c5", W, 1, "START"), ("c5", W, 4, "COMPLETE"), ("c5", APPR, 5),
    ("c6", A, 0), ("c6", B, 2),
]


def make_events() -> tuple[pd.DataFrame, dict]:
    recs = []
    for r in ROWS:
        case, act, hour = r[0], r[1], r[2]
        life = r[3] if len(r) > 3 else "COMPLETE"
        recs.append({"case_id": case, "activity": act, "timestamp": (T0 + pd.Timedelta(hours=hour)).isoformat(),
                     "lifecycle": life, "resource": ""})
    raw = pd.DataFrame(recs)
    return standardize(raw, {k: k for k in raw.columns})
