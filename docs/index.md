# Logforge

Open-source log management, alerting, security detection (SIEM) and
observability, self-hosted with one command. Apache 2.0.

!!! note "Project status: early / alpha"
    Ingestion, storage, search, alerting and detection are real and tested.
    The "AI" features are still keyword templates without a language model.
    The roadmap is public and honest about what is missing.

## Start here

- **[Quick start and README](https://github.com/miteshpant/Logforge#readme)**: deploy the stack with
  `./deploy.sh`, create the first admin, send your first log.
- **[API reference](api/index.html)**: every endpoint (OpenAPI 3.1, also as
  [YAML](api/openapi.yaml) and [JSON](api/openapi.json)).
- **[Shipper recipes](https://github.com/miteshpant/Logforge/tree/main/packages/shipper-recipes)**:
  Vector, Fluent Bit and Fluentd configs that send logs to Logforge.

## Guides

- **[Detection-as-code](detection-as-code.md)**: correlation rules, backtesting,
  tuning, and syncing rules from git.
- **[Cases](cases.md)**: how alerts become cases, analyst actions, SLA metrics
  and the audit export.
- **[Threat intelligence](threat-intel.md)**: feeds, ingest-time matching,
  retro-hunting and enrichment (GeoIP, assets, users).
- **[Ingest pipelines](pipelines.md)**: parse, mask and shape logs on the way in;
  routing, testing against samples, dead-letter queue.
- **[Common schema](schema.md)**: OCSF fields in rules and queries, source
  mappings, search-time `rex` / `parse` / `json`, and the field explorer.
- **[Query language](query-language.md)**: the LogforgeQL reference:
  commands, functions, lookups, joins, saved and scheduled searches,
  dashboard panels, and a cookbook of analyst questions.
- **[Content packs](packs.md)**: one-step installs for Linux, web servers,
  AWS, Okta and Google Workspace, Windows and Kubernetes (pipelines, rules,
  searches, dashboards), and how to write a pack.

## Where it's going

- **[Roadmap](ROADMAP.md)**: short, claimable tasks, including good first issues.
- **[Platform roadmap](PLATFORM_ROADMAP.md)**: the phased plan toward a
  unified, AI-assisted security and observability platform.

## How well it works

- **[Benchmarks](benchmarks/README.md)**: ingest throughput, ingest-to-searchable
  latency and query latency, per release.
- **[Detection evaluation](https://github.com/miteshpant/Logforge/tree/main/tests/eval/detection)**:
  what the shipped rules detect on labelled attack scenarios, and how noisy
  they are on benign traffic. CI fails on regressions.

## Background

- [Architecture](ARCHITECTURE_MINDMAP.md)
- [Code analysis](CODE_ANALYSIS.md)
- [QA report](QA_REPORT.md)
- [Enhancement log](ENHANCEMENTS.md)

## Contributing

See [CONTRIBUTING.md](https://github.com/miteshpant/Logforge/blob/main/CONTRIBUTING.md) and the
[Code of Conduct](https://github.com/miteshpant/Logforge/blob/main/CODE_OF_CONDUCT.md). Report
security issues privately as described in
[SECURITY.md](https://github.com/miteshpant/Logforge/blob/main/SECURITY.md).
