# LogforgeQL reference

LogforgeQL is Logforge's query language. A query is a search followed by
commands joined with `|`. Each command works on the output of the one before
it, the way SPL, ES|QL and Kusto do:

```logforgeql
error timeout
| where service = "checkout" and status >= 500
| stats count() as failures, p95(attrs.duration_ms) as p95 by host
| sort -failures
| head 10
```

You can run queries in the Log Explorer (**LogQL** mode), save them, schedule
them, put them on dashboards, or send them to the API:

```
POST /v1/query/logql   {"query": "...", "since": "24h"}
```

Every value you type is sent to the database as a bound parameter, never as
SQL text. Every query runs only over your tenant's data and inside a time
window.

## Search and time

The first part of a query, before the first `|`, is a full-text search of
the log message. `*` or nothing matches everything. Put a phrase in quotes
to search for it as one piece of text.

```logforgeql
"connection reset" | stats count() as n by service
```

The time window comes from the time picker (or `start_time` / `end_time` /
`since` in the API). `| last 15m` (or `24h`, `7d`, `2w`) in the query sets it
instead. Without either, a query searches the last hour. The widest window is
31 days.

```logforgeql
| last 7d | where level = "error" | timechart span=1d count()
```

## Fields

| Field | Meaning |
|---|---|
| `ts` | event time |
| `host`, `service`, `level`, `msg` | where the event came from, its level, its message |
| `status`, `src_ip`, `user_id`, `trace_id`, `span_id` | common fields stored as columns |
| `attrs.<path>` | any attribute the event was sent with, e.g. `attrs.http.route` (nested paths work) |
| `ocsf.<path>` | the common schema, e.g. `ocsf.actor.user.name` (see [Common schema](schema.md)) |
| derived fields | `http_status`, `http_method`, `http_uri`, `http_response_time_ms`, `is_error`, `is_slow`, ... |

Fields made by `eval`, `rex`, `parse`, `json`, `lookup`, `join` and
`stats` can be used by every later command. After `stats`, `top`, `rare` or
`timechart`, only the columns those commands produce exist.

`attrs.*` and `ocsf.*` values are text. When you compare them with a number
or do arithmetic on them, they are converted to numbers. A value that isn't a
number becomes null, so it doesn't match.

## Expressions

`where` and `eval` take expressions:

| | |
|---|---|
| comparison | `=` (or `==`), `!=`, `<`, `<=`, `>`, `>=` |
| boolean | `and`, `or`, `not`, parentheses |
| text | `contains`, `startswith`, `endswith`, `like "a%b"`, `=~ "regex"`, `!~ "regex"` |
| lists | `in [200, 204]`, `not in ["debug", "trace"]` |
| missing values | `is null`, `is not null` (an empty attribute counts as null) |
| arithmetic | `+`, `-`, `*`, `/`, `%` |
| values | `"text"` or `'text'` (use `\"` inside), numbers, `true`, `false`, `null`, `$variable` |

Regular expressions are RE2, so lookarounds and backreferences are not
supported. Times compare with quoted dates: `ts > "2026-11-19T08:00:00Z"`.

```logforgeql
| where (service = "api" or service = "web") and not level in ["debug", "info"]
```

```logforgeql
| where msg =~ "timeout|refused" and attrs.duration_ms > 1000
```

## Commands

### `where`

Keeps the rows for which the expression is true. It works on events and on
the output of `stats`.

```logforgeql
| where status >= 500 and http_uri startswith "/api/"
```

```logforgeql
| stats count() as failures by user_id | where failures > 10
```

### `eval`

Adds or replaces fields: `eval name = expression[, name = expression]`. Each
assignment can use the ones before it.

```logforgeql
| eval kb = round(attrs.bytes / 1024, 1), big = if(kb > 500, "yes", "no")
```

```logforgeql
| eval class = case(status >= 500, "5xx", status >= 400, "4xx", "ok") | stats count() by class
```

### `stats`

Aggregates: `stats agg[ as name], ... [by field, ...]`. Without `as`, a
column is named after the aggregation, e.g. `count` or `avg(attrs.bytes)`.
Rows come out sorted by the `by` fields. See [Aggregations](#aggregations).

```logforgeql
| stats count() as events, dc(user_id) as users, p95(attrs.duration_ms) as p95 by service
```

```logforgeql
| stats count() as n by service, level | stats sum(n) as total, max(n) as worst by service
```

### `eventstats`

Like `stats`, but adds the result to every event instead of replacing the
events, so each event can be compared with its group.

```logforgeql
| eventstats avg(attrs.duration_ms) as svc_avg by service | where attrs.duration_ms > 3 * svc_avg
```

### `timechart`

Counts or aggregates over time: `timechart [span=1h] [limit=10] agg, ... [by
field]`. The output has `_time` and one column per aggregation. With
`by`, the `limit` busiest values get their own series and the rest are
grouped as `OTHER` (`limit=0` keeps every value). Without `by`, empty buckets
are filled with zeros. Without `span`, the span gives about 50 buckets over
the window.

```logforgeql
| where level = "error" | timechart span=1h count() by service
```

```logforgeql
| timechart span=15m avg(attrs.duration_ms) as avg_ms, p99(attrs.duration_ms) as p99_ms
```

### `top`

The most common values with their `count` and `percent`: `top [limit=10]
field[, field] [by field]`. With `by`, the top values within each group.

```logforgeql
| where attrs.outcome = "failure" | top limit=10 src_ip
```

```logforgeql
| top limit=3 status by service
```

### `rare`

The least common values, like `top`.

```logforgeql
| rare limit=5 attrs.user_agent
```

### `sort`

Orders rows: `sort [N] [-]field[, ...]` or `sort field desc`. `-` (or
`desc`) sorts in descending order. A number first keeps only that many rows.

```logforgeql
| stats count() as n by host | sort -n, host
```

```logforgeql
| sort 20 -attrs.duration_ms
```

### `head`

Keeps the first N rows (default 10, at most 10,000). Events are newest
first unless you `sort`.

```logforgeql
| where level = "error" | head 50
```

### `limit`

The same as `head`.

```logforgeql
| limit 100
```

### `dedup`

Keeps the first `N` events (default 1) for each value of the fields. Events
where a field is missing are dropped. Events are newest first, so `dedup
user_id` keeps each user's latest event.

```logforgeql
| dedup user_id | fields ts, user_id, src_ip
```

```logforgeql
| dedup 3 host, service
```

### `fields`

Keeps only the named fields, in that order. `fields - a, b` removes fields
instead.

```logforgeql
| fields ts, host, msg
```

```logforgeql
| fields - trace_id, span_id
```

### `table`

The same as `fields`.

```logforgeql
| where status >= 500 | table ts, service, http_uri, status
```

### `rename`

Renames fields: `rename old as new[, old as new]`.

```logforgeql
| rename src_ip as client, user_id as user
```

### `bin`

Puts values into buckets, in place or `as` a new field. Times take a span
like `5m` (or none, for about 50 buckets). Numbers need one, like `span=100`.

```logforgeql
| bin span=1h ts | stats count() as n by ts, service
```

```logforgeql
| bin span=100 attrs.duration_ms as latency_bucket | stats count() by latency_bucket
```

### `rex`

Extracts fields with a regular expression; each named group `(?<name>...)`
becomes a field. `field=` picks the text to search (default `msg`).

```logforgeql
| rex "user=(?<user>\w+) from (?<ip>\S+)" | stats count() by user, ip
```

### `parse`

Extracts fields with a pattern where `*` matches anything:
`parse [field=f] "<pattern>" as name, ...`.

```logforgeql
| parse "took * ms" as took | where took > 500 | stats count() as slow
```

### `json`

Reads values from JSON text: `json [field=f] "path"[ as name], ...`.

```logforgeql
| json field=attrs.payload "user.name" as who, "action" | stats count() by who, action
```

### `lookup`

Adds columns from a [lookup table](#lookup-tables) by matching a field to the
table's key: `lookup <table> <field> [as <key>] [output col[ as name], ...]`.
Without `output`, every column is added. When nothing matches, the columns
are null.

```logforgeql
| lookup users user_id output department, manager as boss | stats count() by department
```

```logforgeql
| lookup assets host | where criticality = "high" | stats count() as events by owner
```

### `join`

Joins the rows with the results of a second search on the same fields:
`join [type=inner|left] [max=10000] field[, field] [ subsearch ]`. The
subsearch runs on the same tenant and window, returns at most `max` rows
(at most 50,000), and is reduced to one row per key. `left` keeps rows with
no match, and their joined fields are empty or 0. Both sides may not have
other fields with the same name; rename one first.

```logforgeql
| where attrs.outcome = "failure" | stats count() as failures by user_id
| join type=left user_id [ | where attrs.outcome = "success" | stats count() as successes by user_id ]
| where successes = 0
```

```logforgeql
| join user_id [ | stats dc(src_ip) as ips by user_id ] | where ips > 5 | dedup user_id
```

### `last`

Sets the time window: `last 15m`, `last 24h`, `last 7d` (units s, m, h, d,
w; at most 90 days in the query, and the API's window limit still applies).

```logforgeql
| last 30m | where level = "error"
```

### `patterns`

Groups the lines the query selects into templates, with the variable parts
(addresses, ids, numbers, versions) as `<*>`: up to 1 million lines of the
window, in a few seconds. It must be the last stage. Each row is a template:
`pattern`, `count`, `first_seen`, `last_seen`, an `example` line, the
`services` it came from, and two flags:

- `new`: the template never appeared in the same query over the 7 days
  before the window;
- `rare`: it appeared at most twice in the window.

`| patterns new` keeps only the new ones and `| patterns rare` the new or
rare ones. A saved search on `| patterns new` with "more than 0 rows" alerts
on a sudden new pattern.

```logforgeql
| where service = "checkout" | patterns
```

```logforgeql
| where level = "error" | patterns new
```

## Functions

For `eval` and `where`:

| Function | Result |
|---|---|
| `if(cond, then, else)` | `then` when `cond` is true, otherwise `else` |
| `case(c1, v1, c2, v2, ..., [default])` | the value of the first true condition |
| `coalesce(a, b, ...)` | the first value that isn't null or empty |
| `isnull(x)`, `isnotnull(x)` | whether a value is missing (an empty attribute counts as missing) |
| `lower(s)`, `upper(s)`, `trim(s)` | case and whitespace |
| `len(s)` | length in characters |
| `substr(s, start[, length])` | part of a text; `start` counts from 1 |
| `replace(s, "regex", "replacement")` | replaces every match |
| `match(s, "regex")` | whether the regex matches |
| `like(s, "pattern")` | SQL LIKE: `%` any text, `_` one character |
| `concat(a, b, ...)` | joined as text |
| `tonumber(x)`, `tostring(x)` | conversions (`tonumber` of text that isn't a number is null) |
| `round(x[, digits])`, `floor(x)`, `ceil(x)`, `abs(x)` | rounding |
| `sqrt(x)`, `ln(x)`, `log10(x)`, `exp(x)`, `pow(x, y)` | maths |
| `least(a, b)`, `greatest(a, b)` | the smaller or larger number |
| `now()` | the current time |
| `hour(t)`, `minute(t)`, `dayofweek(t)` (1 = Monday), `date(t)` | parts of a time |
| `strftime(t, "%Y-%m-%d %H:%M")` | a time as text |
| `cidrmatch("10.0.0.0/8", ip)` | whether an IP is in a network (false for anything that isn't an IP) |
| `json_extract(s, "a.b")` | a value from JSON text |
| `inlookup("table", x)` | whether `x` is a key of a [lookup table](#lookup-tables) |

```logforgeql
| where cidrmatch("10.0.0.0/8", src_ip) and not inlookup("blocklist", src_ip)
| eval hour = hour(ts), day = strftime(ts, "%a")
| stats count() by day, hour
```

```logforgeql
| eval region = coalesce(attrs.region, attrs.cloud.region, "unknown"), route = lower(replace(http_uri, "[0-9]+", ":id"))
| stats count() by region, route
```

## Aggregations

For `stats`, `eventstats` and `timechart`. Each takes a field or an
expression, e.g. `avg(attrs.bytes / 1024)`. Name an aggregation of an
expression with `as`.

| Aggregation | Result |
|---|---|
| `count()` | rows; `count(x)` counts rows where `x` is present |
| `dc(x)` | distinct values (exact); `estdc(x)` is a fast estimate |
| `sum(x)`, `avg(x)`, `min(x)`, `max(x)` | numbers (`min` / `max` of a time give a time) |
| `median(x)`, `p50(x)` ... `p95(x)` ... `p99(x)`, `percentile(x, 99.9)` | percentiles (exact below ~8,000 values per group, a close estimate above) |
| `stdev(x)`, `var(x)` | sample standard deviation and variance |
| `values(x)` | up to 100 distinct values, sorted |
| `list(x)` | up to 100 values |
| `earliest(x)`, `latest(x)` | the value of the first and last event in time |

```logforgeql
| stats count() as requests, avg(http_response_time_ms) as avg_ms, p95(http_response_time_ms) as p95_ms,
  values(http_method) as methods, earliest(ts) as first, latest(ts) as last by service
```

```logforgeql
| stats percentile(attrs.duration_ms, 99.9) as p999, stdev(attrs.duration_ms) as sd by service
```

## Variables

`$name` is a value supplied with the query (`"variables": {"name": ...}` in
the API, or a dashboard variable). It is bound like any other value, so it
can't change the query's structure. A list works with `in`.

```logforgeql
| where service = $service and host in $hosts | timechart count()
```

On dashboards a variable can be **All** (`*`): a comparison with All is true
for every row, so `where service = $service` shows every service.

## Lookup tables

A lookup is a small table you upload: a CSV with a header row (up to 100,000
rows, 32 columns, 10 MB), keyed by its first column or by `key`. A managed
list has a single `value` column. Uploading again replaces the table in one
step: queries see either the old version or the new one, never a mix.

```
PUT  /v1/query/lookups/users      {"csv": "user_id,department,manager\nu1,finance,ann\n"}
PUT  /v1/query/lookups/blocklist  {"values": ["203.0.113.9", "198.51.100.7"]}
POST /v1/query/lookups/blocklist/values  {"add": ["192.0.2.1"], "remove": ["198.51.100.7"]}
GET  /v1/query/lookups            the tenant's tables
```

```logforgeql
| where inlookup("blocklist", src_ip) | stats count() as hits, values(user_id) as users by src_ip
```

## Saved and scheduled searches

`/v1/query/searches` stores a query with a name. With `every` (5m to 7d) it
runs on a schedule over the last `window`. A run can **alert** when the
result meets a condition (the row count, or a number in any row), at most
once per `throttle_minutes`. It can also send a **report** of the rows to
notification channels (by email with `report.csv` attached), on every run
or only when it alerts. A run that fails is recorded as an error, never as
"no results". `POST /v1/query/searches/{id}/run` previews a run.

```json
{"name": "Brute force", "query": "| where attrs.outcome = \"failure\" | stats count() as n by src_ip | where n > 20",
 "every": "15m", "window": "1h",
 "alert": {"condition": {"kind": "rows", "op": "gt", "value": 0}, "severity": "high",
           "channels": ["<channel id>"], "throttle_minutes": 60}}
```

## Dashboards

Any query can be a dashboard panel: **Add to dashboard** in the Log
Explorer, or a widget with `"query_definition": {"logql": "..."}`. A
single-value panel shows the first number of the first row. A chart takes
its labels from the first text or time column, with one series per number
column; a `timechart ... by` gives one series per value. Dashboard variables
(fixed values, values from a query, or free text, optionally with All) are
used as `$name` in panel queries. The dashboard's time picker sets the
window.

## Performance and limits

- **Hourly counts.** Count queries over `service`, `level` and `status`
  (`stats` / `timechart` / `top` / `rare` with `count()`, after `where`,
  `eval` and `bin` on those fields, over at least two hours) read an hourly
  summary instead of every event. The partial hours at each end of the
  window are counted from the events, so the answer is exact. The response's
  `query_info.hourly_counts` says when this happened.
- **Cost limit.** Before a query runs, the database estimates how many rows
  it will read. Each plan has a limit per query; a query over it is refused
  with a message. `POST /v1/query/estimate` (same body as `/query/logql`)
  returns the estimate without running anything.
- A query returns at most 10,000 rows (events: 100 unless you `head` or
  `sort N`). A query runs for at most 30 seconds.
- Filter early: `where service = ...` and `where level = ...` narrow what is
  read the most, because events are stored sorted by them. Trace ids, source
  IPs and user ids have their own indexes.

## Compatibility with earlier LogforgeQL

Queries that the first version of LogforgeQL accepted (search, `where` with
`and`, `stats`, `sort`, `limit`, `last`, `rex`, `parse`, `json`) still run as
before and return the same shape. Queries that use anything else run on the
pipeline engine described here. This also fixed two places where the first
version gave wrong answers without any error:

- `stats ... | where n > 3` filtered the events before counting, instead of
  filtering the counts;
- a query starting with a command it didn't know, such as `| eval ...`, was
  run as a full-text search for that text.

## Cookbook

Top source IPs by failed logins per hour, this week:

```logforgeql
| last 7d | where ocsf.status_id = 2 | bin span=1h ts | stats count() as failures by ts, src_ip
| sort -failures | head 10
```

Error rate per service:

```logforgeql
| stats count() as total, count(if(is_error = 1, 1, null)) as errors by service
| eval error_rate = round(100 * errors / total, 2) | sort -error_rate
```

Slowest endpoints at p95, with traffic:

```logforgeql
| where isnotnull(http_response_time_ms)
| stats count() as requests, p95(http_response_time_ms) as p95_ms by service, http_uri
| where requests > 100 | sort -p95_ms | head 20
```

Users who logged in from more than three countries:

```logforgeql
| where ocsf.class_uid = 3002 and ocsf.status_id = 1
| stats dc(attrs.geo.country) as countries, values(attrs.geo.country) as seen by user_id
| where countries > 3
```

New hosts today compared with the rest of the week:

```logforgeql
| last 7d | stats earliest(ts) as first_seen by host | where first_seen > "2026-11-19T00:00:00Z"
```

Failures without any success for the same user:

```logforgeql
| where attrs.outcome = "failure" | stats count() as failures by user_id
| join type=left user_id [ | where attrs.outcome = "success" | stats count() as successes by user_id ]
| where successes = 0 and failures > 5 | sort -failures
```

Latency distribution:

```logforgeql
| bin span=50 http_response_time_ms as ms | stats count() as requests by ms | sort ms
```

Busiest hour of the week by service:

```logforgeql
| last 7d | eval day = dayofweek(ts), hour = hour(ts) | stats count() as n by service, day, hour
| sort -n | dedup service
```

Requests from assets owned by a team:

```logforgeql
| lookup assets host output owner, criticality | where owner = "payments" | timechart span=1h count() by criticality
```

Events that are much slower than their service's average:

```logforgeql
| eventstats avg(http_response_time_ms) as svc_avg, stdev(http_response_time_ms) as svc_sd by service
| where http_response_time_ms > svc_avg + 3 * svc_sd | table ts, service, http_uri, http_response_time_ms
```

Hosts that stopped sending (no events in the last hour, but some earlier):

```logforgeql
| last 24h | stats latest(ts) as last_seen by host | where last_seen < "2026-11-19T11:00:00Z"
```

Message patterns: errors by the first words of the message:

```logforgeql
| where level = "error" | eval pattern = replace(substr(msg, 1, 40), "[0-9]+", "N")
| top limit=20 pattern
```
