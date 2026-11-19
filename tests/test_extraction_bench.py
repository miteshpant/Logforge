"""
Search-time extraction benchmark (Phase 5 acceptance: extraction on 10 M
rows completes within 2x the cost of the same query on an ingest-time
field). The live runner needs a stack; these tests pin the query pairs and
the verdict.
"""

import extraction_bench as bench
import logql


def test_every_pair_counts_the_same_value_both_ways():
    for name, ingest_time, search_time in bench.QUERY_PAIRS:
        a, b = logql.compile_to_request_payload(ingest_time), logql.compile_to_request_payload(search_time)
        assert a["aggregations"] == b["aggregations"] and not a.get("extractions"), name
        assert b["extractions"], name
        assert a["filters"][-1]["value"] == b["filters"][-1]["value"], name


def test_verdict_is_the_ratio_of_medians():
    result = bench.verdict({"rex": {"ingest_p50_ms": 100.0, "search_p50_ms": 180.0},
                            "json": {"ingest_p50_ms": 100.0, "search_p50_ms": 230.0}}, limit=2.0)
    assert result["rex"] == {"ratio": 1.8, "pass": True} and result["json"]["pass"] is False
    assert result["all_pass"] is False
