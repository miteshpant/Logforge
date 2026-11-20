# Detection-as-code

A tenant's detection rules can live in a git repository as Sigma YAML and be
synced into Logforge from CI. Every rule goes through the same fixture gate
as the rules Logforge ships, and can be backtested against your stored logs
before it is enabled.

## Repository layout

Any directory of `*.yml` / `*.yaml` files. A file may hold several rules as
YAML documents (separated by `---`), which keeps base rules next to the
correlations built on them:

```yaml
title: Failed login
id: acme-auth-failed
name: acme_auth_failed       # how correlations reference it
generate: false              # building block: feeds correlations, never alerts
level: low
description: One failed authentication.
tags: [attack.t1110]
detection:
  selection: {event_type: authentication, result: failed}
  condition: selection
fixtures:
  true_positive: {event_type: authentication, result: failed, src_ip: 203.0.113.9, user: root}
  true_negative: {event_type: authentication, result: success, src_ip: 203.0.113.9, user: root}
---
title: Password spray
id: acme-spray
level: high
description: Failed logins for 3+ accounts from one source within 10 minutes.
tags: [attack.credential_access, attack.t1110.003]
correlation:
  type: value_count          # event_count | value_count | value_sum | temporal | temporal_ordered
  rules: [acme_auth_failed]
  group-by: [src_ip]
  timespan: 10m
  condition: {field: user, gte: 3}
fixtures:
  true_positive_batch:
    - {event_type: authentication, result: failed, src_ip: 203.0.113.9, user: alice}
    - {event_type: authentication, result: failed, src_ip: 203.0.113.9, user: bob}
    - {event_type: authentication, result: failed, src_ip: 203.0.113.9, user: carol}
  true_negative_batch:
    - {repeat: 5, every: 10s, event: {event_type: authentication, result: failed, src_ip: 203.0.113.9, user: root}}
```

A sequence (`temporal` or `temporal_ordered`) can name `until` rules: a match
of one for the group abandons the sequence so far. Brute force then a
successful sign-in, unless the password was reset in between:

```yaml
correlation:
  type: temporal_ordered
  rules: [acme_auth_failed, acme_auth_ok]
  until: [acme_password_reset]
  group-by: [user]
  timespan: 30m
```

`until` is a Logforge extension to the Sigma correlation format. Its rules
are referenced like `rules` (they must be in the rule set, and backtests
replay them).

**Correlations over alerts** reference `alerts` (every alert another rule
raises) or `alerts:<severity>` (`alerts:high`, ...). Each alert is fed in
once, on the event that raised it, with `alert.rule_id`, `alert.severity`,
`alert.technique` (the rule's first, primary ATT&CK technique) and
`alert.techniques`. Three different techniques on one host within an hour:

```yaml
correlation:
  type: value_count
  rules: [alerts]
  group-by: [hostname]
  timespan: 1h
  condition: {field: alert.technique, gte: 3}
```

The shipped `lf-c-multi-technique-host` is this rule. Alerts of correlations
over alerts aren't fed back, so they can't loop. Their fixtures and
backtests replay every rule in the set, since any of them can raise the
alerts they count.

Fixture timelines: a plain event comes 1 s after the previous one;
`{repeat: N, every: 30s, event: ...}` repeats it; `{at: 5m, event: ...}`
places it at an offset from the start.

## The gate

A sync is rejected as a whole (nothing is applied) if any rule:

* doesn't parse, has an invalid or duplicate id, or no MITRE technique tag;
* fails its fixtures: the positive must fire, the negative must not, and an
  alerting rule must stay silent on the built-in benign corpus;
* is a correlation that references a rule not in the rule set, or forms a
  reference cycle;
* takes the id of a rule created in the UI;
* (with `backtest_days`) would have alerted more than `max_alerts_per_day`
  over the last N days of your logs.

Correlations can only reference rules in the same rule set.

## Syncing from CI

`scripts/rules_sync.py` posts the repository to
`POST /v1/security/rules/sync`, prints the plan and exits 0 (accepted),
1 (rejected) or 2 (request failed). A dry run on pull requests, apply on
the main branch:

```yaml
# .github/workflows/detections.yml in your detection repository
name: detections
on:
  pull_request:
  push:
    branches: [main]
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with: {repository: miteshpant/Logforge, path: logforge, sparse-checkout: scripts}
      - name: Sync rules
        env:
          LOGFORGE_TOKEN: ${{ secrets.LOGFORGE_TOKEN }}
        run: |
          python logforge/scripts/rules_sync.py \
            --api "${{ vars.LOGFORGE_API }}" --tenant "${{ vars.LOGFORGE_TENANT }}" \
            --dir rules --backtest-days 7 --max-alerts-per-day 50 \
            ${{ github.event_name == 'push' && '--apply --prune' || '' }}
```

`--prune` disables synced rules that were removed from the repository. An
empty rule set is always an error, so a broken checkout can't disable
everything.

## Exporting

`GET /v1/security/rules/export` returns the tenant's enabled rules as Sigma
YAML, fixtures included; syncing that file back reports every rule
unchanged. `?include_defaults=true` adds the shipped library (ids without
the `logforge_` prefix), a starting point for forking a rule.

## Related

* `POST /v1/security/rules/{rule_id}/backtest`: replay one rule over a time
  range ([performance](benchmarks/backtest.md)).
* `POST /v1/security/tuning`: exclusions and throttles for noisy rules;
  `GET /v1/security/rules/{rule_id}/tuning-suggestion` proposes an
  exclusion from false-positive verdicts.
