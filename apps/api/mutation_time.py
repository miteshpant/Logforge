"""The current time as a bound parameter for ClickHouse mutations.

`now()` inside ALTER TABLE ... UPDATE is evaluated by each replica on its own,
so replicated tables would diverge; ClickHouse refuses it unless
allow_nondeterministic_mutations is on. Mutations bind this value instead, as
`col = toDateTime64(%(now)s, 3)`: a UTC string with milliseconds (datetime
parameters lose them) that casts to DateTime and DateTime64 columns alike.
"""

from datetime import datetime, timezone


def now_param() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
