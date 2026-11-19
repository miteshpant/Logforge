"""
docs/query-language.md is the LogforgeQL reference. It must stay true:

* every command, eval function and aggregation the compiler knows is
  documented;
* every example query in the guide (```logforgeql blocks) compiles.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import logql_pipeline as lp

DOC = Path(__file__).resolve().parents[1] / "docs" / "query-language.md"
TEXT = DOC.read_text()
EXAMPLES = re.findall(r"```logforgeql\n(.*?)```", TEXT, re.S)
AGGREGATIONS = ["count", "dc", "estdc", "sum", "avg", "min", "max", "median", "p95", "percentile", "stdev", "var",
                "values", "list", "earliest", "latest"]
LOOKUPS = {"users": lp.LookupMeta("users", 1, ["user_id", "department", "manager"], "user_id"),
           "blocklist": lp.LookupMeta("blocklist", 1, ["value"], "value"),
           "assets": lp.LookupMeta("assets", 1, ["host", "owner", "criticality"], "host")}


def test_every_command_function_and_aggregation_is_documented():
    for stage in lp.STAGES:
        assert re.search(rf"^### `{stage}`", TEXT, re.M), f"command {stage} is not documented"
    for name in lp.FUNCTIONS:
        assert f"`{name}(" in TEXT, f"function {name} is not documented"
    for name in AGGREGATIONS:
        assert f"`{name}(" in TEXT, f"aggregation {name} is not documented"


def test_there_are_plenty_of_examples():
    assert len(EXAMPLES) >= 40


@pytest.mark.parametrize("example", EXAMPLES, ids=[e.strip().splitlines()[0][:60] for e in EXAMPLES])
def test_examples_compile(example):
    end = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    query = " ".join(line.strip() for line in example.strip().splitlines())
    lp.compile_pipeline(query, customer_id="acme", start=end - timedelta(days=7), end=end, lookups=LOOKUPS,
                        variables={"service": "api", "env": "prod", "hosts": ["a", "b"]})
