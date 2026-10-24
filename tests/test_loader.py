import gzip
import io

import pandas as pd

from helpers import APPR, A, B, C, W, make_events
from unjam.loader import LogFormatError, build_cases, guess_columns, load_log, parse_xes, prepare_instances, standardize

XES = b"""<?xml version="1.0" encoding="UTF-8" ?>
<log xes.version="1.0" xmlns="http://www.xes-standard.org/">
 <string key="concept:name" value="demo log"/>
 <trace>
  <string key="concept:name" value="100"/>
  <int key="AMOUNT_REQ" value="2000"/>
  <event><string key="concept:name" value="A_SUBMITTED"/><string key="lifecycle:transition" value="COMPLETE"/>
         <date key="time:timestamp" value="2011-10-01T00:38:44.546+02:00"/><string key="org:resource" value="112"/></event>
  <event><string key="concept:name" value="W_Task"/><string key="lifecycle:transition" value="START"/>
         <date key="time:timestamp" value="2011-10-01T09:00:00.000+02:00"/></event>
  <event><string key="concept:name" value="W_Task"/><string key="lifecycle:transition" value="COMPLETE"/>
         <date key="time:timestamp" value="2011-10-01T11:00:00.000+02:00"/></event>
 </trace>
 <trace>
  <event><string key="concept:name" value="A_SUBMITTED"/><date key="time:timestamp" value="2011-10-02T10:00:00.000+02:00"/></event>
 </trace>
</log>"""


def test_parse_xes_reads_cases_and_events():
    df = parse_xes(io.BytesIO(XES))
    assert len(df) == 4
    assert df["case_id"].tolist() == ["100", "100", "100", "trace_2"]  # trace without id gets a name
    assert df.loc[0, "resource"] == "112"


def test_load_log_handles_gzip_and_converts_to_utc():
    events, q = load_log(gzip.compress(XES), name="demo.xes.gz")
    assert q["source_kind"] == "xes" and q["cases"] == 2 and q["events"] == 4
    assert str(events["timestamp"].min()) == "2011-09-30 22:38:44.546000"  # +02:00 -> UTC


def test_bad_file_gives_friendly_error():
    try:
        load_log(b"not xml at all", name="x.xes")
        assert False, "should raise"
    except LogFormatError as exc:
        assert "XES" in str(exc)


def test_csv_with_semicolons_and_column_guess():
    csv = "Case ID;Activity;Timestamp\n1;A;2020-01-01 10:00\n1;B;2020-01-01 12:00\n2;A;2020-01-02 10:00\n"
    events, q = load_log(csv.encode(), name="log.csv")
    assert q["cases"] == 2 and len(events) == 3
    assert guess_columns(["Case ID", "Activity", "Timestamp"])["case_id"] == "Case ID"


def test_missing_required_column_message():
    raw = pd.DataFrame({"foo": [1], "bar": [2]})
    try:
        standardize(raw, guess_columns(raw.columns))
        assert False
    except LogFormatError as exc:
        assert "case_id" in str(exc)


def test_instances_merge_start_complete_and_ignore_schedule():
    events, _ = make_events()
    inst, stats = prepare_instances(events)
    assert stats["events_in"] == 24 and stats["instances"] == 22
    assert stats["ignored_lifecycle"] == {"SCHEDULE": 1}
    w = inst[inst["activity"] == W].iloc[0]
    assert (w["wait_h"], w["work_h"]) == (1.0, 3.0)
    appr5 = inst[(inst["case_id"] == "c5") & (inst["activity"] == APPR)].iloc[0]
    assert appr5["wait_h"] == 1.0


def test_waits_of_check_step_and_durations():
    events, _ = make_events()
    inst, _ = prepare_instances(events)
    b = inst[inst["activity"] == B]["wait_h"]
    assert sorted(b.tolist()) == [1, 2, 2, 2, 3, 4]
    cases = build_cases(inst)
    assert cases["duration_h"].median() == 9.0
    assert inst["wait_h"].dropna().min() >= 0
