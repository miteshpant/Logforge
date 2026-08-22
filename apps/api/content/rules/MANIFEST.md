# Vendored SigmaHQ detection rules (LF-005)

Rules under `linux/`, `web/` and `windows/` are vendored VERBATIM from the
public SigmaHQ ruleset:

- Upstream: https://github.com/SigmaHQ/sigma
- Pinned commit: `3c0d35188942eb6a8c373e4f4973ac7e84116993` (2026-08-13)
- License: Detection Rule License (DRL) 1.1 — see `LICENSE` in this directory.

## Selection criteria

Only rules the LogForge sigma engine can evaluate faithfully were vendored:

- every detection selection is a field mapping (no keyword lists / list-of-maps)
- every field translates to a LogForge normalized field
  (see `config/field_mapping.yml`; e.g. `Image` → `process_name`,
  `CommandLine` → `command_line`, `c-uri` → `url`, `c-useragent` → `user_agent`)
- every modifier is supported by `SigmaFieldMatcher`
  (`contains`, `all`, `startswith`, `endswith`, `re`, `gt/gte/lt/lte`)
- the condition parses in `sigma_condition.py`'s grammar (no aggregations)
- the rule declares at least one MITRE ATT&CK technique tag
- Windows process-creation rules are additionally restricted to
  `level: high|critical` to keep the default pack high-confidence

Source directories: `rules/linux/process_creation`, `rules/linux/builtin`,
`rules/web/webserver_generic`, `rules/web/proxy_generic`,
`rules/windows/process_creation`.

## Loading

`apps/api/mitre_default_loader.py` loads these files at API startup as
platform-default rules (`customer_id = 'default'`, `created_by = 'system'`,
rule ids `sigma_default_<upstream-uuid>`). At load time it:

1. translates field names to the normalized vocabulary and `|re` → `|regex`;
2. synthesises a true-positive fixture from the rule's own detection logic and
   verifies the translated rule FIRES on it via the real engine evaluator;
3. verifies the rule stays SILENT on a benign event corpus (ordinary logons,
   web requests, cron activity);
4. stores the verified fixtures inside `rule_content.fixtures`.

Rules failing any gate are NOT inserted — they are reported as
`awaiting_content` so coverage numbers stay honest.

## Updating

Re-run the vendoring selection against a newer upstream commit, update the
pinned commit above, and let the loader reconcile on the next API start
(insert-missing-only; removal of retired upstream rules is manual).
