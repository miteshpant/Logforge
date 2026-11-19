"""
Pipeline benchmark (Phase 4 acceptance: a 10-processor pipeline keeps ingest
within 20% of the Phase 0 baseline). The live runner needs a stack; these
tests pin the deterministic parts: the benchmark pipeline is valid, has ten
processors, and processes the benchmark traffic without failures.
"""

import pipeline_bench as bench
from pipeline_processors import ProcessorContext
from pipeline_store import PipelineRecord


def test_the_benchmark_pipeline_has_ten_working_processors():
    record = PipelineRecord.from_dict(bench.TEN_PROCESSORS)
    assert len(record.pipeline.steps) == 10 and record.routing["default"] is True
    for event in bench.traffic(50, "r1"):
        result = record.pipeline.run(dict(event, attrs=dict(event["attrs"])), ProcessorContext())
        assert result.status == "ok", result.error
        attrs = result.doc["attrs"]
        assert isinstance(attrs["bytes"], int) and attrs["action"].islower() and "[email]" in result.doc["msg"]


def test_rate_and_comparison():
    assert bench.rate(5000, 20.0) == 250.0
    cmp = bench.compare({"events_per_second": 250.0}, {"events_per_second": 230.0}, limit_pct=20)
    assert cmp["drop_pct"] == 8.0 and cmp["pass"] is True
